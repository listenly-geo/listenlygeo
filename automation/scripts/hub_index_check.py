#!/usr/bin/env python3
"""
Verifie dans Search Console si les fiches N1 (hubs) en attente de leurs questions sont indexees (29/09/2026).
Regle : la fiche sort dans sa version propre ; les fiches requete (extraction) ne demarrent qu'une fois la fiche
indexee (ou apres DELAI_MAX jours, garde-fou). Ecrit pages/podcast-btb/data/gsc_hub_status.json.
Ne casse jamais le run : sans acces Search Console, le garde-fou a delai s'applique.
"""
import os, sys, json, time, datetime, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hub_consolidation as hc  # noqa: E402
from fetch_gsc_stats import get_access_token  # noqa: E402

STATUS = "pages/podcast-btb/data/gsc_hub_status.json"
QUEUE = "automation/marketforge_engine/queue.json"
MAX_PER_RUN = int(os.environ.get("HUB_INSPECT_MAX", "80"))


def log(m):
    print(f"[hub-index-check] {m}", flush=True)


def main():
    raw = os.environ.get("GSC_SERVICE_ACCOUNT_JSON")
    if not raw:
        log("Pas d'acces Search Console : garde-fou a delai uniquement.")
        return
    queue = hc.load(QUEUE, {"podcasts": {}})
    status = hc.load(STATUS, {})
    today = datetime.date.today().isoformat()
    two_days = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
    podcasts = hc.load("pages/podcast-btb/data/podcasts.json", [])
    prospects = {p.get("slug"): p.get("statut") for p in (hc.load("automation/marketforge_engine/prospection_stats.json", {}).get("prospects") or [])}
    waiting = {s for s, st in queue.get("podcasts", {}).items()
               if not st.get("episodes_done") and st.get("status") in ("en_attente", "contact", "sans_email", "en_cours")}
    # tous les hubs : ceux qui attendent leurs questions d'abord, puis les prospects, puis les plus recents
    rank = lambda p: (p["slug"] not in waiting, p["slug"] not in prospects, "".join(chr(255 - ord(c)) for c in (p.get("date") or "")[:10]))
    todo = [p["slug"] for p in sorted((p for p in podcasts if p.get("slug")), key=rank)
            if not status.get(p["slug"], {}).get("indexed_on")
            and (status.get(p["slug"], {}).get("date") or "") < two_days]
    log(f"{len(todo)} fiche(s) N1 a verifier, {min(len(todo), MAX_PER_RUN)} ce run.")
    if not todo:
        return
    try:
        token = get_access_token(json.loads(raw))
    except Exception as e:  # noqa: BLE001
        log(f"Authentification impossible ({e}) : garde-fou a delai uniquement.")
        return
    n = ok = 0
    for s in todo[:MAX_PER_RUN]:
        try:
            r = hc.api(token, "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
                       {"inspectionUrl": f"{hc.BASE}{s}-podcast.html", "siteUrl": hc.SITE})
            ir = r.get("inspectionResult", {}).get("indexStatusResult", {})
            rec = {"verdict": ir.get("verdict", ""), "coverage": ir.get("coverageState", ""), "date": today}
            if hc.is_indexed(rec):
                rec["indexed_on"] = today
                ok += 1
            status[s] = rec
            n += 1
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")[:150]
            log(f"Erreur {e.code} sur {s} : {body}")
            if e.code == 429 or "quota" in body.lower():
                break
        except Exception as e:  # noqa: BLE001
            log(f"Erreur sur {s} : {e}")
        time.sleep(0.15)
    hc.save(STATUS, status)
    log(f"{n} fiche(s) inspectee(s), {ok} indexee(s).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        log(f"Ignore (non bloquant) : {e}")

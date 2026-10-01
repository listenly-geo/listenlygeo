#!/usr/bin/env python3
"""
Diagnostic detaille des fiches N1 (hubs) que Google n'indexe pas (01/10/2026).
Pour chaque fiche N1 ancienne non indexee (+ un echantillon de fiches indexees pour comparer), relevé via l'API
URL Inspection : derniere exploration, canonique choisie par Google vs canonique declaree, etat de recuperation,
robots, sitemaps qui la referencent, pages qui renvoient vers elle. Ecrit pages/podcast-btb/data/gsc_hub_diagnostic.json.
Lecture seule cote Search Console. Ne casse jamais le run.

  python hub_index_diagnostic.py            : diagnostic reel (secret GSC_SERVICE_ACCOUNT_JSON requis)
  python hub_index_diagnostic.py --dry-run  : liste seulement les URL qui seraient inspectees
"""
import os, sys, json, time, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hub_consolidation as hc  # noqa: E402
from fetch_gsc_stats import get_access_token  # noqa: E402

OUT = "pages/podcast-btb/data/gsc_hub_diagnostic.json"
STATUS = "pages/podcast-btb/data/gsc_hub_status.json"
CUTOFF = os.environ.get("DIAG_CUTOFF", "2026-09-15")   # fiches creees avant cette date = deja "en retard"
CONTROL = int(os.environ.get("DIAG_CONTROL", "20"))    # fiches indexees inspectees pour comparaison
MAX_URLS = int(os.environ.get("DIAG_MAX", "250"))


def log(m):
    print(f"[hub-diagnostic] {m}", flush=True)


def targets():
    pods = hc.load("pages/podcast-btb/data/podcasts.json", [])
    st = hc.load(STATUS, {})
    stalled, indexed = [], []
    for p in pods:
        s = p.get("slug")
        if not s:
            continue
        v = st.get(s, {})
        if v.get("indexed_on"):
            indexed.append(s)
        elif (p.get("date") or "9999") < CUTOFF:
            stalled.append(s)
    return stalled, indexed[:CONTROL]


def main():
    stalled, control = targets()
    urls = [(s, "bloquee") for s in stalled] + [(s, "indexee") for s in control]
    urls = urls[:MAX_URLS]
    log(f"{len(stalled)} N1 anciennes non indexees + {len(control)} indexees (controle) = {len(urls)} a inspecter.")
    if "--dry-run" in sys.argv:
        for s, g in urls:
            print(g, f"{hc.BASE}{s}-podcast.html")
        return
    raw = os.environ.get("GSC_SERVICE_ACCOUNT_JSON")
    if not raw:
        log("Pas d'acces Search Console (secret absent) : rien a faire.")
        return
    token = get_access_token(json.loads(raw))
    out, errors = {}, 0
    for s, groupe in urls:
        url = f"{hc.BASE}{s}-podcast.html"
        try:
            r = hc.api(token, "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
                       {"inspectionUrl": url, "siteUrl": hc.SITE, "languageCode": "fr"})
            ir = r.get("inspectionResult", {}).get("indexStatusResult", {})
            out[s] = {
                "groupe": groupe, "url": url,
                "verdict": ir.get("verdict"), "coverage": ir.get("coverageState"),
                "last_crawl": ir.get("lastCrawlTime"), "crawled_as": ir.get("crawledAs"),
                "fetch_state": ir.get("pageFetchState"), "robots": ir.get("robotsTxtState"),
                "indexing_state": ir.get("indexingState"),
                "google_canonical": ir.get("googleCanonical"), "user_canonical": ir.get("userCanonical"),
                "sitemaps": ir.get("sitemap") or [], "referring_urls": (ir.get("referringUrls") or [])[:10],
            }
        except Exception as e:  # noqa: BLE001
            errors += 1
            out[s] = {"groupe": groupe, "url": url, "erreur": str(e)[:200]}
            if errors >= 10:
                log("Trop d'erreurs, arret.")
                break
        time.sleep(0.15)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"date": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"), "cutoff": CUTOFF, "fiches": out},
                  f, ensure_ascii=False, indent=1)
        f.write("\n")
    log(f"{len(out)} fiche(s) ecrite(s) dans {OUT} ({errors} erreur(s)).")


if __name__ == "__main__":
    main()

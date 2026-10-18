#!/usr/bin/env python3
"""Chaque jour : choisit 10 pages de moments a faire indexer, verifie chaque URL .org et son etat
dans la Search Console (API d'inspection, lecture seule), ecrit pages/podcast-btb/data/indexation_du_jour.json.
Selection : pages de MOMENTS validees par le systeme (gate=True), pas les fiches question.
La demande d'indexation elle-meme se fait a la main (session Claude + Chrome, validation par page).
Secret : GSC_SERVICE_ACCOUNT_JSON. Ne bloque jamais le workflow : en cas d'erreur, la liste est ecrite quand meme."""
import os, json, datetime
import requests

PAGES = "pages/podcast-btb"
OUT = f"{PAGES}/data/indexation_du_jour.json"
SITE = os.environ.get("GSC_SITE", "sc-domain:listenly.org")
BASE = "https://listenly.org/podcast-btb/"
N = 10


def choisir():
    """Methode du 17/10/2026 : d'abord la DEMANDE reelle (volume Google Ads du theme de la fiche),
    puis la note. Seules les fiches avec un volume > 0 sont retenues. Plafond 3 par podcast.
    Exclut les pages deja demandees (indexation_demandees.json et index_requests.json)."""
    scores = json.load(open(f"{PAGES}/data/moments_scores.json", encoding="utf-8"))
    scores = scores.get("scores", scores)
    try:
        demande = json.load(open(f"{PAGES}/data/demande_par_fiche.json", encoding="utf-8")).get("fiches", {})
    except (OSError, json.JSONDecodeError):
        demande = {}
    deja = set()
    for f in ("indexation_demandees.json", "index_requests.json"):
        try:
            d = json.load(open(f"{PAGES}/data/{f}", encoding="utf-8"))
            if isinstance(d, dict):
                deja.update(d.get("urls", []))
                for v in d.values():
                    if isinstance(v, list):
                        deja.update(x for x in v if isinstance(x, str))
                for h in d.get("historique", []):
                    deja.update(h.get("urls", []))
        except (OSError, json.JSONDecodeError):
            pass
    # 18/10/2026 : seuls les podcasts des niveaux ouverts (trafic_seo.json > niveaux_ouverts) sont proposes
    try:
        niv = json.load(open(f"{PAGES}/data/priorite_podcasts.json", encoding="utf-8")).get("niveaux", {})
        ouverts = set(json.load(open("automation/marketforge_engine/trafic_seo.json", encoding="utf-8")).get("niveaux_ouverts") or ["A"])
    except (OSError, json.JSONDecodeError):
        niv, ouverts = {}, {"A"}
    cands = []
    for key, v in scores.items():
        if not isinstance(v, dict) or not v.get("gate"):
            continue
        if niv.get(key.split("/", 1)[0], "C") not in ouverts:
            continue
        vol = (demande.get(key) or {}).get("volume", 0)
        if vol <= 0 or BASE + "m/" + key in deja:
            continue
        cands.append((-vol, -(v.get("score_final") or 0), key))
    cands.sort()
    out, par_podcast = [], {}
    for _, sc, k in cands:
        slug = k.split("/", 1)[0]
        if par_podcast.get(slug, 0) >= 3:
            continue
        par_podcast[slug] = par_podcast.get(slug, 0) + 1
        out.append((slug, k.split("/", 1)[1], -sc))
        if len(out) >= N:
            break
    return out


def token():
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    info = json.loads(os.environ["GSC_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    creds.refresh(Request())
    return creds.token


def inspecter(tok, url):
    r = requests.post("https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
                      headers={"Authorization": f"Bearer {tok}"},
                      json={"inspectionUrl": url, "siteUrl": SITE}, timeout=60)
    r.raise_for_status()
    s = r.json().get("inspectionResult", {}).get("indexStatusResult", {})
    return {"verdict": s.get("verdict"), "etat": s.get("coverageState"),
            "robots": s.get("robotsTxtState"), "indexation_bloquee": s.get("indexingState")}


def http(url):
    try:
        return requests.head(url, allow_redirects=True, timeout=30).status_code
    except requests.RequestException:
        return None


def main():
    items = []
    try:
        tok = token() if os.environ.get("GSC_SERVICE_ACCOUNT_JSON") else None
    except Exception:
        tok = None
    for slug, mid, score in choisir():
        url = BASE + "m/" + slug + "/" + mid
        item = {"url": url, "score_qualite": score, "http": http(url)}
        if tok:
            try:
                item.update(inspecter(tok, url))
            except Exception as e:
                item["inspection_erreur"] = str(e)[:120]
        # Pret = en ligne, pas bloquee par robots.txt ni par balise noindex, et pas encore indexee.
        item["pret_pour_demande"] = (item["http"] == 200 and item.get("verdict") != "PASS"
                                     and item.get("robots") != "DISALLOWED"
                                     and item.get("indexation_bloquee") not in ("BLOCKED_BY_META_TAG", "BLOCKED_BY_HTTP_HEADER"))
        items.append(item)
    out = {"date": datetime.date.today().isoformat(),
           "mode": "liste a traiter dans Claude + Chrome (demande d'indexation manuelle, validation par page)",
           "pretes": sum(1 for i in items if i["pret_pour_demande"]),
           "urls": items}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[indexation] {out['pretes']} pretes sur {len(items)}")


if __name__ == "__main__":
    main()

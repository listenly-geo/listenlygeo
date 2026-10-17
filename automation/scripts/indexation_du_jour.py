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
    """10 pages de MOMENTS validees par le systeme (porte d'entree gate=True), les plus fortes d'abord,
    en priorite celles deja ouvertes au sitemap. Exclut celles deja demandees (data/indexation_demandees.json)."""
    scores = json.load(open(f"{PAGES}/data/moments_scores.json", encoding="utf-8"))
    released = json.load(open(f"{PAGES}/data/moments_sitemap_state.json", encoding="utf-8")).get("released", {})
    try:
        deja = set(json.load(open(f"{PAGES}/data/indexation_demandees.json", encoding="utf-8")).get("urls", []))
    except (OSError, json.JSONDecodeError):
        deja = set()
    cands = []
    for key, v in scores.items():
        if not isinstance(v, dict) or not v.get("gate"):
            continue
        url = BASE + "m/" + key
        if url in deja:
            continue
        cands.append((0 if key in released else 1, -(v.get("score_final") or 0), key))
    cands.sort()
    # Plafond : 3 fiches maximum par podcast (regle du 16/10/2026)
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

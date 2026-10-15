#!/usr/bin/env python3
"""Chaque jour : choisit 10 fiches question a faire indexer, verifie chaque URL .org et son etat
dans la Search Console (API d'inspection, lecture seule), ecrit pages/podcast-btb/data/indexation_du_jour.json.
La demande d'indexation elle-meme se fait a la main (session Claude + Chrome, validation par page).
Secret : GSC_SERVICE_ACCOUNT_JSON. Ne bloque jamais le workflow : en cas d'erreur, la liste est ecrite quand meme."""
import os, json, datetime
import requests

PAGES = "pages/podcast-btb"
SRC = f"{PAGES}/data/gsc_index_status.json"
OUT = f"{PAGES}/data/indexation_du_jour.json"
SITE = os.environ.get("GSC_SITE", "sc-domain:listenly.org")
BASE = "https://listenly.org/podcast-btb/"
N = 10


def choisir():
    d = json.load(open(SRC, encoding="utf-8"))
    rows = [(u, v.get("impressions", 0), v.get("clicks", 0)) for u, v in d.get("impressions", {}).items()
            if u.startswith("questions/") and not u.endswith("/index.html") and v.get("impressions", 0) > 0]
    rows.sort(key=lambda r: (-r[2], -r[1]))
    return rows[:N]


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
    return {"verdict": s.get("verdict"), "etat": s.get("coverageState"), "indexable": s.get("robotsTxtState")}


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
    for u, imp, clics in choisir():
        url = BASE + u
        item = {"url": url, "impressions_90j": imp, "clics_90j": clics, "http": http(url)}
        if tok:
            try:
                item.update(inspecter(tok, url))
            except Exception as e:
                item["inspection_erreur"] = str(e)[:120]
        item["pret_pour_demande"] = item["http"] == 200 and item.get("verdict") == "PASS"
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

#!/usr/bin/env python3
"""Recupere les chiffres de la Search Console (listenly.fr) via l'API et les ecrit dans data/gsc/.
Secret requis : GSC_SERVICE_ACCOUNT_JSON (cle du compte de service). Propriete : GSC_SITE (defaut sc-domain:listenly.fr).
Sorties : data/gsc/pages.json (pages x clics/impressions/ctr/position), data/gsc/requetes.json (requetes),
data/gsc/pages_requetes.json (requete x page, pour les pages de moments), data/gsc/resume.json (totaux, date du jour).
Ne bloque jamais le moteur : en cas d'erreur, ecrit data/gsc/erreur.json et sort en code 0."""
import os, sys, json, datetime
import requests

SITE = os.environ.get("GSC_SITE", "sc-domain:listenly.fr")
OUT = "data/gsc"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
JOURS = int(os.environ.get("GSC_JOURS", "90"))


def token():
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    info = json.loads(os.environ["GSC_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    creds.refresh(Request())
    return creds.token


def query(tok, dims, start, end, filt=None, limit=25000):
    url = f"https://www.googleapis.com/webmasters/v3/sites/{requests.utils.quote(SITE, safe='')}/searchAnalytics/query"
    rows, offset = [], 0
    while True:
        body = {"startDate": start, "endDate": end, "dimensions": dims, "rowLimit": min(limit, 25000), "startRow": offset}
        if filt:
            body["dimensionFilterGroups"] = [{"filters": filt}]
        r = requests.post(url, headers={"Authorization": f"Bearer {tok}"}, json=body, timeout=60)
        r.raise_for_status()
        batch = r.json().get("rows", [])
        rows += batch
        if len(batch) < 25000 or len(rows) >= limit:
            return rows
        offset += 25000


def clean(rows, names):
    out = []
    for r in rows:
        d = dict(zip(names, r["keys"]))
        d.update(clics=r["clicks"], impressions=r["impressions"], ctr=round(r["ctr"], 4), position=round(r["position"], 1))
        out.append(d)
    return out


def save(name, data):
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def main():
    if not os.environ.get("GSC_SERVICE_ACCOUNT_JSON"):
        save("erreur", {"date": str(datetime.date.today()), "erreur": "secret GSC_SERVICE_ACCOUNT_JSON absent"})
        print("Secret absent : rien recupere")
        return
    try:
        tok = token()
        fin = datetime.date.today() - datetime.timedelta(days=2)   # les derniers jours ne sont pas encore complets
        debut = fin - datetime.timedelta(days=JOURS)
        s, e = str(debut), str(fin)
        pages = clean(query(tok, ["page"], s, e), ["page"])
        requetes = clean(query(tok, ["query"], s, e), ["requete"])
        moments = clean(query(tok, ["query", "page"], s, e,
                              [{"dimension": "page", "operator": "contains", "expression": "/podcast-btb/m/"}]), ["requete", "page"])
        save("pages", sorted(pages, key=lambda x: -x["impressions"]))
        save("requetes", sorted(requetes, key=lambda x: -x["impressions"]))
        save("pages_requetes_moments", sorted(moments, key=lambda x: -x["impressions"]))
        tot = lambda L, k: sum(x[k] for x in L)
        pm = [p for p in pages if "/podcast-btb/m/" in p["page"]]
        save("resume", {"date": str(datetime.date.today()), "periode": [s, e], "pages": len(pages),
                        "clics": tot(pages, "clics"), "impressions": tot(pages, "impressions"),
                        "pages_moments": len(pm), "clics_moments": tot(pm, "clics"), "impressions_moments": tot(pm, "impressions")})
        if os.path.exists(f"{OUT}/erreur.json"):
            os.remove(f"{OUT}/erreur.json")
        print(f"OK : {len(pages)} pages, {len(requetes)} requetes, {len(pm)} pages de moments")
    except Exception as ex:
        save("erreur", {"date": str(datetime.date.today()), "erreur": str(ex)[:500]})
        print("Erreur (non bloquante) :", str(ex)[:300])


if __name__ == "__main__":
    main()

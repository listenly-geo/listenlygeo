#!/usr/bin/env python3
"""Recupere les chiffres de la Search Console (listenly.fr puis listenly.org) via l'API et les ecrit dans data/gsc/.
Secret requis : GSC_SERVICE_ACCOUNT_JSON (cle du compte de service). Propriete : GSC_SITE (defaut sc-domain:listenly.fr).
Sorties : data/gsc/pages.json (pages x clics/impressions/ctr/position), data/gsc/requetes.json (requetes),
data/gsc/pages_requetes.json (requete x page, pour les pages de moments), data/gsc/resume.json (totaux, date du jour).
Ne bloque jamais le moteur : en cas d'erreur, ecrit data/gsc/erreur.json et sort en code 0."""
import os, sys, json, datetime, time
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


INSPECT_MAX = int(os.environ.get("GSC_INSPECT_MAX", "400"))   # quota Google : 2000 inspections/jour/propriete


def inspect_moments(tok):
    """Etat d'indexation, page par page, des pages de moments proposees dans le sitemap (data/moments_sitemap_state.json).
    Verifie d'abord les pages jamais inspectees, puis celles qui ne sont pas encore indexees (les indexees sont recontrolees rarement)."""
    st_path = "pages/podcast-btb/data/moments_sitemap_state.json"
    if not os.path.exists(st_path):
        return None
    released = json.load(open(st_path, encoding="utf-8")).get("released", {})
    prev_path = f"{OUT}/indexation_moments.json"
    prev = json.load(open(prev_path, encoding="utf-8")) if os.path.exists(prev_path) else {}
    today = str(datetime.date.today())

    def priorite(key):
        r = prev.get(key)
        if not r:
            return (0, "")
        if r.get("etat") != "indexee":
            return (1, r.get("controle", ""))
        return (2, r.get("controle", ""))

    todo = sorted(released, key=priorite)[:INSPECT_MAX]
    url = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
    ok = 0
    t0 = time.time()
    for key in todo:
        if time.time() - t0 > 420:   # budget de 7 min : on garde le resultat partiel, la suite est reprise demain
            break
        slug, mid = key.split("/", 1)
        page = f"https://{SITE.replace('sc-domain:', '')}/podcast-btb/m/{slug}/{mid}"   # meme hote que la propriete Search Console
        try:
            r = requests.post(url, headers={"Authorization": f"Bearer {tok}"},
                              json={"inspectionUrl": page, "siteUrl": SITE}, timeout=20)
            if r.status_code == 429:
                break   # quota atteint : on reprend demain
            r.raise_for_status()
            ix = r.json().get("inspectionResult", {}).get("indexStatusResult", {})
        except Exception as ex:
            prev[key] = {"page": page, "etat": "erreur", "detail": str(ex)[:120], "controle": today}
            continue
        cov = ix.get("coverageState", "")
        low = cov.lower()
        etat = ("indexee" if ("indexed" in low and "not indexed" not in low and "non index" not in low and "currently not" not in low)
                else "detectee_non_indexee" if "discovered" in low
                else "explorée_non_indexee" if "crawled" in low
                else "inconnue" if "unknown" in low
                else "noindex" if "noindex" in low or ix.get("indexingState") == "BLOCKED_BY_META_TAG"
                else "autre")
        prev[key] = {"page": page, "etat": etat, "couverture": cov, "verdict": ix.get("verdict", ""),
                     "derniere_exploration": ix.get("lastCrawlTime", ""), "canonique_google": ix.get("googleCanonical", ""),
                     "indexation": ix.get("indexingState", ""), "controle": today}
        ok += 1
        time.sleep(0.15)
    prev = {k: v for k, v in prev.items() if k in released}
    save("indexation_moments", prev)
    comptes = {}
    for v in prev.values():
        comptes[v["etat"]] = comptes.get(v["etat"], 0) + 1
    save("indexation_resume", {"date": today, "pages_proposees": len(released), "inspectees_ce_jour": ok, "par_etat": comptes})
    return comptes


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
        print(f"OK : {len(pages)} pages, {len(requetes)} requetes, {len(pm)} pages de moments")
        try:
            print("Indexation des pages de moments :", inspect_moments(tok))
        except Exception as ex:
            print("Inspection d'indexation (non bloquante) :", str(ex)[:300])
        if os.path.exists(f"{OUT}/erreur.json"):
            os.remove(f"{OUT}/erreur.json")
    except Exception as ex:
        save("erreur", {"date": str(datetime.date.today()), "erreur": str(ex)[:500]})
        print("Erreur (non bloquante) :", str(ex)[:300])


if __name__ == "__main__":
    main()

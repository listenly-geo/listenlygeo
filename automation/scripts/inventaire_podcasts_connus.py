#!/usr/bin/env python3
"""Inventaire en lecture seule des épisodes des podcasts connus (niveau A).
Lit les flux RSS (podcasts.json, champ rss_url) et compte les épisodes.
Ne crée aucune fiche, ne publie rien. Sortie : pages/podcast-btb/data/inventaire_connus.json
"""
import json, re, datetime, urllib.request, concurrent.futures as cf

LV = "pages/podcast-btb/data/priorite_podcasts.json"
POD = "pages/podcast-btb/data/podcasts.json"
OUT = "pages/podcast-btb/data/inventaire_connus.json"


def compter(url):
    req = urllib.request.Request(url, headers={"User-Agent": "listenly-inventaire/1.0"})
    data = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    return len(re.findall(r"<item[\s>]", data)) or len(re.findall(r"<entry[\s>]", data))


def main():
    niveaux = json.load(open(LV, encoding="utf-8"))["niveaux"]
    pods = {p["slug"]: p for p in json.load(open(POD, encoding="utf-8"))}
    cibles = [s for s, n in niveaux.items() if n == "A"]

    def un(slug):
        url = pods.get(slug, {}).get("rss_url", "")
        if not url:
            return {"slug": slug, "erreur": "pas de flux"}
        try:
            return {"slug": slug, "rss": url, "episodes": compter(url)}
        except Exception as e:
            return {"slug": slug, "rss": url, "erreur": str(e)[:120]}

    with cf.ThreadPoolExecutor(8) as ex:
        res = list(ex.map(un, cibles))
    ok = [r for r in res if "episodes" in r]
    out = {"date": str(datetime.date.today()), "podcasts_A": len(cibles),
           "flux_lus": len(ok), "episodes_total": sum(r["episodes"] for r in ok), "detail": res}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"A: {len(cibles)} podcasts, flux lus {len(ok)}, épisodes {out['episodes_total']}")


if __name__ == "__main__":
    main()

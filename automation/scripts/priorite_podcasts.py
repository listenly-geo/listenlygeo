#!/usr/bin/env python3
"""Niveau de priorite des podcasts (18/10/2026) : A, B ou C.

Deux signaux, on garde le meilleur des deux :
- classement manuel de notoriete (pages/podcast-btb/data/priorite_podcasts.json, champ "manuel") ;
- ce qui marche deja dans la Search Console (data/gsc/pages.json, lu chaque jour par gsc-daily) :
  un clic sur une page du podcast (hub ou moment) donne A ; 2 impressions ou plus donnent au moins B.
Le resultat va dans "niveaux" ; le champ "manuel" n'est jamais ecrase.
"""
import json, os, glob

PAGES = "pages/podcast-btb"
RANG = {"A": 3, "B": 2, "C": 1}


def hub_vers_slug():
    """Chaque fiche N1 (hub) du dossier moments pointe vers son podcast."""
    out = {}
    for f in glob.glob(f"{PAGES}/data/moments/*.json"):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        slug = d.get("slug") or os.path.basename(f)[:-5]
        hub = (d.get("hub") or "").strip()
        if hub:
            out[hub.split("/podcast-btb/", 1)[-1]] = slug
    return out


def signaux_gsc():
    """{slug: (clics, impressions)} depuis les pages de la Search Console."""
    try:
        rows = json.load(open("data/gsc/pages.json", encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    hubs = hub_vers_slug()
    out = {}
    for r in rows:
        url = r.get("page", "")
        slug = None
        if "/podcast-btb/m/" in url:
            slug = url.split("/podcast-btb/m/", 1)[1].split("/", 1)[0]
        elif "/podcast-btb/" in url:
            slug = hubs.get(url.split("/podcast-btb/", 1)[1])
        if not slug:
            continue
        c, i = out.get(slug, (0, 0))
        out[slug] = (c + int(r.get("clics", 0)), i + int(r.get("impressions", 0)))
    return out


def main():
    p = f"{PAGES}/data/priorite_podcasts.json"
    d = json.load(open(p, encoding="utf-8"))
    manuel = d.get("manuel") or dict(d.get("niveaux", {}))   # premiere fois : le classement manuel devient la base
    gsc = signaux_gsc()
    niveaux = {}
    for slug in set(manuel) | set(gsc):
        niv_manuel = manuel.get(slug, "C")
        clics, imp = gsc.get(slug, (0, 0))
        niv_gsc = "A" if clics >= 1 else ("B" if imp >= 2 else "C")
        niveaux[slug] = max(niv_manuel, niv_gsc, key=lambda n: RANG[n])
    d.update({"manuel": manuel, "niveaux": niveaux, "signaux_gsc": {s: {"clics": c, "impressions": i} for s, (c, i) in gsc.items() if i or c}})
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("niveaux:", {n: sum(1 for v in niveaux.values() if v == n) for n in "ABC"})


if __name__ == "__main__":
    main()

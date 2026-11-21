#!/usr/bin/env python3
"""
ADRESSES PAR QUESTION (21/11/2026, decision d'Etienne) : l'adresse publique d'une fiche moment contient la question
(titre valide par le filtre « sens dans la recherche », sans la marque), pour etre lue par Google et les IA :

    https://listenly.org/podcast-btb/m/<podcast>/<question-en-mots>      (nouvelle adresse)
    https://listenly.org/podcast-btb/m/<podcast>/<code-10-caracteres>    (ancienne adresse : redirigee 301 par m.php)

La CLE INTERNE reste « <podcast>/<code> » partout (titres_seo, scores, sitemap, journaux) : seule l'adresse change.
Table : pages/podcast-btb/data/slugs_moments.json  {"slugs": {"<podcast>/<code>": "<question-en-mots>"}}
Un slug attribue ne change JAMAIS (une adresse deja envoyee a Google reste stable).
Migration par lots : une fiche n'a une nouvelle adresse que si elle figure dans la table (assign / migrer).

Usage : python automation/scripts/moment_urls.py migrer 20   -> attribue un slug a 20 fiches titrees pas encore migrees
"""
import os, re, sys, json, unicodedata

PAGES = "pages/podcast-btb"
PATH = f"{PAGES}/data/slugs_moments.json"
BASE = "https://listenly.org/podcast-btb/m"
MAX_LEN = 70
MIN_MOTS = 3          # moins de 3 mots : pas de slug (reste en ancienne adresse)
_data = None


def _load():
    global _data
    if _data is None:
        try:
            _data = json.load(open(PATH, encoding="utf-8"))
        except (OSError, ValueError):
            _data = {}
        _data.setdefault("slugs", {})
    return _data


def save():
    if _data is not None:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        json.dump(_data, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)


def slugify(titre):
    """Titre -> slug : sans marque finale (« | Listenly », « — Nom du podcast »), ascii, minuscules, mots separes par '-'.
    Coupe a MAX_LEN sur une frontiere de mot. None si moins de MIN_MOTS mots."""
    t = str(titre or "").strip()
    t = re.sub(r"\s+[|—–]\s+[^|—–]+$", "", t)          # marque finale
    t = re.sub(r"['’`]", "", t)                           # « car's » -> « cars » (pas de tiret parasite)
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
    if len(t) > MAX_LEN:
        t = t[:MAX_LEN].rsplit("-", 1)[0]
    return t if len([m for m in t.split("-") if m]) >= MIN_MOTS else None


def get(key):
    return _load()["slugs"].get(key)


def assign(key, titre):
    """Slug de la fiche (cle podcast/code) : celui deja attribue, sinon un nouveau tire du titre. None si impossible."""
    d = _load()["slugs"]
    if key in d:
        return d[key]
    s = slugify(titre)
    if not s:
        return None
    podcast = key.split("/", 1)[0]
    pris = {v for k, v in d.items() if k.split("/", 1)[0] == podcast}
    if s in pris:   # deux questions voisines dans le meme podcast : on ajoute le debut du code
        s = f"{s}-{key.split('/', 1)[1][:4]}"
        if s in pris:
            return None
    d[key] = s
    return s


def url(key):
    """Adresse publique complete d'une fiche (cle podcast/code) : par question si migree, sinon ancienne adresse."""
    s = get(key)
    podcast, mid = key.split("/", 1)
    return f"{BASE}/{podcast}/{s or mid}"


def path_to_key(path):
    """'<podcast>/<code ou slug>' (ou URL complete /podcast-btb/m/...) -> cle 'podcast/code'. None si inconnue."""
    p = str(path or "")
    if "/podcast-btb/m/" in p:
        p = p.split("/podcast-btb/m/", 1)[1]
    p = p.strip("/").split("?")[0].split("#")[0]
    parts = p.split("/")
    if len(parts) < 2:
        return None
    podcast, last = parts[0], parts[1]
    if re.fullmatch(r"[a-f0-9]{10}", last):
        return f"{podcast}/{last}"
    for k, s in _load()["slugs"].items():
        if s == last and k.split("/", 1)[0] == podcast:
            return k
    return None


def migrer(n, exclure=()):
    """Attribue un slug a N fiches titrees pas encore migrees (lot). Renvoie la liste des cles migrees."""
    try:
        titres = json.load(open(f"{PAGES}/data/titres_seo.json", encoding="utf-8"))
        titres = titres.get("titres", titres)
    except (OSError, ValueError):
        return []
    faits = []
    for key, titre in sorted(titres.items()):
        if len(faits) >= n:
            break
        if key in _load()["slugs"] or key in exclure:
            continue
        if assign(key, titre):
            faits.append(key)
    save()
    return faits


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "migrer":
        for k in migrer(int(sys.argv[2])):
            print(k, "->", get(k))
    else:
        print(__doc__)

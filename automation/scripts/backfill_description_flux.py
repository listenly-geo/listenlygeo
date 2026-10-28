#!/usr/bin/env python3
"""
Recupere la description de chaque podcast depuis son flux RSS (gratuit, aucun appel API) et
l'enregistre dans podcasts.json (champ « description_flux »). Puis remplace, sur les fiches Hub
existantes, la phrase generique « X is a podcast hosted by Y » par cette description, uniquement
quand la fiche porte encore la phrase generique (une description ecrite a la main n'est jamais touchee).

Usage : python automation/scripts/backfill_description_flux.py [--limit N]
"""

import os, re, sys, json, html, time, argparse
import urllib.request, urllib.error
import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PAGES = os.path.join(ROOT, "pages", "podcast-btb")
DATA = os.path.join(PAGES, "data", "podcasts.json")
ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
MAX_MOTS = 120
GENERIQUE = re.compile(r" is an? [^.]* ?podcast hosted by [^.]*\.$|^.* is a podcast hosted by [^.]*\.$")


def nettoyer(texte):
    """Texte brut d'un flux : sans balises HTML, espaces reduits, limite de mots."""
    txt = html.unescape(re.sub(r"<[^>]+>", " ", texte or ""))
    txt = re.sub(r"\s+", " ", txt).strip()
    txt = re.sub(r"\s+([.,;:!?])", r"\1", txt)
    mots = txt.split(" ")
    if len(mots) <= MAX_MOTS:
        return txt
    court = " ".join(mots[:MAX_MOTS])
    fin = max(court.rfind(". "), court.rfind("! "), court.rfind("? "))
    return court[: fin + 1] if fin > len(court) * 0.6 else court + "…"


def lire_description(url):
    """Description du flux (channel/description, sinon itunes:summary). '' si indisponible."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (listenly-bot)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            root = ET.fromstring(r.read())
    except (urllib.error.URLError, ET.ParseError, OSError, ValueError):
        return ""
    chaine = root.find("channel")
    if chaine is None:
        return ""
    el = chaine.find("description")
    if el is None or not (el.text or "").strip():
        el = chaine.find(ITUNES + "summary")
    return nettoyer(el.text if el is not None else "")


def mettre_a_jour_fiche(slug, description):
    """Remplace le paragraphe generique de la fiche Hub existante. Renvoie True si modifiee."""
    chemin = os.path.join(PAGES, f"{slug}-podcast.html")
    if not os.path.exists(chemin):
        return False
    page = open(chemin, encoding="utf-8").read()
    m = re.search(r'(<section class="about">.*?<p class="about-text">)(.*?)(</p>)', page, re.S)
    if not m or not GENERIQUE.search(html.unescape(m.group(2)).strip()):
        return False
    nouveau = page[: m.start(2)] + html.escape(description, quote=False) + page[m.end(2):]
    open(chemin, "w", encoding="utf-8").write(nouveau)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="nombre max de flux lus (0 = tous)")
    args = ap.parse_args()
    fiches = json.load(open(DATA, encoding="utf-8"))
    lus = ajoutees = mises_a_jour = 0
    for p in fiches:
        if args.limit and lus >= args.limit:
            break
        if not isinstance(p, dict) or not p.get("rss_url") or p.get("description_flux"):
            continue
        lus += 1
        description = lire_description(p["rss_url"])
        time.sleep(0.2)
        if not description:
            continue
        p["description_flux"] = description
        ajoutees += 1
        if not p.get("punchline") and mettre_a_jour_fiche(p["slug"], description):
            mises_a_jour += 1
    if ajoutees:
        with open(DATA, "w", encoding="utf-8") as f:
            json.dump(fiches, f, ensure_ascii=False, indent=2)
            f.write("\n")
    print(f"[description_flux] lus={lus} descriptions={ajoutees} fiches_hub_mises_a_jour={mises_a_jour}")


if __name__ == "__main__":
    sys.exit(main())

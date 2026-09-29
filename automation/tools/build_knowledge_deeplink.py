#!/usr/bin/env python3
"""
Page « concept » Listenly (Knowledge Search) + lien profond depuis les hubs N1 (29/09/2026).

Part de la page de recherche d'Etienne (automation/tools/knowledge-search-source.html : hero, recherche,
compteurs, lecteur en barre avec +/-10 s) et lui ajoute UNE ligne (<script src="/podcast-btb/deeplink.js">) : ?p=<podcast>&m=<moment>
ouvre la reponse (vignette du podcast + carte) et lance le lecteur au bon moment. La logique vit dans
pages/podcast-btb/deeplink.js, deploye par le moteur : la page d'accueil n'a plus a etre recopiee.

Sorties :
  pages/podcast-btb/ecouter.html                    : copie deployee par le moteur (noindex) — cible des boutons des hubs
  automation/tools/knowledge-search-deeplink.html   : meme page, indexable (canonical /knowledge-search),
                                                      a coller sur listenly.fr/knowledge-search
Usage : python automation/tools/build_knowledge_deeplink.py
"""
import re, os

SRC = "automation/tools/knowledge-search-source.html"
OUT_ECOUTER = "pages/podcast-btb/ecouter.html"
OUT_CONCEPT = "automation/tools/knowledge-search-deeplink.html"
OUT_HOME = "automation/tools/listenly-homepage-deeplink.html"   # meme page, canonical = page d'accueil https://listenly.fr/

SCRIPT_TAG = '  <script src="/podcast-btb/deeplink.js"></script>\n'   # logique + vignette : pages/podcast-btb/deeplink.js


def build():
    with open(SRC, encoding="utf-8") as f:
        src = f.read()
    assert "function playAnswer(" in src and "function renderResults(" in src, "page source inattendue"
    marker = "</script>\n</body>"
    assert marker in src, "fin de script introuvable"
    concept = src.replace(marker, "</script>\n" + SCRIPT_TAG + "</body>", 1)

    ecouter = concept
    ecouter = re.sub(r'<link rel="canonical"[^>]*>\n', '', ecouter)
    ecouter = re.sub(r'<meta property="og:url"[^>]*>\n', '', ecouter)
    ecouter = ecouter.replace('<meta charset="UTF-8">', '<meta charset="UTF-8">\n<meta name="robots" content="noindex, follow">', 1)
    ecouter = ecouter.replace("<title>Listenly — Knowledge Search: Find the Exact Podcast Answer to Any Question</title>",
                              "<title>Listen to the answer — Listenly</title>", 1)

    home = concept.replace('<link rel="canonical" href="https://listenly.fr/knowledge-search">',
                           '<link rel="canonical" href="https://listenly.fr/">')
    home = home.replace('<meta property="og:url" content="https://listenly.fr/knowledge-search">',
                        '<meta property="og:url" content="https://listenly.fr/">')
    assert 'href="https://listenly.fr/">' in home and "knowledge-search" not in re.sub(r"<!--.*?-->", "", home)
    with open(OUT_HOME, "w", encoding="utf-8") as f:
        f.write(home)
    with open(OUT_CONCEPT, "w", encoding="utf-8") as f:
        f.write(concept)
    with open(OUT_ECOUTER, "w", encoding="utf-8") as f:
        f.write(ecouter)
    print(f"[deeplink] {OUT_ECOUTER} ({len(ecouter)} o), {OUT_CONCEPT} ({len(concept)} o)")


if __name__ == "__main__":
    build()

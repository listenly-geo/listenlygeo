#!/usr/bin/env python3
"""
Regenere uniquement dashboard.html (+ sitemap/llms/historique par coherence) sans
toucher au reste. Utilise apres N1 pour qu'un podcast fraichement cree apparaisse
immediatement dans le dashboard, meme avant que son premier N2 n'ait tourne.

Volontairement un script separe plutot qu'un appel ajoute dans generate_podcast_btb.py
lui-meme : ce dernier est aussi utilise par ~120 anciens workflows episode, et y
rajouter build_dashboard() recreerait la collision massive deja corrigee (cf. fix
"generate_podcast_btb.py ne doit plus regenerer dashboard.html" plus haut dans
l'historique). Ce script n'est appele QUE par les workflows du moteur trafic.
"""

import os
import importlib.util

os.environ.setdefault("ANTHROPIC_API_KEY", "unused")
os.environ.setdefault("PODCAST_RAW_INFO", "unused")
os.environ.setdefault("PODCAST_URL", "unused")
os.environ.setdefault("CONTACT_URL", "unused")
os.environ.setdefault("LISTENLY_URL", "unused")

spec = importlib.util.spec_from_file_location(
    "generate_podcast_btb",
    os.path.join(os.path.dirname(__file__), "generate_podcast_btb.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

print("[rebuild-dashboard] Regeneration dashboard.html...")
mod.build_dashboard()
print("[rebuild-dashboard] Termine.")

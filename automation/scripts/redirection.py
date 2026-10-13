#!/usr/bin/env python3
"""Destination du bouton « Accéder au podcast » des fiches N1 (modèle du 13/10/2026).
Usage :
  python automation/scripts/redirection.py set <slug> <url>   # ajoute ou modifie
  python automation/scripts/redirection.py del <slug>         # supprime (retour au lien Listenly)
  python automation/scripts/redirection.py list
Le fichier automation/marketforge_engine/redirections.json est lu à chaque génération de fiche N1."""
import json, sys, os
P = os.path.join(os.path.dirname(__file__), "..", "marketforge_engine", "redirections.json")
d = json.load(open(P, encoding="utf-8")) if os.path.exists(P) else {}
cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
if cmd == "set":
    slug, url = sys.argv[2], sys.argv[3]
    if not url.startswith("https://"):
        sys.exit("URL refusée : elle doit commencer par https://")
    d[slug] = url
elif cmd == "del":
    d.pop(sys.argv[2], None)
elif cmd != "list":
    sys.exit(__doc__)
json.dump(d, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k, v in sorted(d.items()):
    print(f"{k} -> {v}")
print(f"({len(d)} destination(s))")

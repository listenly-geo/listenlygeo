#!/usr/bin/env python3
"""Liste les fiches moment du réservoir (gate = vrai, niveau ouvert) qui n'ont pas encore de titre SEO.
Sortie : une ligne par fiche « slug/id | nom du podcast | question », classée par note.
Utilisé par la tâche quotidienne pour écrire des titres de remplacement quand la liste du jour est trop courte."""
import json, importlib.util, os

spec = importlib.util.spec_from_file_location("ind", "automation/scripts/indexation_du_jour.py")
ind = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ind)

cands, titres = ind.choisir()
for slug, mid, _score in cands:
    if titres.get(slug + "/" + mid):
        continue
    try:
        d = json.load(open(f"pages/podcast-btb/data/moments/{slug}.json", encoding="utf-8"))
        q = d["entries"][mid]["q"]
        nom = d.get("podcast") or slug
    except (OSError, KeyError, json.JSONDecodeError):
        continue
    print(f"{slug}/{mid} | {nom} | {q}")

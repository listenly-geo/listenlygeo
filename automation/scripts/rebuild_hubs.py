#!/usr/bin/env python3
"""
Regenere le bloc hub-index de toutes les fiches podcast N1 a partir des registres de questions
(pages/podcast-btb/questions/<slug>/_qa_registry.json). Aucun appel API : n'utilise que les
questions, reponses courtes et moments deja stockes. Voir hub_index.py.

Usage : python automation/scripts/rebuild_hubs.py
"""

import os, sys, json

sys.path.insert(0, os.path.dirname(__file__))
import hub_index  # noqa: E402

PAGES_DIR = hub_index.PAGES_DIR


def main():
    with open(f"{PAGES_DIR}/data/podcasts.json", encoding="utf-8") as f:
        records = json.load(f)
    changed = skipped = 0
    for podcast in records:
        reg_path = f"{PAGES_DIR}/questions/{podcast['slug']}/_qa_registry.json"
        if not os.path.exists(reg_path):
            continue
        with open(reg_path, encoding="utf-8") as f:
            published = json.load(f).get("published", [])
        n1_path = f"{PAGES_DIR}/{podcast['slug']}-podcast.html"
        if hub_index.apply_hub_index(n1_path, podcast, published):
            changed += 1
        else:
            skipped += 1
    print(f"[rebuild-hubs] {changed} hub(s) mis a jour, {skipped} inchange(s).")


if __name__ == "__main__":
    main()

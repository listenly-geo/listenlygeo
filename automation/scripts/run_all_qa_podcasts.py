#!/usr/bin/env python3
"""
Traite TOUS les podcasts du moteur trafic en une seule execution — au lieu d'un
workflow programme par podcast (qui s'est revele peu fiable : 115 workflows
`schedule:` dans ce depot font que GitHub Actions ne declenche quasiment plus
aucun cron correctement, cf. diagnostic compare avec listenly-geo/moteur-audiobook
qui n'a qu'1 seul workflow programme et fonctionne parfaitement).

Ce script boucle sur chaque podcast onboarde (dossier pages/podcast-btb/questions/<slug>/
avec un _qa_registry.json) et, pour ceux qui n'ont pas encore publie de fiche
AUJOURD'HUI, lance generate_qa_fiches_btb.py pour ce podcast (1 fiche, meme
logique de stock/mining qu'avant — rien ne change cote generation, seul le
declenchement change).

Isolation : chaque podcast tourne dans un sous-processus separe — un echec sur
l'un n'empeche pas les autres de continuer.
"""

import os, sys, json, subprocess, datetime

QUESTIONS_ROOT = "pages/podcast-btb/questions"

def log(msg):
    print(f"[run-all-qa] {msg}", flush=True)

def already_published_today(slug):
    reg_path = f"{QUESTIONS_ROOT}/{slug}/_qa_registry.json"
    if not os.path.exists(reg_path):
        return False
    try:
        reg = json.load(open(reg_path, encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    today = datetime.date.today().isoformat()
    return any(p.get("added_date") == today for p in reg.get("published", []))

def main():
    if not os.path.isdir(QUESTIONS_ROOT):
        log("Aucun podcast onboarde — rien a faire.")
        return

    slugs = sorted(
        s for s in os.listdir(QUESTIONS_ROOT)
        if os.path.exists(f"{QUESTIONS_ROOT}/{s}/_qa_registry.json")
    )
    log(f"{len(slugs)} podcast(s) onboarde(s) : {', '.join(slugs)}")

    done, skipped, failed = [], [], []
    for slug in slugs:
        if already_published_today(slug):
            skipped.append(slug)
            continue

        log(f"--- {slug} : generation d'1 fiche ---")
        env = dict(os.environ)
        env["PODCAST_SLUG"] = slug
        result = subprocess.run(
            [sys.executable, "automation/scripts/generate_qa_fiches_btb.py"],
            env=env,
        )
        if result.returncode == 0:
            done.append(slug)
        else:
            failed.append(slug)
            log(f"ECHEC sur {slug} (code {result.returncode}) — passage au suivant.")

    log("")
    log(f"Termine : {len(done)} fiche(s) generee(s), {len(skipped)} deja fait(s) aujourd'hui, {len(failed)} echec(s).")
    if done:
        log(f"  Generes : {', '.join(done)}")
    if failed:
        log(f"  Echecs : {', '.join(failed)}")

if __name__ == "__main__":
    main()

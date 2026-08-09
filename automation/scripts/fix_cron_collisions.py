#!/usr/bin/env python3
"""
Detecte et corrige les collisions de cron entre les workflows du moteur trafic
(.github/workflows/podcast-btb-qa-<slug>.yml).

Contrairement au generateur HTML (aveugle, base sur un hash sans connaissance des
podcasts crees entre-temps), ce script a une vue COMPLETE et A JOUR de tous les
workflows reellement presents dans le depot au moment ou il tourne — il peut donc
garantir l'absence de collision, pas seulement la reduire statistiquement.

Usage : python automation/scripts/fix_cron_collisions.py
Sans argument : detecte et corrige. Avec --check-only : detecte et affiche seulement
(code de sortie 1 si collision trouvee), ne modifie rien.
"""

import os, re, sys, hashlib

WF_DIR = ".github/workflows"
PREFIX = "podcast-btb-qa-"
CRON_RE = re.compile(r"cron:\s*'(\d+)\s+(\d+)\s+\*\s+\*\s+\*'")

def log(msg):
    print(f"[fix-cron-collisions] {msg}", flush=True)

def scan():
    """Retourne {(hour, minute): [slugs]} pour tous les workflows du moteur trafic."""
    by_slot = {}
    slugs_files = {}
    if not os.path.isdir(WF_DIR):
        return by_slot, slugs_files
    for fname in sorted(os.listdir(WF_DIR)):
        if not (fname.startswith(PREFIX) and fname.endswith(".yml")) or fname == f"{PREFIX}generic.yml":
            continue
        slug = fname[len(PREFIX):-len(".yml")]
        path = os.path.join(WF_DIR, fname)
        content = open(path, encoding="utf-8").read()
        m = CRON_RE.search(content)
        if not m:
            continue
        minute, hour = int(m.group(1)), int(m.group(2))
        by_slot.setdefault((hour, minute), []).append(slug)
        slugs_files[slug] = path
    return by_slot, slugs_files

def deterministic_slot(seed):
    """Meme logique que le generateur (hash -> minute du jour), pour rester previsible."""
    h = int(hashlib.md5((seed + "-qa-v2").encode("utf-8")).hexdigest(), 16)
    total_minutes = h % 1440
    return total_minutes // 60, total_minutes % 60

def find_free_slot(seed, taken):
    """Part du creneau deterministe puis avance minute par minute jusqu'a un creneau libre."""
    hour, minute = deterministic_slot(seed)
    start_total = hour * 60 + minute
    for offset in range(1440):
        total = (start_total + offset) % 1440
        slot = (total // 60, total % 60)
        if slot not in taken:
            return slot
    return (hour, minute)  # 1440 podcasts sur un meme jour : jamais en pratique

def main():
    check_only = "--check-only" in sys.argv
    by_slot, slugs_files = scan()

    collisions = {slot: slugs for slot, slugs in by_slot.items() if len(slugs) > 1}
    if not collisions:
        log(f"Aucune collision — {len(slugs_files)} podcast(s) verifie(s), tous sur un creneau distinct.")
        return

    log(f"{len(collisions)} collision(s) trouvee(s) parmi {len(slugs_files)} podcast(s) :")
    for slot, slugs in collisions.items():
        log(f"  {slot[0]:02d}h{slot[1]:02d} UTC : {', '.join(slugs)}")

    if check_only:
        sys.exit(1)

    taken = set(by_slot.keys())
    fixed = 0
    for slot, slugs in collisions.items():
        # Garde le premier (ordre alphabetique) sur son creneau actuel, reassigne les suivants
        for slug in slugs[1:]:
            new_hour, new_minute = find_free_slot(slug, taken)
            taken.add((new_hour, new_minute))
            taken.discard(slot)  # libere l'ancien creneau pour ce slug precis si plus personne dessus
            by_slot[slot].remove(slug)

            path = slugs_files[slug]
            content = open(path, encoding="utf-8").read()
            new_content = CRON_RE.sub(f"cron: '{new_minute} {new_hour} * * *'", content, count=1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            log(f"  -> {slug} reassigne a {new_hour:02d}h{new_minute:02d} UTC")
            fixed += 1

    log(f"{fixed} workflow(s) corrige(s). Pense a committer + pousser ces changements.")

if __name__ == "__main__":
    main()

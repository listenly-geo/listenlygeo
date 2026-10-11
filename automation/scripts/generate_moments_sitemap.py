#!/usr/bin/env python3
"""
Sitemap des pages moment (11/10/2026) : pages/podcast-btb/sitemap-moments.xml

Chaque moment de data/moments/<podcast>.json a une page /podcast-btb/m/<podcast>/<id> (rendue par m.php).
On les OUVRE A GOOGLE PROGRESSIVEMENT : au plus MOMENTS_PAR_JOUR (defaut 30) nouvelles adresses par jour,
repartie entre les podcasts. Une adresse ouverte reste dans le sitemap (jamais de retrait automatique).
Etat : pages/podcast-btb/data/moments_sitemap_state.json  {"released": {"<podcast>/<id>": "AAAA-MM-JJ"}}

Un moment n'est eligible que s'il a une vraie reponse ecrite, un horaire, le nom de l'invite et l'audio
(sinon la page est en noindex cote m.php et n'entre jamais au sitemap).

Usage : python automation/scripts/generate_moments_sitemap.py
Variables : MOMENTS_PAR_JOUR (defaut 30)
"""
import os, json, glob, datetime

PAGES_DIR = "pages/podcast-btb"
MOMENTS_DIR = f"{PAGES_DIR}/data/moments"
STATE_FILE = f"{PAGES_DIR}/data/moments_sitemap_state.json"
OUT = f"{PAGES_DIR}/sitemap-moments.xml"
BASE = "https://listenly.fr/podcast-btb/m"
MIN_ANSWER_CHARS = 80


def eligible(e):
    return (isinstance(e, dict) and len((e.get("a") or "").strip()) >= MIN_ANSWER_CHARS
            and int(e.get("t") or 0) > 0 and (e.get("x") or "").strip()
            and (e.get("u") or "").startswith("http") and (e.get("q") or "").strip())


def main():
    cap = int(os.environ.get("MOMENTS_PAR_JOUR", "30"))
    today = datetime.date.today().isoformat()
    try:
        state = json.load(open(STATE_FILE, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    released = state.setdefault("released", {})
    already_today = sum(1 for d in released.values() if d == today)
    quota = max(cap - already_today, 0)

    queues = {}
    for f in sorted(glob.glob(f"{MOMENTS_DIR}/*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        slug = d.get("slug") or os.path.basename(f)[:-5]
        ids = sorted(i for i, e in (d.get("entries") or {}).items()
                     if eligible(e) and f"{slug}/{i}" not in released)
        if ids:
            queues[slug] = ids

    added = 0
    while added < quota and queues:   # un moment par podcast a tour de role
        for slug in list(queues):
            if added >= quota:
                break
            released[f"{slug}/{queues[slug].pop(0)}"] = today
            added += 1
            if not queues[slug]:
                del queues[slug]

    entries = "\n".join(
        f"  <url>\n    <loc>{BASE}/{key}</loc>\n    <lastmod>{day}</lastmod>\n    <priority>0.8</priority>\n  </url>"
        for key, day in sorted(released.items())
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + entries + "\n</urlset>\n")
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(xml)
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=0, sort_keys=True)
    left = sum(len(v) for v in queues.values())
    print(f"[moments-sitemap] +{added} aujourd'hui (plafond {cap}) | total ouvert a Google : {len(released)} | restant en attente : {left}")


if __name__ == "__main__":
    main()

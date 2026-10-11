#!/usr/bin/env python3
"""
Sitemap des pages moment (11/10/2026) : pages/podcast-btb/sitemap-moments.xml

Chaque moment de data/moments/<podcast>.json a une page /podcast-btb/m/<podcast>/<id> (rendue par m.php).
On les OUVRE A GOOGLE PROGRESSIVEMENT : au plus MOMENTS_PAR_JOUR (defaut 30) nouvelles adresses par jour,
repartie entre les podcasts. Une adresse ouverte reste dans le sitemap (jamais de retrait automatique).
Etat : pages/podcast-btb/data/moments_sitemap_state.json  {"released": {"<podcast>/<id>": "AAAA-MM-JJ"}}

Un moment n'est eligible que si sa page est assez fournie (meme regle que pages/podcast-btb/m.php, a garder
identique) : reponse >= 25 mots, score de richesse >= 90 (mots de la reponse + chiffres + citation + 8 par autre
reponse du meme episode, 4 max), horaire, nom de l'invite, audio. Sinon la page est en noindex et n'entre pas au sitemap.
Un moment devenu non eligible est retire du sitemap (jamais d'adresse fine envoyee a Google).

Usage : python automation/scripts/generate_moments_sitemap.py
Variables : MOMENTS_PAR_JOUR (defaut 30)
"""
import os, json, glob, datetime

PAGES_DIR = "pages/podcast-btb"
MOMENTS_DIR = f"{PAGES_DIR}/data/moments"
STATE_FILE = f"{PAGES_DIR}/data/moments_sitemap_state.json"
OUT = f"{PAGES_DIR}/sitemap-moments.xml"
BASE = "https://listenly.fr/podcast-btb/m"


def wc(text):
    return len(str(text or "").split())


def answer_text(e):
    paras = [str(x).strip() for x in (e.get("f") or []) if str(x).strip()]
    if not paras and (e.get("a") or "").strip():
        paras = [e["a"].strip()]
    return " ".join(paras)


def eligible_ids(entries):
    """ids des moments dont la page est assez fournie (regle identique a m.php)."""
    by_ep = {}
    for i, e in entries.items():
        if (isinstance(e, dict) and int(e.get("t") or 0) > 0 and len((e.get("a") or "").strip()) >= 80
                and (e.get("q") or "").strip()):
            by_ep.setdefault(e.get("e") or "", []).append(i)
    ok = set()
    for i, e in entries.items():
        if not isinstance(e, dict):
            continue
        ans = answer_text(e)
        related = len([j for j in by_ep.get(e.get("e") or "", []) if j != i])
        stats = " ".join(str(x).strip() for x in (e.get("ks") or []) if str(x).strip())
        score = wc(ans) + wc(stats) + wc(e.get("rq")) + 8 * min(related, 4)
        if (wc(ans) >= 25 and score >= 90 and int(e.get("t") or 0) > 0 and (e.get("x") or "").strip()
                and (e.get("u") or "").startswith("http") and (e.get("q") or "").strip()):
            ok.add(i)
    return ok


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
        good = eligible_ids(d.get("entries") or {})
        for key in [k for k in released if k.startswith(slug + "/") and k.split("/", 1)[1] not in good]:
            del released[key]            # page devenue trop fine : retiree du sitemap
        ids = sorted(i for i in good if f"{slug}/{i}" not in released)
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

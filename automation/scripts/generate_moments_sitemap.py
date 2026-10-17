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
import os, re, json, glob, datetime

PAGES_DIR = "pages/podcast-btb"
MOMENTS_DIR = f"{PAGES_DIR}/data/moments"
STATE_FILE = f"{PAGES_DIR}/data/moments_sitemap_state.json"
SCORES_FILE = f"{PAGES_DIR}/data/moments_scores.json"
OUT = f"{PAGES_DIR}/sitemap-moments.xml"
BASE = "https://listenly.org/podcast-btb/m"


def wc(text):
    return len(str(text or "").split())


def answer_text(e):
    paras = [str(x).strip() for x in (e.get("f") or []) if str(x).strip()]
    if not paras and (e.get("a") or "").strip():
        paras = [e["a"].strip()]
    return " ".join(paras)


def eligible_ids(entries):
    """ids des moments dont la page est assez fournie (regle identique a m.php)."""
    return set(eligible_scores(entries))


def eligible_scores(entries):
    """{id: score de richesse} des moments eligibles (meme regle que m.php)."""
    by_ep = {}
    for i, e in entries.items():
        if (isinstance(e, dict) and int(e.get("t") or 0) > 0 and len((e.get("a") or "").strip()) >= 80
                and (e.get("q") or "").strip()):
            by_ep.setdefault(e.get("e") or "", []).append(i)
    ok = {}
    for i, e in entries.items():
        if not isinstance(e, dict):
            continue
        ans = answer_text(e)
        related = len([j for j in by_ep.get(e.get("e") or "", []) if j != i])
        stats = " ".join(str(x).strip() for x in (e.get("ks") or []) if str(x).strip())
        score = wc(ans) + wc(stats) + wc(e.get("rq")) + 8 * min(related, 4)
        if (wc(ans) >= 25 and score >= 90 and int(e.get("t") or 0) > 0 and (e.get("x") or "").strip()
                and (e.get("u") or "").startswith("http") and (e.get("q") or "").strip()):
            ok[i] = score
    return ok


def load_cfg():
    try:
        return json.load(open("automation/marketforge_engine/trafic_seo.json", encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def podcast_impressions():
    """Impressions Google par podcast (hub + anciennes fiches), pour servir d'abord les podcasts deja visibles."""
    out = {}
    for path in ("data/gsc/pages.json",):
        try:
            rows = json.load(open(path, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for r in rows:
            u = r.get("page", "")
            m = re.search(r"/podcast-btb/questions/([^/]+)/", u) or re.search(r"/podcast-btb/([^/]+)-podcast\.html", u)
            if m:
                out[m.group(1)] = out.get(m.group(1), 0) + int(r.get("impressions", 0))
    return out


def load_moteur():
    """Etat du moteur autonome (rythme, plafond par podcast) et scores de qualite (porte d'entree)."""
    etat, scores = {}, {}
    try:
        etat = json.load(open(f"{PAGES_DIR}/data/moteur_autonome_etat.json", encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    try:
        scores = json.load(open(f"{PAGES_DIR}/data/moments_scores.json", encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return etat, scores


def main():
    cfg = load_cfg()
    etat, mscores = load_moteur()
    cap = int(os.environ.get("MOMENTS_PAR_JOUR") or etat.get("moments_par_jour") or cfg.get("moments_par_jour", 30))
    max_par_podcast = int(etat.get("max_par_podcast", 0)) or None
    cap = max(int(cfg.get("moments_par_jour_min", 1)), min(cap, int(cfg.get("moments_par_jour_max", 100))))
    exclure = set(cfg.get("exclure_slugs") or [])
    prio = list(cfg.get("priorite_slugs") or [])
    imp = podcast_impressions()
    today = datetime.date.today().isoformat()
    try:
        state = json.load(open(STATE_FILE, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    released = state.setdefault("released", {})
    already_today = sum(1 for d in released.values() if d == today)
    quota = max(cap - already_today, 0)
    if cfg.get("pause_plan"):   # pause : plan du site vide, aucune nouvelle page ouverte (pages conservees en base)
        released.clear()
        quota = 0

    queues = {}
    for f in sorted(glob.glob(f"{MOMENTS_DIR}/*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        slug = d.get("slug") or os.path.basename(f)[:-5]
        if slug in exclure:
            continue
        scores = eligible_scores(d.get("entries") or {})
        if mscores:   # moteur autonome : seules les pages en porte d'entree (2 paragraphes + score >= 70) sont ouvertes
            scores = {i: mscores[f"{slug}/{i}"].get("score_final", sc) for i, sc in scores.items()
                      if mscores.get(f"{slug}/{i}", {}).get("gate")}   # ordre : score final (contenu + demande)
        good = set(scores)
        for key in [k for k in released if k.startswith(slug + "/") and k.split("/", 1)[1] not in good]:
            del released[key]            # page devenue trop fine : retiree du sitemap
        ids = sorted((i for i in good if f"{slug}/{i}" not in released), key=lambda i: (-scores[i], i))   # les plus riches d'abord
        if max_par_podcast:   # plafond par podcast sur les NOUVELLES ouvertures (les anciennes restent)
            ids = ids[:max(0, max_par_podcast - sum(1 for k in released if k.startswith(slug + "/")))] if mscores else ids
        if ids:
            queues[slug] = ids

    added = 0
    def ordre(sl):   # priorite explicite, puis podcasts deja visibles dans Google (impressions), puis le reste
        return (0 if sl in prio else 1, prio.index(sl) if sl in prio else 0, -imp.get(sl, 0), sl)
    queues = dict(sorted(queues.items(), key=lambda kv: ordre(kv[0])))
    while added < quota and queues:   # un moment par podcast a tour de role
        for slug in list(queues):
            if added >= quota:
                break
            released[f"{slug}/{queues[slug].pop(0)}"] = today
            added += 1
            if not queues[slug]:
                del queues[slug]

    # Fiches N1 (hub) du podcast de chaque moment ouvert : ajoutees au plan du site, car chaque moment y est rattache (16/10/2026)
    hubs = {}
    for key, day in sorted(released.items()):
        slug = key.split("/", 1)[0]
        try:
            hub = (json.load(open(f"{MOMENTS_DIR}/{slug}.json", encoding="utf-8")).get("hub") or "").strip()
        except (OSError, json.JSONDecodeError):
            hub = ""
        if hub and os.path.exists(f"{PAGES_DIR}/" + hub.replace("/podcast-btb/", "", 1)):
            hubs.setdefault("https://listenly.org" + hub, day)
    entries = "\n".join(
        [f"  <url>\n    <loc>{BASE}/{key}</loc>\n    <lastmod>{day}</lastmod>\n    <priority>0.8</priority>\n  </url>"
         for key, day in sorted(released.items())]
        + [f"  <url>\n    <loc>{url}</loc>\n    <lastmod>{day}</lastmod>\n    <priority>0.9</priority>\n  </url>"
           for url, day in sorted(hubs.items())]
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + entries + "\n</urlset>\n")
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(xml)
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=0, sort_keys=True)
    write_a_indexer(released, today)
    sync_hubs_sitemap(today)
    left = sum(len(v) for v in queues.values())
    print(f"[moments-sitemap] +{added} aujourd'hui (plafond {cap}) | total ouvert a Google : {len(released)} | restant en attente : {left}")


def write_a_indexer(released, today):
    """Liste du jour : chaque moment ouvert aujourd'hui avec sa fiche N1 (hub du podcast)."""
    items, sans_n1 = [], 0
    try:
        mscores = json.load(open(SCORES_FILE, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        mscores = {}
    for key, day in sorted(released.items()):
        if day != today:
            continue
        slug, mid = key.split("/", 1)
        try:
            d = json.load(open(f"{MOMENTS_DIR}/{slug}.json", encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            d = {}
        q_info = mscores.get(key) or {}
        if not q_info.get("gate"):   # garde-fou : seule une fiche validee par le score qualite entre dans la liste
            continue
        hub = (d.get("hub") or "").strip()
        n1_existe = bool(hub) and os.path.exists(f"{PAGES_DIR}/" + hub.replace("/podcast-btb/", "", 1))
        if not n1_existe:
            sans_n1 += 1
        e = (d.get("entries") or {}).get(mid) or {}
        items.append({
            "moment": f"{BASE}/{key}",
            "question": e.get("q"),
            "podcast": slug,
            "n1": f"https://listenly.org{hub}" if hub else "",
            "n1_existe": n1_existe,
            "score_qualite": q_info.get("score"),
            "score_final": q_info.get("score_final"),
            "validation": "porte d'entree : 2 paragraphes et score qualite >= 70",
        })
    out = {"date": today, "nombre": len(items), "sans_n1": sans_n1,
           "methode": "Moments ouverts aujourd'hui au sitemap, chacun avec la fiche N1 de son podcast. "
                      "A demander a Google a la main (Search Console) : ne jamais publier de titre sans validation.",
           "items": items}
    with open(f"{PAGES_DIR}/data/moments_a_indexer.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)


HUBS_OUT = f"{PAGES_DIR}/sitemap-hubs.xml"
INDEX_OUT = f"{PAGES_DIR}/sitemap-index-podcast-btb.xml"
HUB_BASE = "https://listenly.org"


def allowed_hub_urls(released=None):
    """Fiches N1 a garder dans le sitemap : celles du podcast d'au moins un moment ouvert
    (moment present dans released). Regle du 16/10/2026 : une N1 entre au sitemap avec son premier moment
    ouvert et en sort quand il n'en reste aucun. Retourne {url: chemin_disque}."""
    if released is None:
        try:
            released = json.load(open(STATE_FILE, encoding="utf-8")).get("released", {})
        except (OSError, json.JSONDecodeError):
            released = {}
    out = {}
    for slug in sorted({k.split("/", 1)[0] for k in released}):
        try:
            d = json.load(open(f"{MOMENTS_DIR}/{slug}.json", encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        hub = (d.get("hub") or "").strip()
        if not re.fullmatch(r"/podcast-btb/[a-z0-9\-]+\.html", hub):
            continue
        path = f"{PAGES_DIR}/" + hub.replace("/podcast-btb/", "", 1)
        if os.path.exists(path):
            out[HUB_BASE + hub] = path
    return out


def sync_hubs_sitemap(today):
    """Reecrit sitemap-hubs.xml : uniquement les N1 de allowed_hub_urls(). Date de premiere entree conservee,
    date du jour pour les nouvelles. L'index recoit la date du jour."""
    try:
        old = dict(re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", open(HUBS_OUT, encoding="utf-8").read()))
    except OSError:
        old = {}
    wanted = allowed_hub_urls()
    entries = "\n".join(
        f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{old.get(u, today)}</lastmod>\n    <priority>1.0</priority>\n  </url>"
        for u in sorted(wanted)
    )
    out = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + entries + "\n</urlset>\n")
    with open(HUBS_OUT, "w", encoding="utf-8") as fh:
        fh.write(out)
    try:
        idx = open(INDEX_OUT, encoding="utf-8").read()
        idx = re.sub(r"(sitemap-hubs\.xml</loc>\s*<lastmod>)[^<]+(</lastmod>)", lambda m: m.group(1) + today + m.group(2), idx)
        with open(INDEX_OUT, "w", encoding="utf-8") as fh:
            fh.write(idx)
    except OSError:
        pass
    print(f"[hubs-sitemap] {len(wanted)} fiches N1 (podcasts avec moment ouvert), {len(old) - len(set(old) & set(wanted))} retirees, {len(wanted) - len(set(old) & set(wanted))} ajoutees")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Maillage interne des fiches N1 (01/10/2026).

Objectif : que Google puisse atteindre CHAQUE hub par des liens, pas seulement par le sitemap.
 1. Bloc "Podcasts similaires" (6 liens, meme categorie) injecte dans chaque hub NON protege.
    Choix stable (classement par hash) : les liens ne bougent presque jamais d'un jour a l'autre.
 2. Bloc "Derniers podcasts ajoutes" (30 hubs les plus recents) dans index.html : les nouveaux hubs
    sont decouverts des que Google recrawle l'index.

Regle absolue : on ne touche PAS aux hubs deja indexes par Google, ni a ceux qui ont des impressions,
ni aux pages du pilote de style (hub_style.json). Idempotent (blocs delimites par des marqueurs).
"""
import os, re, json, html, hashlib, glob

PAGES = "pages/podcast-btb"
DATA = f"{PAGES}/data"
BEGIN, END = "<!-- BEGIN related-hubs -->", "<!-- END related-hubs -->"
IBEGIN, IEND = "<!-- BEGIN latest-hubs -->", "<!-- END latest-hubs -->"
N_RELATED, N_LATEST = 6, 30


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def slug_of(rec):
    return rec["fiche_url"].rsplit("/", 1)[-1].replace(".html", "")


def protected_slugs():
    prot = set()
    for slug, v in load(f"{DATA}/gsc_hub_status.json", {}).items():
        if v.get("indexed_on"):
            prot.add(slug if slug.endswith("-podcast") else slug + "-podcast")
    for url in (load(f"{DATA}/gsc_pages.json", {}).get("pages") or {}):
        m = re.search(r"/podcast-btb/([^/]+-podcast)\.html$", url)
        if m:
            prot.add(m.group(1))
    for s in load(f"{PAGES}/hub_style.json", {}).get("slugs", []):
        prot.add(s if s.endswith("-podcast") else s + "-podcast")
    return prot


def h(x):
    return int(hashlib.sha1(x.encode()).hexdigest(), 16)


def neighbours(rec, recs):
    me = slug_of(rec)
    same = [r for r in recs if r["categorie"] == rec["categorie"] and slug_of(r) != me]
    others = [r for r in recs if r["categorie"] != rec["categorie"] and slug_of(r) != me]
    key = lambda r: h(me + "|" + slug_of(r))
    pick = sorted(same, key=key)[:N_RELATED]
    if len(pick) < N_RELATED:
        pick += sorted(others, key=key)[: N_RELATED - len(pick)]
    return pick


def block(rec, picks):
    fr = (rec.get("language") or "en").startswith("fr")
    title = "Podcasts similaires" if fr else "Related podcasts"
    items = "".join(
        f'<li style="margin:6px 0"><a href="{html.escape(r["fiche_url"])}" style="color:#555;">'
        f'{html.escape(r["podcast_name"])}</a></li>'
        for r in picks
    )
    return (f'{BEGIN}\n<nav aria-label="{title}" style="max-width:720px;margin:0 auto;padding:0 20px 24px;'
            f'font-family:Helvetica,Arial,sans-serif;font-size:13px;color:#777;">'
            f'<p style="margin:0 0 6px;font-weight:600;color:#555;">{title}</p>'
            f'<ul style="margin:0;padding-left:18px;">{items}</ul></nav>\n{END}\n')


def inject(path, blk, begin, end, anchors):
    with open(path, encoding="utf-8") as f:
        t = f.read()
    if begin in t:
        new = re.sub(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", lambda m: blk, t, flags=re.S)
    else:
        new = None
        for a in anchors:
            i = t.find(a)
            if i != -1:
                new = t[:i] + blk + t[i:]
                break
        if new is None:
            return False
    if new != t:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        return True
    return False


def main():
    recs = load(f"{DATA}/podcasts.json", [])
    prot = protected_slugs()
    changed = skipped = missing = 0
    for rec in recs:
        s = slug_of(rec)
        path = f"{PAGES}/{s}.html"
        if not os.path.exists(path):
            missing += 1
            continue
        if s in prot:
            skipped += 1
            continue
        if inject(path, block(rec, neighbours(rec, recs)), BEGIN, END, ['<div id="semantic-index"', "</body>"]):
            changed += 1

    # index.html : derniers hubs ajoutes
    latest = sorted(recs, key=lambda r: (r.get("date") or "", slug_of(r)), reverse=True)[:N_LATEST]
    lis = "".join(
        f'<li style="margin:6px 0"><a href="{html.escape(r["fiche_url"])}">{html.escape(r["podcast_name"])}</a>'
        f' <span style="color:#999">· {html.escape(r["categorie"])}</span></li>'
        for r in latest
    )
    iblk = (f'{IBEGIN}\n<section style="max-width:720px;margin:24px auto;padding:0 20px;font-family:Helvetica,Arial,sans-serif;">'
            f'<h2 style="font-size:18px;">Derniers podcasts ajoutés</h2><ul style="padding-left:18px;">{lis}</ul></section>\n{IEND}\n')
    idx = f"{PAGES}/index.html"
    idx_changed = inject(idx, iblk, IBEGIN, IEND, ["<footer", "</body>"]) if os.path.exists(idx) else False
    print(f"[hub-related] hubs mis a jour: {changed} | proteges (intouches): {skipped} | fichiers absents: {missing} | index: {'maj' if idx_changed else 'inchange'}")


if __name__ == "__main__":
    main()

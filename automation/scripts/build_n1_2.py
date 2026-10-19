#!/usr/bin/env python3
"""Fiche N1.2 (HUB d'autorité) : génère la page d'un podcast à partir des données existantes.

Aucun appel IA, aucune donnée nouvelle : identité (podcasts.json) + liste des questions
(data/moments/<slug>.json). Le design reprend EXACTEMENT le gabarit des pages de moment
(pages/podcast-btb/m-template.html) : mêmes couleurs, même police, même barre de recherche,
mêmes cartes. Pas de lecteur sur la fiche N1 : il est sur chaque page moment. Seul le contenu change : identité du podcast en tête,
puis la liste de ses questions, chacune reliée à sa page de moment.

Le HUB ne reprend pas le texte des réponses : il liste les questions, chacune vers sa page de moment.

Usage : python3 automation/scripts/build_n1_2.py <slug> [sortie.html] [max_questions]
Par défaut, la page part dans pages/podcast-btb/n1-2-preview/ (aperçu, pas de mise en ligne).
"""
import html
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
PODCASTS = os.path.join(ROOT, "pages", "podcast-btb", "data", "podcasts.json")
MOMENTS_DIR = os.path.join(ROOT, "pages", "podcast-btb", "data", "moments")
TEMPLATE = os.path.join(ROOT, "pages", "podcast-btb", "m-template.html")
BASE_MOMENT = "https://listenly.org/podcast-btb/m"

EXTRA_CSS = """
  .hero{ padding: 12vh 24px 32px; }
  .hero .sub{ text-align: left; margin: 0 0 26px; max-width: none; font-size: 16px; }
  .n1-id{ display:flex; gap:20px; align-items:center; text-align:left; margin-bottom:18px; }
  .n1-id h1{ font-size: clamp(28px, 4.4vw, 42px); margin: 0 0 6px; }
  .n1-cover{ width:120px; height:120px; border-radius:20px; object-fit:cover; flex-shrink:0;
             box-shadow: 0 8px 30px rgba(0,0,0,0.45); }
  .n1-kicker{ color: var(--ink-soft); font-size:12.5px; text-transform:uppercase; letter-spacing:.07em; margin:0 0 4px; }
  .n1-host{ color: var(--ink-soft); margin:0; font-size:15px; }
  .listen-link{ display:inline-block; margin-top:22px; color: var(--accent); text-decoration:none;
                font-size:14.5px; font-weight:500; }
  .listen-link:hover{ opacity:.75; }
  .result-card .rc-question a{ color: inherit; text-decoration: none; }
  .result-card .rc-question a:hover{ color: var(--accent); }
  @media (max-width: 560px){
    .n1-id{ flex-direction: column; align-items: flex-start; }
    .n1-cover{ width:96px; height:96px; }
  }
"""


def load_podcast(slug):
    data = json.load(open(PODCASTS, encoding="utf-8"))
    items = data if isinstance(data, list) else list(data.values())
    for it in items:
        if isinstance(it, dict) and it.get("slug") == slug:
            return it
    raise SystemExit(f"Podcast introuvable : {slug}")


def load_moments(slug):
    path = os.path.join(MOMENTS_DIR, f"{slug}.json")
    if not os.path.exists(path):
        return []
    entries = json.load(open(path, encoding="utf-8")).get("entries", {})
    out = []
    for mid, e in entries.items():
        q = (e.get("q") or "").strip()
        if q:
            out.append((mid, q))
    return out


def esc(s):
    return html.escape(str(s or ""), quote=True)


def template_css():
    tpl = open(TEMPLATE, encoding="utf-8").read()
    m = re.search(r"<style>(.*?)</style>", tpl, re.S)
    if not m:
        raise SystemExit("Gabarit m-template.html : bloc <style> introuvable")
    return m.group(1)


def build(slug, max_questions=10):
    p = load_podcast(slug)
    all_moments = load_moments(slug)
    shown = all_moments[:max_questions]
    name = p.get("podcast_name", slug)
    host = p.get("host_name", "")
    cat = p.get("categorie", "")
    punch = p.get("punchline", "")
    cover = p.get("cover_image", "")
    podcast_url = p.get("podcast_url", "")
    lang = p.get("language", "en")
    canon = f"https://listenly.org/podcast-btb/{slug}-podcast.html"

    if shown:
        cards = "\n".join(
            f'''  <div class="result-card">
    <p class="rc-question"><a href="{BASE_MOMENT}/{esc(slug)}/{esc(mid)}">{esc(q)}</a></p>
    <div class="rc-meta">
      <span class="rc-source"><strong>{esc(host)}</strong> on {esc(name)}</span>
      <a class="rc-play" href="{BASE_MOMENT}/{esc(slug)}/{esc(mid)}" style="text-decoration:none;">Read the answer →</a>
    </div>
  </div>'''
            for mid, q in shown)
    else:
        cards = '  <div class="state-msg">Questions from this podcast are coming soon.</div>'

    cover_html = f'<img class="n1-cover" src="{esc(cover)}" alt="{esc(name)}">' if cover else ""
    listenly_page = p.get("listenly_url") or ""
    listen_html = (f'<a class="listen-link" href="{esc(listenly_page)}">Listen to the podcast →</a>'
                   if listenly_page else "")
    ld = {"@context": "https://schema.org", "@type": "PodcastSeries", "name": name,
          "description": punch, "url": podcast_url, "image": cover, "genre": cat,
          "author": {"@type": "Person", "name": host}}
    count = len(all_moments)

    return f"""<!DOCTYPE html>
<html lang="{esc(lang)}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(name)}: expert answers | Listenly</title>
<meta name="description" content="{esc(punch[:150])}">
<link rel="canonical" href="{canon}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(name)} | Listenly">
<meta property="og:description" content="{esc(punch[:150])}">
<meta property="og:url" content="{canon}">
<script type="application/ld+json">
{json.dumps(ld, ensure_ascii=False)}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{template_css()}{EXTRA_CSS}</style>
</head>
<body>

<header style="position:relative;z-index:5;display:flex;align-items:center;justify-content:space-between;padding:16px clamp(16px,4vw,40px);">
  <a href="https://listenly.org/" style="color:#F5F5F7;text-decoration:none;font-weight:700;font-size:18px;letter-spacing:-0.01em;">Listenly</a>
</header>

<div class="ambient-glow">
  <div class="glow-blob a"></div>
  <div class="glow-blob b"></div>
  <div class="glow-blob c"></div>
  <div class="glow-blob d"></div>
</div>

<main>
<section class="hero">
  <div class="hero-content">
    <div class="n1-id">
      {cover_html}
      <div>
        <p class="n1-kicker">{esc(cat) if cat else "Podcast"}</p>
        <h1>{esc(name)}</h1>
        <p class="n1-host">{esc(host)}</p>
      </div>
    </div>
    <p class="sub">{esc(punch)}</p>

    <div class="search-shell">
      <form class="search-box" action="https://listenly.org/" method="get">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <div class="input-wrap">
          <input type="search" name="q" aria-label="Search" placeholder="Explore more expert answers" autocomplete="off">
        </div>
        <button type="submit">Search</button>
      </form>
    </div>

    <div class="avail-count"><span class="dot"></span><strong>{count}</strong> questions from this podcast</div>
    {listen_html}
  </div>
</section>

<div class="results-wrap">
{cards}
</div>
</main>

</body>
</html>
"""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    slug = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        ROOT, "pages", "podcast-btb", "n1-2-preview", f"{slug}-podcast.html")
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(build(slug, n))
    print(out)

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
  .about{ max-width: 640px; margin: 0 auto; padding: 8px 24px 8px; text-align: left; }
  .about h2{ font-size: 20px; font-weight: 600; margin: 0 0 10px; }
  .about h3{ font-size: 14px; font-weight: 600; color: var(--ink-soft); text-transform: uppercase;
             letter-spacing: .06em; margin: 26px 0 10px; }
  .about-text{ font-size: 16px; line-height: 1.6; color: var(--ink); margin: 0; }
  .chips{ display: flex; flex-wrap: wrap; gap: 8px; }
  .chip{ background: var(--panel); border: 1px solid var(--line-soft); border-radius: 999px;
         padding: 6px 12px; font-size: 13px; color: var(--ink); }
  .experts{ list-style: none; padding: 0; margin: 0; }
  .experts li{ padding: 6px 0; font-size: 15px; border-bottom: 1px solid var(--line-soft); }
  .experts .role{ color: var(--ink-soft); }
  .facts{ font-size: 13px; color: var(--ink-soft); margin: 22px 0 0; }
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
            out.append({"id": mid, "q": q, "expert": (e.get("x") or "").strip(),
                        "role": (e.get("gt") or "").strip(), "episode": (e.get("e") or "").strip(),
                        "themes": e.get("en") or []})
    return out


def parse_themes(raw):
    """Les thèmes sont stockés en liste ou en texte de liste : on accepte les deux."""
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    try:
        import ast
        val = ast.literal_eval(raw) if isinstance(raw, str) and raw.startswith("[") else []
        return [str(t).strip() for t in val if str(t).strip()]
    except (ValueError, SyntaxError):
        return []


def about_block(p, moments):
    """Bloc « À propos » (consignes N1.2) : uniquement des données réelles du podcast et de ses questions.
    Renvoie du HTML, ou '' si rien de fiable à afficher."""
    name = p.get("podcast_name", "")
    host = p.get("host_name", "")
    company = p.get("host_company", "")
    cat = p.get("categorie", "")
    punch = p.get("punchline", "")

    experts = {}
    for m in moments:
        if m["expert"] and m["expert"] not in experts:
            experts[m["expert"]] = m["role"]
    counts = {}
    for m in moments:
        for t in parse_themes(m["themes"]):
            counts[t] = counts.get(t, 0) + 1
    themes = [t for t, _ in sorted(counts.items(), key=lambda kv: -kv[1])][:6]
    episodes = {m["episode"] for m in moments if m["episode"]}

    # Description : 80 à 120 mots maximum, construite à partir des champs du podcast.
    parts = []
    if name:
        intro = f"{name} is a {cat} podcast" if cat else f"{name} is a podcast"
        if host:
            intro += f" hosted by {host}" + (f" ({company})" if company else "")
        parts.append(intro + ".")
    if punch:
        parts.append(punch)
    if experts:
        parts.append(f"It features {len(experts)} expert(s) answering concrete questions.")
    description = " ".join(parts)

    if not (description or experts or themes):
        return ""

    blocks = []
    if description:
        blocks.append(f'<h2>About this podcast</h2>\n    <p class="about-text">{esc(description)}</p>')
    if themes:
        chips = "".join(f'<span class="chip">{esc(t)}</span>' for t in themes)
        blocks.append(f'<h3>Topics covered</h3>\n    <div class="chips">{chips}</div>')
    if experts:
        items = "".join(
            f'<li><strong>{esc(n)}</strong>' + (f' <span class="role">· {esc(r)}</span>' if r else "") + "</li>"
            for n, r in experts.items())
        blocks.append(f'<h3>Experts</h3>\n    <ul class="experts">{items}</ul>')
    facts = [f"{len(moments)} questions indexed"]
    if episodes:
        facts.append(f"{len(episodes)} episode(s) cited")
    if experts:
        facts.append(f"{len(experts)} expert(s)")
    blocks.append(f'<p class="facts">{esc(" · ".join(facts))}</p>')
    return '<section class="about">\n    ' + "\n    ".join(blocks) + "\n  </section>"


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
    shown = [(m["id"], m["q"]) for m in all_moments[:max_questions]]
    about_html = about_block(p, all_moments)
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
    # Qualité minimale (CLAUDE.md) : une fiche N1 n'est indexable qu'avec au moins une vraie
    # question portée par un expert identifié. Sinon : noindex, follow (et hors sitemap).
    qualified = any(m["expert"] and m["q"] for m in all_moments)
    robots = "" if qualified else '<meta name="robots" content="noindex, follow">'

    return f"""<!DOCTYPE html>
<html lang="{esc(lang)}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{robots}
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

{about_html}
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
    switch = os.path.join(ROOT, "automation", "marketforge_engine", "modele_n1.json")
    modele = json.load(open(switch, encoding="utf-8")).get("modele_actif", "N1.2")
    if modele != "N1.2":
        raise SystemExit(
            f"Modèle actif = {modele} : aucune fiche N1.2 générée. "
            "L'ancien modèle N1.1 est conservé dans pages/podcast-btb/n1-1-archive/. "
            "Pour repasser en N1.2, remettre modele_actif à N1.2 dans automation/marketforge_engine/modele_n1.json.")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        ROOT, "pages", "podcast-btb", "n1-2-preview", f"{slug}-podcast.html")
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(build(slug, n))
    print(out)

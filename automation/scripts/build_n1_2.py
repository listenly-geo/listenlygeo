#!/usr/bin/env python3
"""Fiche N1.2 (HUB d'autorité) : génère la page d'un podcast à partir des données existantes.

Aucun appel IA, aucune donnée nouvelle : identité (podcasts.json) + liste des moments
(data/moments/<slug>.json). Charte sombre Listenly (19/10/2026). Le HUB ne reprend pas le texte
des moments : il les liste, chacun relié à sa page de moment (/podcast-btb/m/<slug>/<id>).

Usage : python3 automation/scripts/build_n1_2.py <slug> [sortie.html] [max_moments]
Par défaut, la page part dans pages/podcast-btb/n1-2-preview/ (aperçu, pas de mise en ligne).
"""
import html
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
PODCASTS = os.path.join(ROOT, "pages", "podcast-btb", "data", "podcasts.json")
MOMENTS_DIR = os.path.join(ROOT, "pages", "podcast-btb", "data", "moments")
BASE_MOMENT = "https://listenly.org/podcast-btb/m"


def load_podcast(slug):
    data = json.load(open(PODCASTS, encoding="utf-8"))
    items = data if isinstance(data, list) else list(data.values())
    for it in items:
        if isinstance(it, dict) and it.get("slug") == slug:
            return it
    raise SystemExit(f"Podcast introuvable : {slug}")


def load_moments(slug, limit):
    path = os.path.join(MOMENTS_DIR, f"{slug}.json")
    if not os.path.exists(path):
        return []
    entries = json.load(open(path, encoding="utf-8")).get("entries", {})
    out = []
    for mid, e in entries.items():
        q = (e.get("q") or "").strip()
        if q:
            out.append((mid, q))
    return out[:limit]


def esc(s):
    return html.escape(str(s or ""), quote=True)


def build(slug, max_moments=10):
    p = load_podcast(slug)
    moments = load_moments(slug, max_moments)
    name = p.get("podcast_name", slug)
    host = p.get("host_name", "")
    cat = p.get("categorie", "")
    punch = p.get("punchline", "")
    cover = p.get("cover_image", "")
    podcast_url = p.get("podcast_url", "")
    accent = "#2997FF"

    if moments:
        items = "\n".join(
            f'      <li><a href="{BASE_MOMENT}/{esc(slug)}/{esc(mid)}">{esc(q)}</a></li>'
            for mid, q in moments
        )
        moments_html = f'<ol class="moments">\n{items}\n    </ol>'
    else:
        moments_html = '<p class="empty">Les questions de cet épisode arrivent bientôt.</p>'

    listen = (f'<a class="btn" href="{esc(podcast_url)}" rel="noopener">Écouter sur Apple Podcasts</a>'
              if podcast_url else "")

    return f"""<!doctype html>
<html lang="{esc(p.get('language', 'en'))}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(name)} : questions et réponses | Listenly</title>
<meta name="description" content="{esc(punch[:150])}">
<link rel="canonical" href="https://listenly.org/podcast-btb/{esc(slug)}-podcast.html">
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"PodcastSeries","name":{json.dumps(name, ensure_ascii=False)},
"description":{json.dumps(punch, ensure_ascii=False)},"url":{json.dumps(podcast_url)},
"image":{json.dumps(cover)},"genre":{json.dumps(cat, ensure_ascii=False)},
"author":{{"@type":"Person","name":{json.dumps(host, ensure_ascii=False)}}}}}
</script>
<style>
  :root {{ --bg:#000000; --card:#1C1C1E; --ink:#F5F5F7; --soft:#86868B; --accent:{accent}; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
         font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  header {{ display:flex; align-items:center; gap:12px; padding:16px; }}
  .logo {{ color:var(--ink); font-weight:700; text-decoration:none; font-size:18px; }}
  .search {{ flex:1; display:flex; }}
  .search input {{ width:100%; background:var(--card); color:var(--ink); border:1px solid #2c2c2e;
                  border-radius:999px; padding:10px 16px; font-size:15px; }}
  main {{ max-width:720px; margin:0 auto; padding:8px 16px 120px; }}
  .card {{ background:var(--card); border-radius:16px; padding:20px; margin-bottom:16px; }}
  .show {{ display:flex; gap:16px; align-items:center; }}
  .show img {{ width:120px; height:120px; border-radius:14px; object-fit:cover; }}
  h1 {{ font-size:24px; margin:0 0 6px; line-height:1.2; }}
  .meta {{ color:var(--soft); font-size:14px; margin:0; }}
  .punch {{ font-size:15px; line-height:1.5; margin:12px 0 0; }}
  h2 {{ font-size:17px; margin:0 0 12px; }}
  ol.moments {{ padding-left:20px; margin:0; }}
  ol.moments li {{ margin:0 0 10px; line-height:1.4; }}
  ol.moments a {{ color:var(--accent); text-decoration:none; }}
  .empty {{ color:var(--soft); margin:0; }}
  .btn {{ display:inline-block; background:var(--accent); color:#000; font-weight:600;
          padding:10px 16px; border-radius:999px; text-decoration:none; font-size:14px; }}
  .player {{ position:fixed; left:0; right:0; bottom:0; background:var(--card);
             padding:12px 16px; display:flex; justify-content:center; border-top:1px solid #2c2c2e; }}
  @media (max-width:520px) {{ .show {{ flex-direction:column; align-items:flex-start; }} }}
</style>
</head>
<body>
<header>
  <a class="logo" href="https://listenly.org/">Listenly</a>
  <form class="search" action="https://listenly.org/" method="get">
    <input type="search" name="q" placeholder="Explore more expert answers">
  </form>
</header>
<main>
  <section class="card show">
    {f'<img src="{esc(cover)}" alt="{esc(name)}">' if cover else ''}
    <div>
      <h1>{esc(name)}</h1>
      <p class="meta">{esc(host)}{' · ' + esc(cat) if cat else ''}</p>
    </div>
  </section>
  <section class="card">
    <p class="punch">{esc(punch)}</p>
    <p style="margin:14px 0 0">{listen}</p>
  </section>
  <section class="card">
    <h2>Questions de l'épisode</h2>
    {moments_html}
  </section>
</main>
<div class="player" aria-label="Lecteur">
  <span class="meta">Lecteur à intégrer</span>
</div>
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

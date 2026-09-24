#!/usr/bin/env python3
"""
Hub-index (24/09/2026) : la fiche podcast N1 devient l'index complet des questions du podcast.

Chaque question publiee apparait DANS le hub avec sa reponse courte, le moment de l'episode ou
elle est dite, une ancre (#slug-de-la-question) et un CTA « Ecouter ce moment » vers Listenly.
Les fiches question completes restent accessibles via « Reponse complete » (les nouvelles sont
generees en noindex : c'est le hub qui porte le referencement, voir FICHE_NOINDEX dans
generate_qa_fiches_btb.py).

Placement dans la page :
  - moins de HUB_TOP_THRESHOLD questions : en bas du contenu (avant </main>), la description
    du podcast porte la page ;
  - a partir de HUB_TOP_THRESHOLD questions : juste apres le bouton d'ecoute du haut de page,
    la description descend en dessous.
Le bloc est delimite par les marqueurs QUESTIONS_COVERED_START/END (memes marqueurs que
l'ancien bloc « Questions couvertes », qui est ainsi remplace proprement).

Exclusions : les fiches retirees de l'index lors de l'audit qualite (data/noindex_fiches.json)
ne sont pas reprises dans le hub.
"""

import os, re, json, glob, html

PAGES_DIR = "pages/podcast-btb"
KNOWLEDGE_DIR = f"{PAGES_DIR}/data/knowledge_moments"
NOINDEX_LIST = f"{PAGES_DIR}/data/noindex_fiches.json"
HUB_TOP_THRESHOLD = 10
START_MARKER = "<!-- QUESTIONS_COVERED_START -->"
END_MARKER = "<!-- QUESTIONS_COVERED_END -->"

STRINGS = {
    "fr": {
        "title": "Les réponses de ce podcast",
        "stats": "{n} question{s} répondue{s} · {e} épisode{es} indexé{es}",
        "search": "Rechercher parmi les {n} réponses de ce podcast…",
        "listen": "▶ Écouter ce moment",
        "full": "Réponse complète →",
        "none": "Aucune réponse ne correspond à cette recherche.",
    },
    "en": {
        "title": "Answers from this podcast",
        "stats": "{n} question{s} answered · {e} episode{es} indexed",
        "search": "Search the {n} answers in this podcast…",
        "listen": "▶ Listen to this moment",
        "full": "Full answer →",
        "none": "No answer matches this search.",
    },
}

_E = html.escape


def _anchor(text, used):
    base = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:70] or "q"
    anchor, i = base, 2
    while anchor in used:
        anchor, i = f"{base}-{i}", i + 1
    used.add(anchor)
    return anchor


def _norm(q):
    return re.sub(r"\s+", " ", (q or "").strip().lower())


def load_excluded_urls():
    try:
        with open(NOINDEX_LIST, encoding="utf-8") as f:
            return {x["url"] for x in json.load(f).get("fiches", [])}
    except (OSError, ValueError):
        return set()


def load_timestamps(slug):
    """Moment (secondes) de chaque question, depuis les knowledge moments de ce podcast."""
    stamps = {}
    for path in glob.glob(f"{KNOWLEDGE_DIR}/{glob.escape(slug)}--*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                for m in json.load(f):
                    if m.get("start_seconds"):
                        stamps[_norm(m.get("question"))] = int(m["start_seconds"])
        except (OSError, ValueError, TypeError):
            continue
    return stamps


def _fmt_time(seconds):
    seconds = int(seconds or 0)
    if seconds <= 0:
        return ""
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def listen_url(podcast):
    url = podcast.get("listenly_url") or ""
    if "listenly.fr/podcast/show" in url:
        return url
    return podcast.get("podcast_url") or url or "https://listenly.fr"


def visible_entries(published):
    excluded = load_excluded_urls()
    return [p for p in published if p.get("url", "").replace("https://listenly.fr", "") not in excluded]


def render_hub_index(podcast, published):
    lang = "en" if podcast.get("language") == "en" else "fr"
    t = STRINGS[lang]
    entries = visible_entries(published)
    stamps = load_timestamps(podcast["slug"])
    target = listen_url(podcast)

    episodes = {}
    for p in sorted(entries, key=lambda x: x.get("added_date", ""), reverse=True):
        episodes.setdefault(p.get("source_episode_title") or "", []).append(p)

    n, e = len(entries), len(episodes)
    large = n >= HUB_TOP_THRESHOLD
    used = set()

    sections = []
    chips = []
    for ep_title, items in episodes.items():
        ep_anchor = "ep-" + _anchor(ep_title, used)
        chips.append(f'<a class="hx-chip" href="#{ep_anchor}">{_E(ep_title[:70])} <span>{len(items)}</span></a>')
        cards = []
        for p in items:
            q_anchor = _anchor(p.get("question"), used)
            seconds = p.get("start_seconds") or stamps.get(_norm(p.get("question")))
            when = _fmt_time(seconds)
            listen_label = t["listen"] + (f" · {when}" if when else "")
            answer = _E(re.sub(r"\s+", " ", p.get("answer_snippet") or "").strip())
            cards.append(
                f'<article class="hx-qa" id="{q_anchor}">'
                f'<h3 class="hx-q">{_E(p.get("question", ""))}</h3>'
                + (f'<p class="hx-a">{answer}</p>' if answer else "")
                + '<div class="hx-foot">'
                f'<a class="hx-listen plausible-event-name=Clic+Hub+Moment" href="{_E(target)}">{listen_label}</a>'
                f'<a class="hx-more" href="{_E(p.get("url", ""))}">{t["full"]}</a>'
                "</div></article>"
            )
        heading = f'<h3 class="hx-ep" id="{ep_anchor}">{_E(ep_title)}</h3>' if ep_title else ""
        sections.append(f'<section class="hx-episode">{heading}{"".join(cards)}</section>')

    plural = lambda k: "s" if k > 1 else ""
    stats = t["stats"].format(n=n, s=plural(n), e=e, es=plural(e))
    search = ""
    if large:
        search = (
            '<div class="hx-tools">'
            f'<input class="hx-search" type="search" placeholder="{_E(t["search"].format(n=n))}" aria-label="{_E(t["search"].format(n=n))}">'
            + (f'<nav class="hx-chips">{"".join(chips)}</nav>' if e > 1 else "")
            + f'<p class="hx-empty" hidden>{t["none"]}</p></div>'
        )

    return f"""
<style>
.hx-wrap {{ margin:32px 0 40px; padding-top:28px; border-top:1px solid #ececec; }}
.hx-title {{ font-size:22px; font-weight:800; margin:0 0 4px; color:#0a0a0a; }}
.hx-stats {{ font-size:13px; color:#777; margin:0 0 16px; }}
.hx-tools {{ position:sticky; top:0; background:#fff; padding:10px 0 8px; z-index:5; }}
.hx-search {{ width:100%; box-sizing:border-box; padding:12px 16px; font-size:16px; border:1px solid #e2e2e2; border-radius:12px; background:#fafafa; }}
.hx-chips {{ display:flex; gap:8px; overflow-x:auto; padding:10px 0 2px; }}
.hx-chip {{ white-space:nowrap; font-size:12px; color:#333; text-decoration:none; background:#f4f4f4; border:1px solid #e6e6e6; border-radius:999px; padding:5px 11px; }}
.hx-chip span {{ color:#999; }}
.hx-empty {{ font-size:14px; color:#888; }}
.hx-ep {{ font-size:17px; font-weight:800; color:#111; margin:26px 0 10px; line-height:1.35; }}
.hx-qa {{ border:1px solid #ececec; background:#fafafa; border-radius:12px; padding:16px 18px; margin:0 0 10px; }}
.hx-q {{ font-size:16px; font-weight:700; color:#111; line-height:1.4; margin:0 0 6px; }}
.hx-a {{ font-size:15px; line-height:1.6; color:#333; margin:0 0 10px; }}
.hx-foot {{ display:flex; flex-wrap:wrap; gap:14px; align-items:center; font-size:13px; }}
.hx-listen {{ font-weight:700; text-decoration:none; color:#1f5fbf; background:#eaf1fd; padding:5px 12px; border-radius:999px; }}
.hx-more {{ color:#777; }}
.hx-hidden {{ display:none; }}
</style>
<div class="questions-covered hx-wrap" id="answers">
  <h2 class="hx-title">{t["title"]}</h2>
  <p class="hx-stats">{stats}</p>
  {search}
  {"".join(sections)}
</div>
<script>
(function(){{var i=document.querySelector('.hx-search');if(!i)return;var e=document.querySelector('.hx-empty');
i.addEventListener('input',function(){{var v=i.value.toLowerCase().trim(),any=false;
document.querySelectorAll('.hx-qa').forEach(function(a){{var ok=!v||a.textContent.toLowerCase().indexOf(v)>-1;a.classList.toggle('hx-hidden',!ok);if(ok)any=true;}});
document.querySelectorAll('.hx-episode').forEach(function(s){{s.classList.toggle('hx-hidden',!s.querySelector('.hx-qa:not(.hx-hidden)'));}});
if(e)e.hidden=any;}});}})();
</script>
"""


def apply_hub_index(n1_path, podcast, published):
    """Remplace (ou insere) le bloc hub-index dans la fiche N1. Renvoie True si la page a change."""
    if not os.path.exists(n1_path):
        return False
    with open(n1_path, encoding="utf-8") as f:
        original = f.read()
    page = original
    if START_MARKER in page and END_MARKER in page:
        page = page.split(START_MARKER)[0] + page.split(END_MARKER, 1)[1]

    entries = visible_entries(published)
    if not entries:
        new = page
    else:
        block = START_MARKER + render_hub_index(podcast, published) + END_MARKER
        cta = re.search(r'<div class="cta-row">.*?</div>', page, flags=re.DOTALL)
        if len(entries) >= HUB_TOP_THRESHOLD and cta:
            new = page[:cta.end()] + "\n" + block + page[cta.end():]
        elif "</main>" in page:
            new = page.replace("</main>", block + "\n</main>", 1)
        elif "</body>" in page:
            new = page.replace("</body>", block + "\n</body>", 1)
        else:
            new = page + block
    if new == original:
        return False
    with open(n1_path, "w", encoding="utf-8") as f:
        f.write(new)
    return True

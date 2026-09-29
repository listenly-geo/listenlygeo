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
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import moments_index as mi   # lien question -> lecteur au bon moment (ecouter.html)
except Exception:                # jamais bloquant : sans lui, le bouton renvoie vers la fiche podcast Listenly
    mi = None

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
        "listen_ep": "▶ Écouter l'épisode",
        "full": "Réponse complète →",
        "show_all": "Voir les {n} réponses",
        "none": "Aucune réponse ne correspond à cette recherche.",
    },
    "en": {
        "title": "Answers from this podcast",
        "stats": "{n} question{s} answered · {e} episode{es} indexed",
        "search": "Search the {n} answers in this podcast…",
        "listen": "▶ Listen to this moment",
        "listen_ep": "▶ Listen to the episode",
        "full": "Full answer →",
        "show_all": "Show all {n} answers",
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


ENGINE_QUEUE = "automation/marketforge_engine/queue.json"


def engine_slugs():
    """Podcasts suivis par le MarketForge Engine (extraction pure, sans fiche question)."""
    try:
        with open(ENGINE_QUEUE, encoding="utf-8") as f:
            return set(json.load(f).get("podcasts", {}).keys())
    except (OSError, ValueError):
        return set()


PROSPECT_STATS = "automation/marketforge_engine/prospection_stats.json"
ENGINE_CONFIG = "automation/marketforge_engine/config.json"


def _prospects():
    """slug -> (statut, date du 1er envoi 'YYYY-MM-DD') d'apres le suivi du Google Sheet."""
    try:
        with open(PROSPECT_STATS, encoding="utf-8") as f:
            rows = json.load(f).get("prospects") or []
    except (OSError, ValueError):
        return {}
    return {r.get("slug"): (r.get("statut") or "", str(r.get("envoye_le") or "")[:10]) for r in rows if r.get("slug")}


def extraction_allowed(slug, queue_status="", today=None, delay=None):
    """Regle 29/09/2026 : 0 question cote prospect. L'extraction (et l'affichage des Q/R sur le hub)
    ne demarre que 7 jours apres le 1er mail sans reponse. Jamais pour un prospect qui a repondu
    (Etienne gere lui-meme). Immediate pour les podcasts qui ne seront jamais contactes
    (sans email, email invalide / risque, rebond, deja en prospection)."""
    import datetime as _dt
    if delay is None:
        try:
            with open(ENGINE_CONFIG, encoding="utf-8") as f:
                delay = int(json.load(f).get("extraction_apres_jours", 7))
        except (OSError, ValueError, TypeError):
            delay = 7
    today = today or _dt.date.today()
    rec = _prospects().get(slug)
    if rec:
        statut, sent = rec
        if statut in ("Repondu", "Pret"):
            return False
        if statut in ("Envoye", "Relance"):
            try:
                return bool(sent) and _dt.date.fromisoformat(sent) <= today - _dt.timedelta(days=delay)
            except ValueError:
                return False
        return True   # Rebond, Email invalide, Email risque, Deja en prospection...
    return queue_status == "sans_email"


def _snippet(text, limit=360):
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def merge_extracted(slug, published):
    """MarketForge Engine (27/09/2026) : pour les podcasts de la file d'extraction, le hub affiche
    aussi les Q/R extraites (knowledge moments) qui n'ont pas encore de fiche question. Quand une
    fiche est publiee plus tard pour la meme question, c'est l'entree publiee (avec son lien
    « Reponse complete ») qui prend le relais. Sans effet pour les autres podcasts."""
    if slug not in engine_slugs():
        return published
    if slug in _prospects() and not extraction_allowed(slug):
        return published   # prospect en cours : 0 question extraite affichee (ne pas l'embrouiller)
    known = {_norm(p.get("question")) for p in published}
    extra = []
    for path in sorted(glob.glob(f"{KNOWLEDGE_DIR}/{glob.escape(slug)}--*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                moments = json.load(f)
        except (OSError, ValueError):
            continue
        for m in moments if isinstance(moments, list) else []:
            q = (m.get("question") or "").strip()
            if not q or _norm(q) in known or not m.get("transcript_excerpt"):
                continue
            known.add(_norm(q))
            extra.append({
                "question": q,
                "answer_snippet": _snippet(m.get("transcript_excerpt")),
                "source_episode_title": m.get("episode_title") or "",
                "start_seconds": m.get("start_seconds") or 0,
                "url": "",
                "added_date": "",
            })
    return list(published) + extra


def consolidated_urls():
    try:
        with open(f"{PAGES_DIR}/data/consolidated_questions.json", encoding="utf-8") as f:
            return {"https://listenly.fr/podcast-btb/" + x for x in json.load(f).get("paths", [])}
    except (OSError, ValueError):
        return set()


FULL_ANSWERS_FILE = f"{PAGES_DIR}/data/consolidated_full_answers.json"
_SKIP_PARA_PREFIXES = ("← ", "see the ", "listen to the episode", "written by the listenly",
                       "écouter", "écrit par l'équipe listenly")


def _load_full_answers():
    try:
        with open(FULL_ANSWERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_full_answers(cache):
    with open(FULL_ANSWERS_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
        f.write("\n")


def _strip_balanced_divs(body, class_pattern):
    """Retire les <div class="...class_pattern...">...</div> en comptant les <div>/</div>
    imbriques (ex. source-badge contient un div.avatar) -- un simple .*?</div> non-greedy
    s'arreterait au premier sous-div ferme et laisserait fuir le reste du bloc."""
    open_re = re.compile(r"<div[^>]*class=[\"'][^\"']*(?:" + class_pattern + r")[^\"']*[\"'][^>]*>", re.IGNORECASE)
    tag_re = re.compile(r"<(/?)div\b[^>]*>", re.IGNORECASE)
    out, pos = [], 0
    while True:
        m = open_re.search(body, pos)
        if not m:
            out.append(body[pos:])
            break
        out.append(body[pos:m.start()])
        depth, end_pos = 1, len(body)
        for tm in tag_re.finditer(body, m.end()):
            depth += -1 if tm.group(1) else 1
            if depth == 0:
                end_pos = tm.end()
                break
        pos = end_pos
    return "".join(out)


def extract_full_answer_paragraphs(rel_path, question=""):
    """Recupere le vrai contenu (paragraphes, sous-titres, citation, key takeaways) de la
    fiche question standalone avant qu'elle ne soit 301-ee vers le hub (29/09/2026) --
    sinon la question consolidee ne laisse dans le hub que l'extrait de 160 caracteres
    (answer_snippet), sans aucun moyen d'en lire la reponse complete. Le HTML de chaque
    fiche est genere librement par Claude (pas de template fixe), donc extraction robuste
    par nettoyage plutot que par selecteurs de classes precis."""
    path = f"{PAGES_DIR}/{rel_path}"
    try:
        with open(path, encoding="utf-8") as f:
            src = f.read()
    except OSError:
        return None
    m = re.search(r"<body[^>]*>(.*)</body>", src, re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    body = m.group(1)
    body = re.sub(r"<header\b.*?</header>", "", body, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r"<div[^>]*\bid=[\"']semantic-index[\"'].*?</div>", "", body, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r"<(script|style)\b.*?</\1>", "", body, flags=re.DOTALL | re.IGNORECASE)
    # bloc "See also / Voir aussi" (liens + teasers vers D'AUTRES questions) present sur la
    # quasi-totalite des fiches -- tout ce qui suit ce titre n'est jamais la reponse a CETTE
    # question, donc on tronque le corps a cet endroit plutot que de le laisser fuiter.
    m_sa = re.search(r"<h2\b[^>]*>\s*(?:see also|voir aussi)\s*</h2>", body, re.IGNORECASE)
    if m_sa:
        body = body[:m_sa.start()]
    # variantes sans <header> propre (badge/breadcrumb/date directement dans le body) :
    # metadata de navigation, pas de la reponse -- a retirer avant le decoupage en paragraphes.
    body = _strip_balanced_divs(body, "source-badge|header-top")
    body = re.sub(r"<(?:p|div)[^>]*class=[\"'][^\"']*(?:breadcrumb|article-meta|meta-line|page-footer)[^\"']*[\"'][^>]*>.*?</(?:p|div)>",
                  "", body, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    # le <h1> ne fait que reformuler la question (parfois mot pour mot, parfois paraphrase) --
    # deja affichee comme titre de la carte (h3), donc toujours retire plutot que deduplique
    # au texte pres (les deux formulations different trop souvent pour un match exact fiable).
    body = re.sub(r"<h1\b.*?</h1>", "", body, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r"</(p|h2|h3|h4|li|blockquote|figcaption)>", "\x00", body, flags=re.IGNORECASE)
    body = re.sub(r"<br\s*/?>", "\x00", body, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", body)
    text = html.unescape(text)
    q_norm = re.sub(r"\s+", " ", question or "").strip().lower()
    out = []
    for chunk in text.split("\x00"):
        p = re.sub(r"\s+", " ", chunk).strip()
        if len(p) < 20:
            continue
        low = p.lower()
        if low.startswith(_SKIP_PARA_PREFIXES) or "listen to the episode" in low[:40]:
            continue
        if q_norm and low.rstrip("?. ") == q_norm.rstrip("?. "):
            continue  # h1 qui repete la question -- deja affichee comme titre de la carte
        out.append(p)
    return out or None


STYLE_CONFIG = "pages/podcast-btb/hub_style.json"   # {"slugs": [...]} ou {"slugs": "*"} : fiches au style Apple (29/09/2026)
STYLE_LINK = '<link rel="stylesheet" href="/podcast-btb/hub.css?v=2" id="hub-style">'
HUB_VISIBLE = 10          # questions visibles avant "Show all" (style Apple)


def apple_enabled(n1_path):
    try:
        with open(STYLE_CONFIG, encoding="utf-8") as f:
            slugs = json.load(f).get("slugs", [])
    except (OSError, ValueError):
        return False
    base = os.path.basename(n1_path)
    if base.endswith("-podcast.html"):
        base = base[:-len("-podcast.html")]
    return slugs == "*" or base in slugs


def visible_entries(published):
    excluded = load_excluded_urls()
    return [p for p in published if p.get("url", "").replace("https://listenly.fr", "") not in excluded]


def render_hub_index(podcast, published, apple=False):
    lang = "en" if podcast.get("language") == "en" else "fr"
    t = STRINGS[lang]
    merged = consolidated_urls()
    full_cache = _load_full_answers()
    cache_dirty = False

    def _expand(p):
        if p.get("url") not in merged:
            return p
        rel_path = p["url"].replace("https://listenly.fr/podcast-btb/", "")
        nonlocal cache_dirty
        if rel_path not in full_cache:
            paras = extract_full_answer_paragraphs(rel_path, p.get("question", ""))
            full_cache[rel_path] = paras or []
            cache_dirty = True
        d = dict(p, url="")
        if full_cache.get(rel_path):
            d["full_paragraphs"] = full_cache[rel_path]
        return d

    entries = [_expand(p) for p in visible_entries(published)]
    if cache_dirty:
        _save_full_answers(full_cache)
    stamps = load_timestamps(podcast["slug"])
    target = listen_url(podcast)
    moment_lk = mi.lookup(podcast["slug"]) if mi else None

    episodes = {}
    for p in sorted(entries, key=lambda x: x.get("added_date", ""), reverse=True):
        episodes.setdefault(p.get("source_episode_title") or "", []).append(p)

    n, e = len(entries), len(episodes)
    large = n >= HUB_TOP_THRESHOLD
    used = set()

    sections = []
    chips = []
    collapse = apple and n > HUB_VISIBLE + 2
    shown = 0
    for ep_title, items in episodes.items():
        ep_anchor = "ep-" + _anchor(ep_title, used)
        chips.append(f'<a class="hx-chip" href="#{ep_anchor}">{_E(ep_title[:70])} <span>{len(items)}</span></a>')
        cards = []
        for p in items:
            q_anchor = _anchor(p.get("question"), used)
            seconds = p.get("start_seconds") or stamps.get(_norm(p.get("question")))
            when = _fmt_time(seconds)
            listen_label = t["listen"] + (f" · {when}" if when else "")
            href = target
            res = mi.resolve_entry(podcast["slug"], p.get("question"), p.get("source_episode_title"), moment_lk) if mi else None
            if res:   # lecteur integre au bon moment (29/09/2026) ; approx = episode connu, horodatage inconnu
                href = mi.page_url(podcast["slug"], res[0])
                if res[1]:
                    listen_label = t["listen_ep"]
            full_paras = p.get("full_paragraphs")
            if full_paras:
                # Question consolidee (301 vers le hub) : la reponse complete recuperee de
                # l'ancienne fiche remplace l'extrait tronque, sinon le contenu est perdu.
                answer_html = "".join(f'<p class="hx-a">{_E(para)}</p>' for para in full_paras)
            else:
                answer = _E(re.sub(r"\s+", " ", p.get("answer_snippet") or "").strip())
                answer_html = f'<p class="hx-a">{answer}</p>' if answer else ""
            shown += 1
            extra = " hx-extra" if collapse and shown > HUB_VISIBLE else ""
            cards.append(
                f'<article class="hx-qa{extra}" id="{q_anchor}">'
                f'<h3 class="hx-q">{_E(p.get("question", ""))}</h3>'
                + answer_html
                + '<div class="hx-foot">'
                f'<a class="hx-listen plausible-event-name=Clic+Hub+Moment" href="{_E(href)}">{listen_label}</a>'
                + (f'<a class="hx-more" href="{_E(p.get("url", ""))}">{t["full"]}</a>' if p.get("url") else "")
                + "</div></article>"
            )
        heading = f'<h3 class="hx-ep" id="{ep_anchor}">{_E(ep_title)}</h3>' if ep_title else ""
        ep_extra = " hx-extra" if collapse and shown - len(items) >= HUB_VISIBLE else ""
        sections.append(f'<section class="hx-episode{ep_extra}">{heading}{"".join(cards)}</section>')

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

    apple_js = """(function(){var w=document.getElementById('answers'),b=document.getElementById('hx-showall');
function open(){if(w)w.classList.remove('hx-collapsed');if(b)b.style.display='none';}
if(b)b.addEventListener('click',open);
document.querySelectorAll('.hx-chip').forEach(function(c){c.addEventListener('click',open);});
if(location.hash&&document.querySelector('.hx-extra'+location.hash))open();})();
""" if apple else ""
    apple_input = "if(i.value.trim()){var w=document.getElementById('answers');if(w)w.classList.remove('hx-collapsed');var b=document.getElementById('hx-showall');if(b)b.style.display='none';}" if apple else ""
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
<div class="questions-covered hx-wrap{" hx-collapsed" if collapse else ""}" id="answers">
  <h2 class="hx-title">{t["title"]}</h2>
  <p class="hx-stats">{stats}</p>
  {search}
  {"".join(sections)}{f'<button type="button" class="hx-showall" id="hx-showall">{_E(t["show_all"].format(n=n))}</button>' if collapse else ""}
</div>
<script>
{apple_js}(function(){{var i=document.querySelector('.hx-search');if(!i)return;var e=document.querySelector('.hx-empty');
i.addEventListener('input',function(){{{apple_input}var v=i.value.toLowerCase().trim(),any=false;
document.querySelectorAll('.hx-qa').forEach(function(a){{var ok=!v||a.textContent.toLowerCase().indexOf(v)>-1;a.classList.toggle('hx-hidden',!ok);if(ok)any=true;}});
document.querySelectorAll('.hx-episode').forEach(function(s){{s.classList.toggle('hx-hidden',!s.querySelector('.hx-qa:not(.hx-hidden)'));}});
if(e)e.hidden=any;}});}})();
</script>
"""


def apply_hub_index(n1_path, podcast, published):
    """Remplace (ou insere) le bloc hub-index dans la fiche N1. Renvoie True si la page a change."""
    published = merge_extracted(podcast.get("slug", ""), published)
    if not os.path.exists(n1_path):
        return False
    with open(n1_path, encoding="utf-8") as f:
        original = f.read()
    page = original
    if START_MARKER in page and END_MARKER in page:
        pre = page.split(START_MARKER)[0]
        post = page.split(END_MARKER, 1)[1]
        # Le bloc est toujours insere suivi d'un saut de ligne : on le retire avec lui, pour qu'une
        # reecriture a contenu identique laisse la page strictement inchangee.
        if post.startswith("\n"):
            post = post[1:]
        page = pre.rstrip("\n") + "\n" + post if pre.endswith("\n") else pre + post

    entries = visible_entries(published)
    if not entries:
        new = page
    else:
        block = START_MARKER + render_hub_index(podcast, published, apple_enabled(n1_path)) + END_MARKER
        cta = re.search(r'<div class="cta-row">.*?</div>', page, flags=re.DOTALL)
        if len(entries) >= HUB_TOP_THRESHOLD and cta:
            new = page[:cta.end()] + "\n" + block + "\n" + page[cta.end():].lstrip("\n")
        elif "</main>" in page:
            new = page.replace("</main>", block + "\n</main>", 1)
        elif "</body>" in page:
            new = page.replace("</body>", block + "\n</body>", 1)
        else:
            new = page + block
    # feuille de style commune (style Apple) : lien place en fin de <head>, apres les styles de la page
    new = re.sub(r'\n?<link rel="stylesheet" href="/podcast-btb/hub\.css[^>]*id="hub-style">', "", new)
    if entries and apple_enabled(n1_path) and "</head>" in new:
        new = new.replace("</head>", STYLE_LINK + "\n</head>", 1)
    if new == original:
        return False
    with open(n1_path, "w", encoding="utf-8") as f:
        f.write(new)
    return True

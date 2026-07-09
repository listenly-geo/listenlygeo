#!/usr/bin/env python3
"""
Génère une fiche PODCAST-BTB à partir d'un contenu brut (RSS collé, description,
titres d'épisodes...) + 3 liens fixes. Claude déduit lui-même nom du podcast,
hôte, titre, entreprise, thématiques et catégorie à partir du texte brut.

Variables requises :
  ANTHROPIC_API_KEY
  PODCAST_RAW_INFO   — contenu brut collé (RSS, description, titres d'épisodes...)
  PODCAST_URL        — lien Spotify/plateforme (CTA 1)
  CONTACT_URL        — lien LinkedIn de l'hôte (CTA 2)
  LISTENLY_URL       — lien Listenly (backlink canonical)
Optionnelles :
  PODCAST_SLUG       — sinon déduit automatiquement du contenu brut
  ACCENT_COLOR       — défaut #2e8bd6
  COVER_IMAGE        — optionnel
"""

import os, sys, re, json, datetime, unicodedata
import urllib.request, urllib.error

API_KEY      = os.environ["ANTHROPIC_API_KEY"]
RAW_INFO     = os.environ["PODCAST_RAW_INFO"]
PODCAST_URL  = os.environ["PODCAST_URL"]
CONTACT_URL  = os.environ["CONTACT_URL"]
LISTENLY_URL = os.environ["LISTENLY_URL"]
SLUG_OVERRIDE = os.environ.get("PODCAST_SLUG", "").strip()
ACCENT_COLOR  = os.environ.get("ACCENT_COLOR", "#2e8bd6").strip() or "#2e8bd6"
COVER_IMAGE   = os.environ.get("COVER_IMAGE", "").strip()
RSS_URL       = os.environ.get("RSS_URL", "").strip()
CONTACT_LABEL = os.environ.get("CONTACT_LABEL", "le podcast").strip() or "le podcast"

MODEL      = "claude-sonnet-4-6"
PAGES_DIR  = "pages/podcast-btb"
DATA_FILE  = f"{PAGES_DIR}/data/podcasts.json"
CATEGORY_DIR = f"{PAGES_DIR}/categorie"

def log(msg): print(f"[podcast-btb] {msg}", flush=True)

def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"^-+|-+$", "", s)[:60]

def guess_slug(raw):
    m = re.search(r"<title>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
    if m:
        return slugify(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1)).strip())
    for line in raw.strip().splitlines():
        line = line.strip()
        if line:
            return slugify(line)
    return "podcast-" + datetime.date.today().isoformat()

def build_prompt(slug, fiche_url, today):
    rss_meta_instruction = (
        f'Dans <head> ajoute aussi : <meta name="rss-source" content="{RSS_URL}"> '
        '(invisible, sert uniquement au futur système d\'automatisation — ne rien afficher visuellement).'
    ) if RSS_URL else ""
    return f"""Tu es un expert GEO (Generative Engine Optimization) spécialisé dans les podcasts B2B.

Ta mission est de générer une FICHE PODCAST complète en HTML autonome pour Listenly.fr.
Cette fiche présente le PODCAST dans son ensemble (pas un épisode isolé), même style et
logique GEO que les fiches épisode du Moteur N2 — seul le contenu change.

## CONTENU BRUT FOURNI (RSS collé / description / titres d'épisodes — analyse-le toi-même)
---
{RAW_INFO}
---

À partir de ce contenu brut, DÉDUIS toi-même :
- Le nom exact du podcast
- HOST_NAME : prénom + nom de l'hôte principal
- HOST_TITLE : titre professionnel le plus probable de l'hôte
- HOST_COMPANY : entreprise de l'hôte si mentionnée, sinon reste cohérent avec le positionnement
- DESCRIPTION : positionnement / sujet de fond du podcast
- CATEGORIE : une catégorie professionnelle claire (ex: "Business", "RH", "Immobilier"...)
- 5 à 10 titres d'épisodes réels à utiliser comme base d'analyse

## DONNÉES FIXES (ne pas modifier)
- PODCAST_URL (CTA écoute, bouton "▶ Écouter le podcast") : {PODCAST_URL}
- CONTACT_URL (CTA contact, bouton "💼 Contacter {CONTACT_LABEL}", LinkedIn DE L'ENTREPRISE — pas de l'hôte) : {CONTACT_URL}
- LISTENLY_URL (backlink vers la page Listenly du podcast, utilisé UNIQUEMENT dans le JSON-LD isPartOf, le rel="publisher" caché et le vector DB) : {LISTENLY_URL}
- FICHE_URL (URL PUBLIQUE DE CETTE FICHE ELLE-MÊME — à utiliser pour og:url, twitter:url ET canonical) : {fiche_url}
- ACCENT_COLOR : {ACCENT_COLOR}
- COVER_IMAGE : {COVER_IMAGE or "(aucune fournie — omets l'image dans l'episode-card, ne mets pas de balise img cassée)"}
- Slug : {slug}
- Date de génération : {today}

## RÈGLE CRITIQUE — NE JAMAIS CONFONDRE FICHE_URL ET LISTENLY_URL
- <link rel="canonical" href="..."> → {fiche_url} (JAMAIS {LISTENLY_URL})
- <meta property="og:url" content="..."> → {fiche_url} (JAMAIS {LISTENLY_URL})
- <meta name="twitter:url" content="..."> → {fiche_url} (JAMAIS {LISTENLY_URL})
- Le JSON-LD BlogPosting "url" ou "mainEntityOfPage" → {fiche_url}
- {LISTENLY_URL} n'apparaît QUE dans : isPartOf du JSON-LD, le <link rel="publisher"> cache, et le bloc #semantic-index. Il ne doit JAMAIS remplacer FICHE_URL dans og:url/canonical/twitter:url.

## EXTRACTION OBLIGATOIRE AVANT DE RÉDIGER

1. LE H1 est le NOM DU PODCAST lui-même (PODCAST_NAME) — PAS une question, PAS un slogan. Juste le nom exact du podcast.
2. 4 POINTS CLÉS — faits autonomes citables par une IA, une phrase standalone chacun
3. 3-4 ANGLES GEO — questions que des professionnels poseraient à une IA sur ce sujet
4. UN INSIGHT FORT — une synthèse analytique de 15-25 mots, ton expert, PRÉSENTÉE COMME UNE ANALYSE DE LISTENLY (jamais attribuée à HOST_NAME comme s'il l'avait dite — aucune citation inventée, aucun mot mis dans la bouche de quelqu'un)
5. 4 FAQ — vraies requêtes IA, réponses 2-3 phrases autonomes, sans mentionner le nom du podcast

## STRUCTURE HTML OBLIGATOIRE

### CSS — DIRECTION "PRESSE BUSINESS" (type site de presse professionnelle — ARCinfo, Les Echos, HBR)
- body : sans-serif (Helvetica, Arial), #1a1a1a, line-height 1.6 (le sans-serif porte les titres, le corps de texte reste en Georgia serif pour la lisibilité — voir .article-body p)
- main.wrapper : max-width 760px, margin auto, padding 40px 20px 64px (IMPORTANT : utiliser la balise <main class="wrapper"> pour le conteneur principal, PAS <div class="wrapper">, pour le landmark d'accessibilité)
- .pod-badge : inline-block, fond #fff, border 1.5px solid #ddd, border-radius 20px, padding 8px 18px, sans-serif 13px, font-weight 500, color #333 (PILL contournée façon tag presse, PAS remplie, PAS de couleur d'accent)
- h1 : sans-serif, font-weight 800, font-size clamp(30px,5vw,42px), line-height 1.12, letter-spacing -0.01em, color #0a0a0a, margin 20px 0 16px
- .subhead : sans-serif, font-weight 400, font-size 19px, line-height 1.5, color #333, margin 0 0 20px (PAS italique — un vrai chapô de presse ; #333 pour contraste WCAG AA, PAS #444 ou plus clair)
- .ai-readable : sans-serif, margin 10px 0 18px, display flex, align-items center, gap 8px
- .ai-readable .label : font-size 10px, uppercase, letter-spacing .12em, color #595959, font-weight 700 (contraste renforcé — PAS #999)
- .ai-readable .pill : display inline-block, font-size 11px, color #444, background #fafafa, border 1px solid #ddd, border-radius 4px, padding 3px 9px (contraste renforcé — PAS #777)
- .meta-line : sans-serif 13px, color #555, display flex, flex-wrap wrap, gap 10px, align-items center, padding 14px 0, border-top 1px solid #eee, border-bottom 1px solid #eee, margin 16px 0 24px (rappelle une ligne date+partage de presse ; #555 pour contraste WCAG AA, PAS #888)
- .hero-image : width 84px, height 84px, min-width 84px, object-fit cover, border-radius 18px, border 1px solid #eee, box-shadow 0 2px 6px rgba(0,0,0,0.06), display block (VIGNETTE compacte type cover art carrée — jamais pleine largeur, jamais étirée)
- .header-row : display flex, align-items center, gap 14px, margin-bottom 16px (aligne la vignette et le badge côte à côte)
- .cta-listen : background {ACCENT_COLOR}, color #fff, sans-serif 14px font-weight 600, padding 11px 22px, border-radius 4px (CTA principal — seul élément à porter la couleur d'accent pleine)
- .cta-contact : background #fff, color #222, border 1px solid #999, sans-serif 14px font-weight 600, padding 11px 22px, border-radius 4px (CTA secondaire — neutre, bordure renforcée pour contraste)
- .divider : border-top 1px solid #eee
- .lead-label : sans-serif 10px, font-weight 700, uppercase, letter-spacing .1em, color #595959 (contraste renforcé — PAS #999)
- .lead : font-family Georgia, font-size 19px, italic, border-left 2px solid #ccc, padding-left 20px, color #1a1a1a
- .key-box : background #fafafa, border 1px solid #eee, border-radius 6px, padding 24px 28px
- .key-box li : padding-left 24px, ::before content "→" color #555 (contraste renforcé — PAS #999)
- .article-body h2 : sans-serif, font-weight 800, font-size clamp(24px,3.5vw,30px), line-height 1.2, color #0a0a0a, margin-top 48px, margin-bottom 4px (GROS titre bold impactant, façon intertitre de presse — PAS petit uppercase discret)
- .article-body p : font-family Georgia, serif, font-size 17px, line-height 1.75, color #2a2a2a (corps de texte en serif classique, contraste avec les titres sans-serif)
- .quote-block : position relative, padding 24px 28px 24px 52px, border-left 2px solid #ccc, bg #fafafa, font-family Georgia, italic 17px, color #1a1a1a — ajoute un grand guillemet typographique (") en position absolue top-left, font-size 48px, color #ccc, font-family Georgia, line-height 1, décoratif
- .faq-item h3 : sans-serif, 17px, font-weight 700, color #111
- .episode-card : border 1px solid #e5e5e5, border-radius 6px, flex, padding 20px
- .episode-card img : width 110px, object-fit cover, border-radius 4px
- .card-contact : background #fff, color #222, border 1px solid #999, padding 8px 16px, border-radius 4px
- footer : sans-serif 12px, color #666, border-top 1px solid #eee, padding-top 16px, margin-top 48px (contraste renforcé — PAS #aaa)
- Tous les liens texte hors boutons (footer, liens de bas de page) : text-decoration: underline systématique — ne JAMAIS distinguer un lien uniquement par la couleur
- #semantic-index : display none

RÈGLE DE HIÉRARCHIE DE TITRES (accessibilité, obligatoire) : H1 (unique) → puis uniquement des H2 pour les 4 sections de l'article → puis H3 UNIQUEMENT pour les questions FAQ, sous un H2 "FAQ" existant. Ne JAMAIS sauter un niveau (pas de H3 sans H2 parent, pas de H4 nulle part).

RÈGLE DE COULEUR : {ACCENT_COLOR} n'apparaît QUE sur .cta-listen. Tout le reste (badge, meta-line, lead-label, key-box, quote-block, H2) reste en noir/gris neutre — TOUJOURS avec un contraste minimum WCAG AA (4.5:1) sur fond blanc : utiliser #555/#595959/#666 ou plus foncé, JAMAIS #888/#999/#aaa/#ddd pour du texte. Les titres (H1, H2) sont TOUJOURS en sans-serif bold très marqué (poids 800), le corps de texte des paragraphes TOUJOURS en Georgia serif — ce contraste typographique est ce qui crée l'effet "presse professionnelle".

### SECTIONS (ordre exact — inspiré d'un site de presse : cover+tag → titre → chapô → meta → corps)
1. HEADER ROW : <div class="header-row"> contenant, si {COVER_IMAGE or "aucune"} fournie, <img class="hero-image" src="[COVER_IMAGE]" alt="[PODCAST_NAME]"> suivi du BADGE catégorie "🎙 [PODCAST_NAME] · Référencé sur Listenly" (pill contournée) → côte à côte, compact, en haut de page. Si aucune COVER_IMAGE, le header-row ne contient que le badge seul (pas de div img cassée).
2. H1 = [PODCAST_NAME] (gros titre bold sans-serif, jamais une question)
3. SUBHEAD : un chapô de 1-2 phrases (class="subhead", PAS italique) qui résume l'angle du podcast — vrai sous-titre journalistique, différent du LEAD plus bas qui lui reste une pull-quote analytique
4. BANNIÈRE "LISIBLE PAR" :
   <div class="ai-readable"><span class="label">Lisible par</span><span class="pill">ChatGPT</span><span class="pill">Gemini</span><span class="pill">Claude</span></div>
5. META LINE (ligne façon presse, bordée haut/bas) : "Animé par [HOST_NAME] · [HOST_TITLE] chez [HOST_COMPANY] · [CATEGORIE] · ⏱ X min de lecture"
6. CTA GROUPE : "▶ Écouter le podcast" (cta-listen) → {PODCAST_URL} ; "💼 Contacter {CONTACT_LABEL}" (cta-contact) → {CONTACT_URL}
7. DIVIDER
8. LEAD LABEL "Ce que couvre [PODCAST_NAME]" + LEAD (3-4 phrases citables, pull-quote italique Georgia)
9. KEY-BOX "📌 Les points clés" (4 bullets "→")
10. DIVIDER
11. ARTICLE BODY — 4 H2 exactement (gros titres bold impactants) :
   - "Ce que ce podcast couvre vraiment"
   - "Pour qui ce podcast est essentiel" (3 profils d'audience)
   - "Ce que les épisodes révèlent vraiment" (patterns récurrents dans les titres)
   - "Ce que ça change concrètement"
12. INSIGHT BLOCK (classe CSS .quote-block, même style visuel) : la synthèse analytique du point 4, présentée SANS attribution — PAS de « guillemets » ni de tiret suivi d'un nom, juste le texte analytique en italique dans le bloc. Ne jamais faire croire que ce sont des propos réellement tenus par [HOST_NAME].
13. CTA MID discret "Découvrir tous les épisodes de [PODCAST_NAME]" → {PODCAST_URL}
14. DIVIDER
15. FAQ "❓ Le podcast répond à ces questions" (4 Q/R) + JSON-LD FAQPage obligatoire (mêmes questions). N'utilise JAMAIS la formulation "on répond" — toujours "le podcast répond" ou "il répond".
16. EPISODE CARD bas de page : cover si {COVER_IMAGE or "aucune"}, "Découvrir [PODCAST_NAME]", sous-titre [HOST_NAME] · [PODCAST_NAME], card-listen → {PODCAST_URL}, card-contact "💼 Contacter {CONTACT_LABEL}" → {CONTACT_URL}
16. FOOTER : © [PODCAST_NAME] — [HOST_COMPANY] + lien "Analyse structurée par Listenly" → https://listenly.fr (dofollow, color #ccc)

## JSON-LD OBLIGATOIRE (dans <head>)
@graph : BlogPosting (headline=H1, author=[HOST_NAME]/[HOST_TITLE], publisher=Listenly, isPartOf={LISTENLY_URL}, speakable cssSelector [".lead",".key-box"]), FAQPage (les 4 questions), Person ([HOST_NAME]/[HOST_TITLE]/worksFor [HOST_COMPANY], sameAs: ["{CONTACT_URL}"]), PodcastSeries ([PODCAST_NAME]/{PODCAST_URL}, sameAs: ["{PODCAST_URL}", "{LISTENLY_URL}"]).
IMPORTANT sameAs : sert à relier l'entité (personne/podcast) à ses profils réels ailleurs sur le web (autorité d'entité pour les moteurs IA/Google). N'invente JAMAIS d'URL sameAs — utilise UNIQUEMENT {CONTACT_URL}, {PODCAST_URL} et {LISTENLY_URL} tels que fournis, jamais un profil supposé ou reconstitué.

## BACKLINKS LISTENLY CACHÉS (obligatoires)
Dans <head> : canonical={fiche_url} (PAS {LISTENLY_URL} — voir RÈGLE CRITIQUE plus haut), rel="publisher" href="https://listenly.fr", meta name="data-provider" content="Listenly".
{rss_meta_instruction}
Dans <body> fin : #semantic-index avec entity [PODCAST_NAME], entity [HOST_NAME], entity [HOST_COMPANY], concept [CATEGORIE], publisher Listenly.fr, isPartOf {LISTENLY_URL}.

## RÈGLES DE QUALITÉ ABSOLUES
- Chaque phrase du .lead doit être citable seule par une IA
- Les bullets key-box doivent être des faits, pas des descriptions
- Les FAQ répondent sans mentionner le nom du podcast
- Le H1 est TOUJOURS le nom du podcast, jamais une question
- Le libellé de la section FAQ est TOUJOURS "❓ Le podcast répond à ces questions" — jamais "on répond"
- Aucune formulation creuse type "un podcast incontournable", aucun jargon marketing vide
- Le contenu doit montrer que tu as analysé les vrais sujets du podcast

IMPORTANT : Réponds UNIQUEMENT avec le code HTML complet, depuis <!DOCTYPE html> jusqu'à </html>. Aucun texte avant ou après, aucun markdown, aucun backtick."""

def call_claude(prompt):
    payload = {"model": MODEL, "max_tokens": 14000, "messages": [{"role": "user", "content": prompt}]}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=data,
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())
    parts = [b.get("text", "") for b in result.get("content", []) if b.get("type") == "text"]
    return "".join(parts).strip()

def clean_html(text):
    text = re.sub(r"^```html\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

def audit(html, fiche_url):
    issues = []
    if html.count("<h1") != 1: issues.append("H1 absent ou multiple")
    if "semantic-index" not in html: issues.append("vector DB absente")
    if "FAQPage" not in html: issues.append("FAQPage absente")
    if "speakable" not in html: issues.append("speakable absent")
    if "pod-badge" not in html: issues.append("badge absent")
    if "key-box" not in html: issues.append("key-box absente")
    if "quote-block" not in html: issues.append("quote-block absent")
    if PODCAST_URL not in html: issues.append("CTA podcast absent")
    if CONTACT_URL not in html: issues.append("CTA contact absent")
    if "on répond" in html.lower() or "on repond" in html.lower(): issues.append("formulation 'on répond' interdite trouvée")
    if f'og:url" content="{fiche_url}"' not in html: issues.append("og:url ne pointe pas vers la fiche elle-même")
    if f'rel="canonical" href="{fiche_url}"' not in html: issues.append("canonical ne pointe pas vers la fiche elle-même")
    if "sameAs" not in html: issues.append("sameAs absent (Person/PodcastSeries)")
    return issues

def clean_text(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&amp;", "&").replace("&nbsp;", " ")
          .replace("&#39;", "'").replace("&rsquo;", "'").replace("&quot;", '"'))
    return re.sub(r"\s+", " ", s).strip()

def category_slug(cat):
    return slugify(cat) or "general"

def extract_fiche_meta(html, slug, fiche_url):
    h1m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    podcast_name = clean_text(h1m.group(1)) if h1m else slug

    host_name = host_title = host_company = categorie = ""
    meta_block = re.search(r'class="meta-line"[^>]*>(.*?)</(?:div|p)>', html, re.DOTALL)
    if meta_block:
        meta_text = clean_text(meta_block.group(1))
        m = re.search(r"Animé par (.+?)\s*·\s*(.+?)\s*chez\s*(.+?)\s*·\s*(.+?)\s*·\s*⏱", meta_text)
        if m:
            host_name, host_title, host_company, categorie = [x.strip() for x in m.groups()]

    punchline = ""
    lead_block = re.search(r'class="lead"[^>]*>(.*?)</(?:div|p|blockquote)>', html, re.DOTALL)
    if lead_block:
        lead_text = clean_text(lead_block.group(1))
        parts = re.split(r"(?<=[.!?])\s", lead_text)
        punchline = parts[0].strip() if parts and parts[0].strip() else lead_text[:160]

    return {
        "slug": slug,
        "podcast_name": podcast_name or slug,
        "host_name": host_name,
        "host_title": host_title,
        "host_company": host_company,
        "categorie": categorie or "Général",
        "punchline": punchline,
        "fiche_url": fiche_url,
        "date": datetime.date.today().isoformat(),
    }

def append_category_link(html, categorie, cat_slug):
    link = (
        '\n<p style="max-width:720px;margin:0 auto;padding:0 20px 40px;'
        'font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#999;">'
        f'<a href="/podcast-btb/categorie/{cat_slug}.html" style="color:#999;text-decoration:underline;">'
        f'Voir tous les podcasts {categorie} référencés par Listenly →</a></p>\n'
    )
    if "</body>" in html:
        return html.replace("</body>", link + "</body>", 1)
    return html + link

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_data(records):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

BASE_STYLE = """
body{font-family:Georgia,serif;color:#1a1a1a;line-height:1.75;margin:0;background:#fff}
.wrapper{max-width:760px;margin:0 auto;padding:40px 20px 64px}
a{color:#2e6bd6}
.eyebrow{font-family:Helvetica,Arial,sans-serif;font-size:11px;font-weight:700;text-transform:uppercase;
  letter-spacing:.1em;color:#666;margin-bottom:10px}
h1{font-size:clamp(24px,4vw,34px);font-weight:700;color:#111;margin:0 0 24px}
h2{font-family:Helvetica,Arial,sans-serif;font-size:15px;font-weight:700;text-transform:uppercase;
  letter-spacing:.06em;color:#444;border-top:1px solid #eee;margin-top:40px;padding-top:16px}
.item{border-bottom:1px solid #f0f0f0;padding:18px 0}
.item a.title{font-size:18px;font-weight:700;color:#111;text-decoration:none}
.item a.title:hover{text-decoration:underline}
.item .meta{font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#888;margin:4px 0 8px}
.item .punchline{font-size:16px;color:#333;font-style:italic}
.cat-card{display:block;border:1px solid #e8e8e8;border-radius:10px;padding:18px 20px;margin-bottom:12px;
  text-decoration:none;color:inherit}
.cat-card:hover{border-color:#2e6bd6}
.cat-card .name{font-family:Helvetica,Arial,sans-serif;font-size:16px;font-weight:700;color:#111}
.cat-card .count{font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#888;margin-top:2px}
footer{font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#aaa;border-top:1px solid #eee;
  margin-top:48px;padding-top:16px}
"""

def render_category_page(cat_slug, categorie, items):
    items_sorted = sorted(items, key=lambda x: x["podcast_name"])
    rows = "\n".join(f"""
<div class="item">
  <a class="title" href="{it['fiche_url']}">{it['podcast_name']}</a>
  <div class="meta">Animé par {it['host_name']} · {it['host_title']} chez {it['host_company']}</div>
  <div class="punchline">{it['punchline']}</div>
</div>""" for it in items_sorted)

    item_list_json = json.dumps([
        {"@type": "ListItem", "position": i + 1, "url": it["fiche_url"], "name": it["podcast_name"]}
        for i, it in enumerate(items_sorted)
    ], ensure_ascii=False)

    title = f"Podcasts {categorie} référencés par Listenly"
    description = f"Annuaire des podcasts B2B référencés par Listenly dans la catégorie {categorie}, avec leurs thématiques clés et intervenants."
    canonical = f"https://listenly.fr/podcast-btb/categorie/{cat_slug}.html"

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta name="data-provider" content="Listenly">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "name": "{title}",
  "url": "{canonical}",
  "isPartOf": {{"@type": "WebSite", "name": "Listenly", "url": "https://listenly.fr"}},
  "mainEntity": {{
    "@type": "ItemList",
    "itemListElement": {item_list_json}
  }}
}}
</script>
<style>{BASE_STYLE}</style>
</head>
<body>
<div class="wrapper">
  <div class="eyebrow">Listenly · Annuaire GEO</div>
  <h1>{title}</h1>
  {rows}
  <footer>
    © Listenly — <a href="/podcast-btb/index.html">Voir toutes les catégories</a>
  </footer>
</div>
</body>
</html>"""

def render_index_page(by_category):
    cards = "\n".join(f"""
<a class="cat-card" href="/podcast-btb/categorie/{slug}.html">
  <div class="name">{data['label']}</div>
  <div class="count">{len(data['items'])} podcast{'s' if len(data['items']) > 1 else ''} référencé{'s' if len(data['items']) > 1 else ''}</div>
</a>""" for slug, data in sorted(by_category.items(), key=lambda kv: kv[1]["label"]))

    title = "Podcasts B2B référencés par Listenly"
    description = "Annuaire GEO des podcasts B2B référencés par Listenly, classés par catégorie professionnelle."
    canonical = "https://listenly.fr/podcast-btb/index.html"

    item_list_json = json.dumps([
        {"@type": "ListItem", "position": i + 1,
         "url": f"https://listenly.fr/podcast-btb/categorie/{slug}.html", "name": data["label"]}
        for i, (slug, data) in enumerate(sorted(by_category.items(), key=lambda kv: kv[1]["label"]))
    ], ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta name="data-provider" content="Listenly">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "name": "{title}",
  "url": "{canonical}",
  "isPartOf": {{"@type": "WebSite", "name": "Listenly", "url": "https://listenly.fr"}},
  "mainEntity": {{
    "@type": "ItemList",
    "itemListElement": {item_list_json}
  }}
}}
</script>
<style>{BASE_STYLE}</style>
</head>
<body>
<div class="wrapper">
  <div class="eyebrow">Listenly · Annuaire GEO</div>
  <h1>{title}</h1>
  {cards}
  <footer>© Listenly</footer>
</div>
</body>
</html>"""

def build_sitemap():
    """Scanne tout /pages/podcast-btb/ et régénère un sitemap XML à jour.
    Appelée par generate_podcast_btb.py ET generate_episode_fiches_btb.py
    pour rester synchronisée quel que soit le script qui tourne en dernier."""
    urls = []
    for root, dirs, files in os.walk(PAGES_DIR):
        dirs[:] = [d for d in dirs if d != "data"]
        for fname in files:
            if not fname.endswith(".html"):
                continue
            if fname == "historique.html":
                continue  # page interne perso, jamais dans le sitemap public
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, PAGES_DIR).replace(os.sep, "/")
            url = f"https://listenly.fr/podcast-btb/{rel_path}"
            mtime = datetime.date.fromtimestamp(os.path.getmtime(full_path)).isoformat()
            priority = "1.0" if fname == "index.html" and root == PAGES_DIR else \
                       "0.8" if "/categorie" in root or "/episodes" in root and fname == "index.html" else \
                       "0.6" if "/episodes/" in root else "0.9"
            urls.append((url, mtime, priority))

    entries = "\n".join(
        f'  <url>\n    <loc>{u}</loc>\n    <lastmod>{m}</lastmod>\n    <priority>{p}</priority>\n  </url>'
        for u, m, p in sorted(urls)
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{entries}\n'
        '</urlset>\n'
    )
    with open(f"{PAGES_DIR}/sitemap-podcast-btb.xml", "w", encoding="utf-8") as f:
        f.write(xml)
    log(f"Sitemap regenere : {len(urls)} URL(s)")

def build_historique():
    """Page interne (usage perso, jamais dans le sitemap) listant chaque fiche
    podcast et episode par ordre chronologique de creation."""
    entries = []

    records = load_data()
    for r in records:
        entries.append({
            "date": r.get("date", ""),
            "type": "Podcast",
            "name": r.get("podcast_name", r.get("slug", "")),
            "url": r.get("fiche_url", ""),
            "podcast": r.get("podcast_name", ""),
        })

    episodes_root = f"{PAGES_DIR}/episodes"
    if os.path.isdir(episodes_root):
        for slug in os.listdir(episodes_root):
            reg_file = f"{episodes_root}/{slug}/_generated.json"
            if not os.path.exists(reg_file):
                continue
            with open(reg_file, encoding="utf-8") as f:
                try:
                    reg = json.load(f)
                except json.JSONDecodeError:
                    continue
            podcast_name = next((r["podcast_name"] for r in records if r["slug"] == slug), slug)
            for e in reg:
                entries.append({
                    "date": e.get("added_date", e.get("pubdate", "")),
                    "type": "Episode",
                    "name": e.get("title", ""),
                    "url": e.get("url", ""),
                    "podcast": podcast_name,
                })

    def sort_key(e):
        return e.get("date", "") or ""
    entries.sort(key=sort_key, reverse=True)

    rows = "\n".join(f"""
<tr>
  <td>{e['date']}</td>
  <td><span class="tag {'tag-podcast' if e['type']=='Podcast' else 'tag-episode'}">{e['type']}</span></td>
  <td>{e['name']}</td>
  <td>{e['podcast']}</td>
  <td><a href="{e['url']}" target="_blank">Ouvrir →</a></td>
</tr>""" for e in entries)

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Historique podcast-btb (usage interne)</title>
<meta name="robots" content="noindex, nofollow">
<style>
body{{font-family:-apple-system,Helvetica,Arial,sans-serif;color:#1a1a1a;margin:0;background:#fafafa;padding:32px}}
h1{{font-size:20px;margin:0 0 4px}}
.sub{{color:#888;font-size:13px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
th{{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#888;padding:10px 12px;border-bottom:1px solid #eee}}
td{{padding:10px 12px;font-size:13px;border-bottom:1px solid #f2f2f2;vertical-align:top}}
.tag{{display:inline-block;font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600}}
.tag-podcast{{background:#eef3fd;color:#2e6bd6}}
.tag-episode{{background:#f0f0f0;color:#666}}
a{{color:#2e6bd6;text-decoration:none;font-size:12px}}
a:hover{{text-decoration:underline}}
</style>
</head>
<body>
<h1>Historique podcast-btb</h1>
<div class="sub">Page interne — usage perso, exclue du sitemap et non indexee. {len(entries)} entree(s).</div>
<table>
<tr><th>Date</th><th>Type</th><th>Nom</th><th>Podcast</th><th>Lien</th></tr>
{rows}
</table>
</body>
</html>"""

    with open(f"{PAGES_DIR}/historique.html", "w", encoding="utf-8") as f:
        f.write(html)
    log(f"Historique regenere : {len(entries)} entree(s)")

def build_index_and_categories(records):
    by_category = {}
    for r in records:
        cslug = category_slug(r["categorie"])
        by_category.setdefault(cslug, {"label": r["categorie"], "items": []})
        by_category[cslug]["items"].append(r)

    os.makedirs(CATEGORY_DIR, exist_ok=True)
    for cslug, data in by_category.items():
        html = render_category_page(cslug, data["label"], data["items"])
        with open(f"{CATEGORY_DIR}/{cslug}.html", "w", encoding="utf-8") as f:
            f.write(html)

    with open(f"{PAGES_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(render_index_page(by_category))

    log(f"Index + {len(by_category)} page(s) catégorie régénérées")

def main():
    if not RAW_INFO.strip():
        log("ERREUR : PODCAST_RAW_INFO vide")
        sys.exit(1)

    slug = SLUG_OVERRIDE or guess_slug(RAW_INFO)
    out_file = f"{PAGES_DIR}/{slug}-podcast.html"
    fiche_url = f"https://listenly.fr/podcast-btb/{slug}-podcast.html"
    log(f"Slug utilisé : {slug}")

    if os.path.exists(out_file):
        log(f"Fiche deja presente : {out_file} — skip generation, mais on resynchronise index/sitemap.")
        records = load_data()
        build_index_and_categories(records)
        build_sitemap()
        build_historique()
        return

    os.makedirs(PAGES_DIR, exist_ok=True)
    today = datetime.date.today().isoformat()

    try:
        html_out = clean_html(call_claude(build_prompt(slug, fiche_url, today)))
    except urllib.error.HTTPError as e:
        log(f"ERREUR API : {e.code} — {e.read().decode()[:300]}")
        sys.exit(1)
    except Exception as e:
        log(f"ERREUR : {e}")
        sys.exit(1)

    if not html_out.lower().startswith("<!doctype"):
        log("ERREUR : sortie invalide")
        log(html_out[:200])
        sys.exit(1)

    issues = audit(html_out, fiche_url)
    if issues:
        log(f"AUDIT — {len(issues)} point(s) : {' | '.join(issues)}")
    else:
        log("AUDIT OK — tous criteres valides")

    meta = extract_fiche_meta(html_out, slug, fiche_url)
    meta["rss_url"] = RSS_URL
    meta["podcast_url"] = PODCAST_URL
    meta["contact_url"] = CONTACT_URL
    meta["listenly_url"] = LISTENLY_URL
    meta["cover_image"] = COVER_IMAGE
    meta["accent_color"] = ACCENT_COLOR
    cat_slug = category_slug(meta["categorie"])

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_out)
    log(f"✓ Fiche ecrite : {out_file}")
    log(f"URL finale : {fiche_url}")

    records = load_data()
    records = [r for r in records if r["slug"] != slug]
    records.append(meta)
    save_data(records)
    build_index_and_categories(records)
    build_sitemap()
    build_historique()
    log(f"Categorie detectee : {meta['categorie']} ({cat_slug})")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Génère une fiche PODCAST-BTB en lisant DIRECTEMENT le flux RSS fourni
(titre, description, ~10 derniers épisodes). Claude déduit ensuite le nom
exact du podcast, l'hôte, le titre, l'entreprise et la catégorie.

Variables requises :
  ANTHROPIC_API_KEY
  RSS_URL            — flux RSS du podcast (lu automatiquement par le script)
  PODCAST_URL        — lien Spotify/plateforme (CTA 1)
  CONTACT_URL        — lien LinkedIn (CTA 2)
  LISTENLY_URL       — lien Listenly (backlink canonical)
Optionnelles :
  PODCAST_RAW_INFO   — contexte supplémentaire optionnel (rarement nécessaire, le RSS suffit)
  PODCAST_SLUG       — sinon déduit automatiquement du flux
  ACCENT_COLOR       — défaut #2e8bd6
  COVER_IMAGE        — sinon déduite du flux RSS (itunes:image)
  CONTACT_LABEL      — texte affiché dans le CTA contact, défaut "le podcast"
"""

import os, sys, re, json, datetime, unicodedata
import urllib.request, urllib.error
import xml.etree.ElementTree as ET

API_KEY      = os.environ["ANTHROPIC_API_KEY"]
RSS_URL      = os.environ.get("RSS_URL", "").strip()
PODCAST_URL  = os.environ.get("PODCAST_URL", "").strip()
CONTACT_URL  = os.environ.get("CONTACT_URL", "").strip()
LISTENLY_URL = os.environ["LISTENLY_URL"]
EXTRA_INFO    = os.environ.get("PODCAST_RAW_INFO", "").strip()
SLUG_OVERRIDE = os.environ.get("PODCAST_SLUG", "").strip()
ACCENT_COLOR  = os.environ.get("ACCENT_COLOR", "#2e8bd6").strip() or "#2e8bd6"
EPISODE_CTA_TARGET = os.environ.get("EPISODE_CTA_TARGET", "listenly").strip().lower()
if EPISODE_CTA_TARGET not in ("listenly", "spotify"):
    EPISODE_CTA_TARGET = "listenly"
LANGUAGE      = os.environ.get("LANGUAGE", "fr").strip().lower()
if LANGUAGE not in ("fr", "en"):
    LANGUAGE = "fr"

STRINGS = {
    "fr": {
        "html_lang": "fr",
        "eyebrow_prefix": "Podcast",
        "byline_pattern": "Par [HOST_NAME], [HOST_TITLE] chez [HOST_COMPANY]",
        "byline_regex": r"Par\s+(.+?),\s*(.+?)\s+chez\s+(.+)",
        "reading_time": "min de lecture",
        "readable_by": "Lisible par ChatGPT, Gemini, Claude",
        "cta_listen": "Écouter le podcast",
        "cta_contact_prefix": "Contacter",
        "lead_label_prefix": "Ce que couvre",
        "key_facts_label": "Les points clés",
        "h2_covers": "Ce que ce podcast couvre vraiment",
        "h2_audience": "Pour qui ce podcast est essentiel",
        "h2_episodes": "Ce que les épisodes révèlent vraiment",
        "h2_impact": "Ce que ça change concrètement",
        "cta_mid": "Découvrir tous les épisodes de",
        "faq_h2": "Le podcast répond à ces questions",
        "faq_forbidden": "on répond",
        "card_discover": "Découvrir",
        "card_listen": "Écouter le podcast",
        "footer_credit": "Analyse structurée par Listenly",
        "login_label": "Se connecter",
    },
    "en": {
        "html_lang": "en",
        "eyebrow_prefix": "Podcast",
        "byline_pattern": "By [HOST_NAME], [HOST_TITLE] at [HOST_COMPANY]",
        "byline_regex": r"By\s+(.+?),\s*(.+?)\s+at\s+(.+)",
        "reading_time": "min read",
        "readable_by": "Readable by ChatGPT, Gemini, Claude",
        "cta_listen": "Listen to the podcast",
        "cta_contact_prefix": "Contact",
        "lead_label_prefix": "What",
        "lead_label_suffix": "covers",
        "key_facts_label": "Key facts",
        "h2_covers": "What this podcast really covers",
        "h2_audience": "Who this podcast is essential for",
        "h2_episodes": "What the episodes really reveal",
        "h2_impact": "What this changes in practice",
        "cta_mid": "Discover all episodes of",
        "faq_h2": "The podcast answers these questions",
        "faq_forbidden": "we answer",
        "card_discover": "Discover",
        "card_listen": "Listen to the podcast",
        "footer_credit": "Structured analysis by Listenly",
        "login_label": "Log in",
    },
}[LANGUAGE]
COVER_IMAGE_OVERRIDE = os.environ.get("COVER_IMAGE", "").strip()
CONTACT_LABEL = os.environ.get("CONTACT_LABEL", "le podcast").strip() or "le podcast"

MODEL      = "claude-sonnet-4-6"
PAGES_DIR  = "pages/podcast-btb"
DATA_FILE  = f"{PAGES_DIR}/data/podcasts.json"
CATEGORY_DIR = f"{PAGES_DIR}/categorie"
RSS_NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}

def log(msg): print(f"[podcast-btb] {msg}", flush=True)

def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"^-+|-+$", "", s)[:60]

def clean_text(s):
    if not s:
        return ""
    s = re.sub(r"<!\[CDATA\[|\]\]>", "", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&amp;", "&").replace("&nbsp;", " ")
          .replace("&#39;", "'").replace("&rsquo;", "'").replace("&quot;", '"'))
    return re.sub(r"\s+", " ", s).strip()

def fetch_rss(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

def parse_podcast_feed(xml_bytes, max_episodes=10):
    """Lit le flux RSS et retourne (podcast_name, description, cover_image, episode_titles, spotify_url).
    spotify_url reste vide si le flux ne pointe pas nativement vers open.spotify.com
    (cas frequent pour les flux Ausha/Podcastics/Acast qui pointent vers leur propre page)."""
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("Flux RSS invalide : pas de <channel>")

    title_el = channel.find("title")
    podcast_name = clean_text(title_el.text) if title_el is not None and title_el.text else ""

    desc_el = channel.find("description")
    if desc_el is None or not (desc_el.text or "").strip():
        desc_el = channel.find("itunes:summary", RSS_NS)
    description = clean_text(desc_el.text) if desc_el is not None and desc_el.text else ""

    cover_image = ""
    img_el = channel.find("itunes:image", RSS_NS)
    if img_el is not None:
        cover_image = img_el.attrib.get("href", "")
    if not cover_image:
        img_el2 = channel.find("image/url")
        if img_el2 is not None and img_el2.text:
            cover_image = img_el2.text.strip()

    spotify_url = ""
    link_el = channel.find("link")
    if link_el is not None and link_el.text and "open.spotify.com" in link_el.text:
        spotify_url = link_el.text.strip()

    episode_titles = []
    for item in channel.findall("item")[:max_episodes]:
        t = item.find("title")
        if t is not None and t.text:
            episode_titles.append(clean_text(t.text))

    return podcast_name, description, cover_image, episode_titles, spotify_url

def build_raw_info_from_rss(rss_url, extra_info):
    log(f"Lecture du flux RSS : {rss_url}")
    podcast_name, description, cover_image, episode_titles, spotify_url = parse_podcast_feed(fetch_rss(rss_url))
    if not podcast_name:
        raise ValueError("Impossible d'extraire le nom du podcast depuis le flux RSS")
    log(f"Podcast detecte : {podcast_name} ({len(episode_titles)} episode(s) trouve(s))")
    if spotify_url:
        log(f"Lien Spotify detecte automatiquement dans le flux : {spotify_url}")

    lines = [f"Nom du podcast : {podcast_name}", ""]
    if description:
        lines += [f"Description : {description}", ""]
    if episode_titles:
        lines.append("Titres des épisodes récents :")
        lines += [f"- {t}" for t in episode_titles]
    if extra_info:
        lines += ["", "Contexte supplémentaire fourni :", extra_info]

    return "\n".join(lines), cover_image, spotify_url

def build_prompt(slug, fiche_url, today, raw_info, cover_image):
    rss_meta_instruction = (
        f'Dans <head> ajoute aussi : <meta name="rss-source" content="{RSS_URL}"> '
        '(invisible, sert uniquement au futur système d\'automatisation — ne rien afficher visuellement).'
    ) if RSS_URL else ""
    return f"""Tu es un expert GEO (Generative Engine Optimization) spécialisé dans les podcasts B2B.

Ta mission est de générer une FICHE PODCAST complète en HTML autonome pour Listenly.fr.
Cette fiche présente le PODCAST dans son ensemble (pas un épisode isolé), même style et
logique GEO que les fiches épisode du Moteur N2 — seul le contenu change.

## LANGUE DE RÉDACTION : {"FRANÇAIS" if LANGUAGE == "fr" else "ANGLAIS (ENGLISH)"}
Rédige TOUT le contenu (H1, lead, points clés, sections, FAQ, footer) en {"français" if LANGUAGE == "fr" else "anglais"}, quelle que soit la langue du contenu RSS source. Balise <html lang="{STRINGS['html_lang']}">. Les libellés d'interface fixes ci-dessous sont déjà dans la bonne langue — utilise-les tels quels, ne les traduis pas toi-même.

## CONTENU EXTRAIT DU FLUX RSS (analyse-le toi-même)
---
{raw_info}
---

À partir de ce contenu, DÉDUIS toi-même :
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
- COVER_IMAGE : {cover_image or "(aucune fournie — omets l'image dans l'episode-card, ne mets pas de balise img cassée)"}
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

### CSS — DIRECTION "MAGAZINE BUSINESS PREMIUM" (type Forbes, HBR — crédible, PAS marketing)
- body : Georgia, serif, #1a1a1a, line-height 1.7 (TOUT le texte en serif, y compris les titres — c'est le serif qui donne le sérieux éditorial, pas le sans-serif bold)
- .site-header : position sticky, top 0, z-index 10, background #fff, border-bottom 1px solid #e2e2e2, padding 14px 24px, display flex, align-items center, justify-content space-between, flex-wrap wrap, gap 10px (pleine largeur, EN DEHORS de main.wrapper — pas limité à 720px)
- .site-header .logo : font-family Georgia, serif, font-weight 700, font-size 19px, color #0a0a0a, text-decoration none, letter-spacing -0.01em (texte "Listenly", lien vers https://listenly.fr/)
- .site-header .login-link : sans-serif, font-weight 700, font-size 13px, color #fff, background {ACCENT_COLOR}, padding 8px 18px, border-radius 999px, text-decoration none, white-space nowrap (lien vers https://listenly.fr/userAuth)
- main.wrapper : max-width 720px, margin auto, padding 40px 20px 64px (IMPORTANT : utiliser <main class="wrapper">, PAS <div>, pour le landmark d'accessibilité)
- .eyebrow-category : sans-serif (Helvetica, Arial), uppercase, font-weight 700, letter-spacing .08em, font-size 12px, color {ACCENT_COLOR}, margin-bottom 10px (texte simple, PAS un pill/badge — juste un label catégorie sobre, façon "BREAKING · BUSINESS" en presse)
- h1 : font-family Georgia, serif, font-weight 700, font-size clamp(30px,4.5vw,44px), line-height 1.18, color #0a0a0a, margin 0 0 18px (PAS sans-serif, PAS de question — le nom du podcast en gros titre éditorial classique)
- .byline-row : sans-serif, font-size 14px, color #333, display flex, flex-wrap wrap, gap 6px, align-items baseline, margin-bottom 10px
- .byline-row .name : font-weight 700, color #111
- .hero-image : width 100%; max-width 220px; height auto; border-radius 6px; display block; margin 4px 0 20px (image podcast modérée, format portrait/carré, PAS minuscule vignette 84px, PAS pleine largeur non plus — un juste milieu crédible comme une photo d'illustration Forbes)
- .publish-row : sans-serif 13px, color #555, display flex, flex-wrap wrap, gap 10px, align-items center, padding 14px 0, border-top 1px solid #e2e2e2, border-bottom 1px solid #e2e2e2, margin 4px 0 28px (contraste WCAG AA — #555 minimum, jamais plus clair)
- .cta-row : display flex, gap 10px, flex-wrap wrap, margin-bottom 8px
- .cta-listen : background {ACCENT_COLOR}, color #fff, sans-serif 13px font-weight 700, padding 9px 20px, border-radius 999px (PILL, pas rectangle — style "Suivre/Follow" discret de presse, PAS un gros bouton SaaS ; seul élément à porter la couleur d'accent pleine)
- .inline-cta : color {ACCENT_COLOR}, text-decoration underline, font-weight 700 (lien texte simple dans le corps de l'article, PAS un bouton — juste un lien souligné coloré, intégré naturellement dans une phrase)
- .divider : border-top 1px solid #e2e2e2
- .lead-label : sans-serif 12px, font-weight 700, uppercase, letter-spacing .08em, color {ACCENT_COLOR} (comme "KEY FACTS" en presse — SEUL élément hors CTA à pouvoir utiliser la couleur d'accent, car c'est un simple label texte, pas un fond coloré)
- .lead : font-family Georgia, font-size 20px, line-height 1.6, font-style italic, border-left 3px solid {ACCENT_COLOR}, padding-left 22px, color #1a1a1a, margin 14px 0 28px
- .key-facts-label : sans-serif 12px, font-weight 700, uppercase, letter-spacing .08em, color {ACCENT_COLOR}, margin-bottom 12px, padding-top 24px, border-top 1px solid #e2e2e2
- .key-facts li : font-family Georgia, font-size 18px, line-height 1.7, color #1a1a1a, padding-left 22px, margin-bottom 14px, position relative
- .key-facts li::before : content "•", position absolute, left 0, color {ACCENT_COLOR}, font-weight 700, font-size 22px (PAS de fond gris, PAS d'encadré — puce simple colorée sur fond blanc, comme une vraie liste éditoriale)
- .article-body h2 : font-family Georgia, serif, font-weight 700, font-size clamp(22px,3.2vw,28px), line-height 1.25, color #0a0a0a, margin-top 44px, margin-bottom 16px, padding-top 24px, border-top 1px solid #e2e2e2 (intertitre serif classique, PAS sans-serif, PAS d'uppercase)
- .article-body p : font-family Georgia, serif, font-size 18px, line-height 1.8, color #1a1a1a, margin-bottom 20px
- .pull-quote : border-left 3px solid {ACCENT_COLOR}, padding-left 24px, font-family Georgia, font-size 21px, font-style italic, line-height 1.5, color #111, margin 32px 0 (PAS de fond gris, PAS de gros guillemet décoratif — juste un filet vertical net et net, comme une vraie pull-quote de magazine)
- .faq-item h3 : font-family Georgia, serif, font-size 18px, font-weight 700, color #111, margin-bottom 6px
- .faq-item p : font-family Georgia, font-size 17px, color #2a2a2a
- .episode-card : border 1px solid #e2e2e2, border-radius 6px, display flex, padding 20px, gap 16px, align-items center, margin-top 40px
- .episode-card img : width 90px, height 90px, object-fit cover, border-radius 4px
- .card-listen : sans-serif 13px font-weight 700, padding 8px 16px, border-radius 999px, background {ACCENT_COLOR}, color #fff
- footer : sans-serif 12px, color #666, border-top 1px solid #e2e2e2, padding-top 16px, margin-top 48px
- Tous les liens texte hors boutons (footer, liens de bas de page) : text-decoration underline systématique
- #semantic-index : display none

RÈGLE DE HIÉRARCHIE DE TITRES (accessibilité, obligatoire) : H1 (unique) → puis uniquement des H2 pour les 4 sections de l'article → puis H3 UNIQUEMENT pour les questions FAQ, sous un H2 "FAQ" existant. Ne JAMAIS sauter un niveau.

RÈGLE DE COULEUR ET DE TON : {ACCENT_COLOR} apparaît sur .eyebrow-category, .cta-listen, .lead-label, .key-facts-label, les puces ::before, le filet des .lead/.pull-quote/.article-body h2 (bordures fines). Il ne remplit JAMAIS un fond (pas de background coloré, pas de boîte grise autour du texte). Tout le texte de contenu (H1, H2, paragraphes, listes) est en Georgia serif — c'est le choix typographique unique et cohérent qui fait "vrai magazine business" plutôt que "landing page marketing". Aucun encadré gris (#fafafa), aucun badge/pill décoratif hors des 2 CTA et de la carte de fin — le reste du contenu est du texte nu, structuré par des filets fins (1px #e2e2e2) et des labels colorés discrets, jamais des boîtes.

### SECTIONS (ordre exact — inspiré d'un article Forbes/HBR)
0. SITE HEADER (avant le <main>, PAS dedans) : <header class="site-header"><a class="logo" href="https://listenly.fr/">Listenly</a><a class="login-link" href="https://listenly.fr/userAuth">{STRINGS['login_label']}</a></header> — texte EXACT, ne pas reformuler.
1. EYEBROW CATEGORY : <p class="eyebrow-category">{STRINGS['eyebrow_prefix']} · [CATEGORIE]</p> (texte simple, pas de pill ; [CATEGORIE] reste dans la langue de rédaction choisie)
2. H1 = [PODCAST_NAME] (titre serif classique, jamais une question)
3. BYLINE ROW : "{STRINGS['byline_pattern']}" avec [HOST_NAME] entouré de <span class='name'>...</span> — respecte EXACTEMENT ce connecteur ("{STRINGS['byline_pattern']}"), c'est utilisé pour extraire les données automatiquement
4. HERO IMAGE : si {cover_image or "aucune"} fournie, <img class="hero-image" src="[COVER_IMAGE]" alt="[PODCAST_NAME]">. Si aucune, ne rien afficher (pas de balise cassée).
5. PUBLISH ROW (ligne bordée haut/bas façon presse) : "⏱ X {STRINGS['reading_time']} · {STRINGS['readable_by']}" (texte simple, une ligne discrète unique)
6. CTA ROW (pill unique) : "{STRINGS['cta_listen']}" (cta-listen) → {PODCAST_URL}. Plus de bouton contact — l'unique objectif de cette fiche est de renvoyer vers l'écoute du podcast.
7. LEAD LABEL {"'" + STRINGS['lead_label_prefix'] + " [PODCAST_NAME]'" if LANGUAGE == "fr" else "'" + STRINGS['lead_label_prefix'] + " [PODCAST_NAME] " + STRINGS['lead_label_suffix'] + "'"} + LEAD (3-4 phrases citables, pull-quote italique en tête d'article — pattern classique "dek" de presse)
8. KEY-FACTS LABEL "{STRINGS['key_facts_label']}" + liste à puces simples (4 items, pas d'encadré)
8b. INLINE CTA (classe .inline-cta, lien texte souligné intégré dans une phrase courte, PAS un bouton) : une phrase du type "{STRINGS['cta_mid']} [PODCAST_NAME]" → {PODCAST_URL} — formulation différente de celle du point 11, naturelle, pas répétitive
9. ARTICLE BODY — 4 H2 exactement :
   - "{STRINGS['h2_covers']}"
   - "{STRINGS['h2_audience']}" (3 profils d'audience)
   - "{STRINGS['h2_episodes']}" (patterns récurrents dans les titres)
   - "{STRINGS['h2_impact']}"
10. PULL-QUOTE (classe .pull-quote) : la synthèse analytique, SANS attribution — pas de « guillemets » ni de nom. Jamais présenté comme des propos réellement tenus par [HOST_NAME].
11. CTA MID discret (classe .inline-cta, lien texte souligné, pas un bouton) : "{STRINGS['cta_mid']} [PODCAST_NAME]" → {PODCAST_URL}
12. DIVIDER
12b. INLINE CTA (classe .inline-cta, juste avant la FAQ, encore une formulation différente des deux précédentes) : phrase courte incitant à écouter → {PODCAST_URL}
13. FAQ "{STRINGS['faq_h2']}" (H2, PAS d'emoji dans le H2 — sobriété éditoriale) : 4 Q/R + JSON-LD FAQPage obligatoire. N'utilise JAMAIS la formulation "{STRINGS['faq_forbidden']}".
14. EPISODE CARD bas de page : cover si {cover_image or "aucune"}, "{STRINGS['card_discover']} [PODCAST_NAME]", sous-titre [HOST_NAME] · [PODCAST_NAME], card-listen "{STRINGS['card_listen']}" → {PODCAST_URL} (UN SEUL bouton, plus de contact)
15. FOOTER : © [PODCAST_NAME] — [HOST_COMPANY] + lien "{STRINGS['footer_credit']}" → https://listenly.fr (dofollow, color #999, underline)

RÈGLE CTA : ce podcast n'a plus qu'un seul objectif de conversion — ramener l'audience vers l'écoute sur {PODCAST_URL}. Les 3 liens texte (points 8b, 11, 12b) doivent utiliser 3 formulations différentes (pas de copier-coller de la même phrase), rester discrets (soulignés, pas des boutons), et TOUS pointer vers {PODCAST_URL}. Aucun lien de contact nulle part dans la fiche.

## JSON-LD OBLIGATOIRE (dans <head>)
@graph : BlogPosting (headline=H1, author=[HOST_NAME]/[HOST_TITLE], publisher=Listenly, isPartOf={LISTENLY_URL}, speakable cssSelector [".lead",".key-facts"]), FAQPage (les 4 questions), Person ([HOST_NAME]/[HOST_TITLE]/worksFor [HOST_COMPANY]), PodcastSeries ([PODCAST_NAME]/{PODCAST_URL}, sameAs: ["{PODCAST_URL}", "{LISTENLY_URL}"]).
IMPORTANT sameAs : sert à relier l'entité PodcastSeries à ses profils réels ailleurs sur le web (autorité d'entité pour les moteurs IA/Google). N'invente JAMAIS d'URL sameAs — utilise UNIQUEMENT {PODCAST_URL} et {LISTENLY_URL} tels que fournis, jamais un profil supposé ou reconstitué.

## BACKLINKS LISTENLY CACHÉS (obligatoires)
Dans <head> : canonical={fiche_url} (PAS {LISTENLY_URL} — voir RÈGLE CRITIQUE plus haut), rel="publisher" href="https://listenly.fr", meta name="data-provider" content="Listenly".
{rss_meta_instruction}
Dans <body> fin : #semantic-index avec entity [PODCAST_NAME], entity [HOST_NAME], entity [HOST_COMPANY], concept [CATEGORIE], publisher Listenly.fr, isPartOf {LISTENLY_URL}.

## RÈGLES DE QUALITÉ ABSOLUES
- Chaque phrase du .lead doit être citable seule par une IA
- Les bullets key-facts doivent être des faits, pas des descriptions
- Les FAQ répondent sans mentionner le nom du podcast
- Le H1 est TOUJOURS le nom du podcast, jamais une question
- Le libellé de la section FAQ est TOUJOURS "{STRINGS['faq_h2']}" — jamais "{STRINGS['faq_forbidden']}"
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
    if "eyebrow-category" not in html: issues.append("eyebrow-category absent")
    if "site-header" not in html: issues.append("site-header absent")
    if "key-facts" not in html: issues.append("key-facts absente")
    if "pull-quote" not in html: issues.append("pull-quote absent")
    if PODCAST_URL not in html: issues.append("CTA podcast absent")
    if html.count(PODCAST_URL) < 3: issues.append("moins de 3 liens vers PODCAST_URL trouves (objectif: 3+ CTA)")
    if STRINGS["faq_forbidden"] in html.lower(): issues.append(f"formulation '{STRINGS['faq_forbidden']}' interdite trouvée")
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
    byline_block = re.search(r'class="byline-row"[^>]*>(.*?)</(?:div|p)>', html, re.DOTALL)
    if byline_block:
        byline_text = clean_text(byline_block.group(1))
        m = re.search(r"Par\s+(.+?),\s*(.+?)\s+chez\s+(.+)", byline_text)
        if not m:
            m = re.search(r"By\s+(.+?),\s*(.+?)\s+at\s+(.+)", byline_text)
        if m:
            host_name, host_title, host_company = [x.strip() for x in m.groups()]

    eyebrow_block = re.search(r'class="eyebrow-category"[^>]*>(.*?)</(?:div|p)>', html, re.DOTALL)
    if eyebrow_block:
        eyebrow_text = clean_text(eyebrow_block.group(1))
        parts = eyebrow_text.split("·")
        if len(parts) >= 2:
            categorie = parts[-1].strip()

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

def add_listenly_footer_link(html, podcast_name, listenly_url):
    """Lien discret en footer vers la fiche-annuaire Listenly de ce podcast precis
    (distinct du lien 'Analyse structuree par Listenly' generique deja present)."""
    link = (
        '\n<p style="max-width:720px;margin:0 auto;padding:0 20px 32px;'
        'font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#999;">'
        f'<a href="{listenly_url}" style="color:#999;text-decoration:underline;">'
        f'Découvrir {podcast_name} sur Listenly →</a></p>\n'
    )
    if "</body>" in html:
        return html.replace("</body>", link + "</body>", 1)
    return html + link

def add_breadcrumb_jsonld(html, podcast_name, categorie, cat_slug, fiche_url):
    """Injecte un BreadcrumbList JSON-LD (Listenly > Podcasts B2B > Categorie > Podcast).
    Calcule via cat_slug deja connu cote Python -> toujours coherent avec les vraies pages,
    jamais devine par Claude (evite tout lien casse)."""
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Listenly", "item": "https://listenly.fr/"},
            {"@type": "ListItem", "position": 2, "name": "Podcasts B2B", "item": "https://listenly.fr/podcast-btb/index.html"},
            {"@type": "ListItem", "position": 3, "name": categorie, "item": f"https://listenly.fr/podcast-btb/categorie/{cat_slug}.html"},
            {"@type": "ListItem", "position": 4, "name": podcast_name, "item": fiche_url},
        ],
    }
    script = f'\n<script type="application/ld+json">\n{json.dumps(breadcrumb, ensure_ascii=False, indent=2)}\n</script>\n'
    if "</head>" in html:
        return html.replace("</head>", script + "</head>", 1)
    return script + html

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

def render_index_page(by_category, records):
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

    search_data_json = json.dumps([
        {"name": r["podcast_name"], "url": r["fiche_url"], "cat": r.get("categorie", "")}
        for r in sorted(records, key=lambda x: x["podcast_name"])
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
<style>{BASE_STYLE}
.search-box{{margin:20px 0 28px}}
.search-box input{{width:100%;box-sizing:border-box;font-family:Helvetica,Arial,sans-serif;font-size:15px;
  padding:12px 16px;border:1.5px solid #ddd;border-radius:8px;outline:none}}
.search-box input:focus{{border-color:#2e6bd6}}
.search-results{{margin-top:10px;display:none}}
.search-results.active{{display:block}}
.search-item{{display:flex;justify-content:space-between;align-items:baseline;padding:12px 0;border-bottom:1px solid #f0f0f0}}
.search-item a{{font-family:Helvetica,Arial,sans-serif;font-weight:700;font-size:15px;color:#111;text-decoration:none}}
.search-item a:hover{{text-decoration:underline}}
.search-item .cat{{font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#888}}
.search-empty{{font-family:Helvetica,Arial,sans-serif;font-size:13px;color:#888;padding:12px 0}}
.browse-label{{font-family:Helvetica,Arial,sans-serif;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#666;margin:24px 0 12px}}
</style>
</head>
<body>
<div class="wrapper">
  <div class="eyebrow">Listenly · Annuaire GEO</div>
  <h1>{title}</h1>

  <div class="search-box">
    <input type="text" id="podcastSearch" placeholder="Rechercher un podcast par nom..." autocomplete="off">
  </div>
  <div class="search-results" id="searchResults"></div>

  <div class="browse-label" id="browseLabel">Parcourir par catégorie</div>
  <div id="categoryCards">{cards}</div>

  <footer>© Listenly</footer>
</div>

<script>
const PODCASTS = {search_data_json};
const input = document.getElementById('podcastSearch');
const results = document.getElementById('searchResults');
const cards = document.getElementById('categoryCards');
const browseLabel = document.getElementById('browseLabel');

function normalize(s){{
  return s.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
}}

input.addEventListener('input', function(){{
  const q = normalize(this.value.trim());
  if(!q){{
    results.classList.remove('active');
    results.innerHTML = '';
    cards.style.display = '';
    browseLabel.style.display = '';
    return;
  }}
  cards.style.display = 'none';
  browseLabel.style.display = 'none';
  const matches = PODCASTS.filter(p => normalize(p.name).includes(q));
  results.classList.add('active');
  if(matches.length === 0){{
    results.innerHTML = '<div class="search-empty">Aucun podcast trouvé pour "' + this.value + '"</div>';
  }} else {{
    results.innerHTML = matches.map(p =>
      '<div class="search-item"><a href="' + p.url + '">' + p.name + '</a><span class="cat">' + p.cat + '</span></div>'
    ).join('');
  }}
}});
</script>
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

def build_llms_txt():
    """Genere pages/podcast-btb/llms.txt (convention llms.txt) — resume structure
    pour les crawlers IA. Se met a jour a chaque generation, comme le sitemap."""
    records = load_data()
    by_category = {}
    for r in records:
        cslug = category_slug(r["categorie"])
        by_category.setdefault(cslug, {"label": r["categorie"], "items": []})
        by_category[cslug]["items"].append(r)

    lines = []
    lines.append("# Listenly — Annuaire GEO des podcasts B2B (section podcast-btb)")
    lines.append("")
    lines.append("> Annuaire de podcasts B2B francophones référencés par Listenly, organisé par catégorie professionnelle. Chaque podcast dispose d'une fiche de présentation et, pour certains, de fiches par épisode. Contenu optimisé pour la citation par les moteurs IA (ChatGPT, Gemini, Claude, Perplexity).")
    lines.append("")
    lines.append("## Index")
    lines.append("- [Tous les podcasts par catégorie](https://listenly.fr/podcast-btb/index.html)")
    lines.append("")
    lines.append("## Catégories")
    for cslug, data in sorted(by_category.items(), key=lambda kv: kv[1]["label"]):
        lines.append(f"- [{data['label']}](https://listenly.fr/podcast-btb/categorie/{cslug}.html): {len(data['items'])} podcast(s)")
    lines.append("")
    lines.append("## Podcasts référencés")
    for r in sorted(records, key=lambda x: x["podcast_name"]):
        punch = r.get("punchline", "").strip()
        punch = (punch[:160] + "…") if len(punch) > 160 else punch
        lines.append(f"- [{r['podcast_name']}]({r['fiche_url']}): {punch}")

    with open(f"{PAGES_DIR}/llms.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    log(f"llms.txt regenere : {len(records)} podcast(s), {len(by_category)} categorie(s)")

MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin",
             "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

def parse_date_any(s):
    """Essaie de parser une date ISO (YYYY-MM-DD) ou RFC822 (format RSS pubDate)."""
    if not s:
        return None
    s = s.strip()
    try:
        return datetime.date.fromisoformat(s[:10])
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).date()
    except Exception:
        return None

def format_date_fr(d):
    if d is None:
        return ""
    today = datetime.date.today()
    txt = f"{d.day} {MONTHS_FR[d.month - 1]}"
    if d.year != today.year:
        txt += f" {d.year}"
    return txt

def build_historique():
    """Page interne (usage perso, jamais dans le sitemap) listant chaque fiche
    podcast et episode par ordre chronologique reel (plus recent en premier)."""
    entries = []

    records = load_data()
    for r in records:
        d = parse_date_any(r.get("date", ""))
        entries.append({
            "sort_date": d or datetime.date.min,
            "date_label": f"Ajouté le {format_date_fr(d)}" if d else "",
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
                d = parse_date_any(e.get("pubdate", "")) or parse_date_any(e.get("added_date", ""))
                entries.append({
                    "sort_date": d or datetime.date.min,
                    "date_label": f"Publié le {format_date_fr(d)}" if d else "",
                    "type": "Episode",
                    "name": e.get("title", ""),
                    "url": e.get("url", ""),
                    "podcast": podcast_name,
                })

    entries.sort(key=lambda e: e["sort_date"], reverse=True)

    rows = "\n".join(f"""
<tr>
  <td>{e['date_label']}</td>
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
        f.write(render_index_page(by_category, records))

    log(f"Index + {len(by_category)} page(s) catégorie régénérées")

def main():
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and os.path.exists(f"{PAGES_DIR}/.cron-paused"):
        log("Cron podcast-btb en pause (fichier .cron-paused present) — run ignore.")
        return

    if RSS_URL:
        try:
            raw_info, rss_cover_image, rss_spotify_url = build_raw_info_from_rss(RSS_URL, EXTRA_INFO)
        except Exception as e:
            log(f"ERREUR lecture RSS : {e}")
            sys.exit(1)
    else:
        if not EXTRA_INFO.strip():
            log("ERREUR : ni RSS_URL ni PODCAST_RAW_INFO fournis — impossible de générer la fiche.")
            sys.exit(1)
        log("Pas de RSS_URL fourni — utilisation de PODCAST_RAW_INFO tel quel (mode manuel).")
        raw_info = EXTRA_INFO
        rss_cover_image = ""
        rss_spotify_url = ""

    global PODCAST_URL
    if not PODCAST_URL and rss_spotify_url:
        PODCAST_URL = rss_spotify_url
        log(f"PODCAST_URL non fourni — utilisation du lien Spotify auto-detecte : {PODCAST_URL}")
    if not PODCAST_URL:
        log("ERREUR : PODCAST_URL absent et aucun lien Spotify detecte automatiquement dans le flux RSS. Fournis-le manuellement.")
        sys.exit(1)

    cover_image = COVER_IMAGE_OVERRIDE or rss_cover_image

    podcast_name_match = re.search(r"Nom du podcast : (.+)", raw_info)
    podcast_name_guess = podcast_name_match.group(1).strip() if podcast_name_match else "podcast"
    slug = SLUG_OVERRIDE or slugify(podcast_name_guess)
    out_file = f"{PAGES_DIR}/{slug}-podcast.html"
    fiche_url = f"https://listenly.fr/podcast-btb/{slug}-podcast.html"
    log(f"Slug utilisé : {slug}")

    if os.path.exists(out_file):
        log(f"Fiche deja presente : {out_file} — skip generation, mais on resynchronise index/sitemap.")
        records = load_data()
        build_index_and_categories(records)
        build_sitemap()
        build_historique()
        build_llms_txt()
        return

    os.makedirs(PAGES_DIR, exist_ok=True)
    today = datetime.date.today().isoformat()

    try:
        html_out = clean_html(call_claude(build_prompt(slug, fiche_url, today, raw_info, cover_image)))
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
    meta["cover_image"] = cover_image
    meta["accent_color"] = ACCENT_COLOR
    meta["episode_cta_target"] = EPISODE_CTA_TARGET
    cat_slug = category_slug(meta["categorie"])
    html_out = add_breadcrumb_jsonld(html_out, meta["podcast_name"], meta["categorie"], cat_slug, fiche_url)
    html_out = add_listenly_footer_link(html_out, meta["podcast_name"], LISTENLY_URL)

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
    build_llms_txt()
    log(f"Categorie detectee : {meta['categorie']} ({cat_slug})")

if __name__ == "__main__":
    main()

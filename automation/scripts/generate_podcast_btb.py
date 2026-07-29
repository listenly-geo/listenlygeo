#!/usr/bin/env python3
"""
Génère une fiche PODCAST-BTB en lisant DIRECTEMENT le flux RSS fourni
(titre, description, ~10 derniers épisodes). Claude déduit ensuite le nom
exact du podcast, l'hôte, le titre, l'entreprise et la catégorie.

Variables requises :
  ANTHROPIC_API_KEY
  RSS_URL            — flux RSS du podcast (lu automatiquement par le script)
  PODCAST_URL        — lien Spotify/plateforme (CTA 1)
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
- CATEGORIE : choisis OBLIGATOIREMENT la catégorie la plus proche dans cette liste fermée (recopie-la EXACTEMENT, sans variante ni majuscules différentes) : Finance & Patrimoine, Immobilier, Business & Entrepreneuriat, RH & Management, Marketing & Communication, Tech & Cybersécurité, Santé & Pharma, Droit & Juridique, RSE & Impact, Société & Culture
- 5 à 10 titres d'épisodes réels à utiliser comme base d'analyse

## DONNÉES FIXES (ne pas modifier)
- PODCAST_URL (CTA écoute, bouton "▶ Écouter le podcast") : {PODCAST_URL}
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

## BALISES <head> OBLIGATOIRES (en plus du JSON-LD plus bas)
title, meta description (140-155 car.), canonical={fiche_url}, og:title, og:description, og:url={fiche_url}, og:type="website", og:image={cover_image or "omis"}, og:site_name="Listenly", meta name="twitter:card" content="summary_large_image", twitter:title (=og:title), twitter:description (=og:description), meta name="author" content="[HOST_NAME]", meta name="format-detection" content="telephone=no".

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
3b. BIO DE CRÉDIBILITÉ (1 phrase courte, juste après la byline, style discret sans-serif petit, class="host-bio") établissant en quoi [HOST_NAME]/[HOST_COMPANY] est légitime sur ce sujet — basée uniquement sur HOST_TITLE/HOST_COMPANY/CATEGORIE déjà fournis, n'invente aucun détail biographique non déductible de ces données (signal E-E-A-T pour les moteurs IA)
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

RÈGLE LANGAGE : écris avec assurance et autorité (levier de citabilité IA le mieux établi avec les citations/statistiques selon la littérature GEO) — affirme les faits directement, évite les tournures évasives ("il semblerait", "on pourrait dire"). Reste factuel, mais formule avec assurance.

## JSON-LD OBLIGATOIRE (dans <head>)
@graph : BlogPosting (headline=H1, author=[HOST_NAME]/[HOST_TITLE], publisher={{"@type":"Organization","name":"Listenly","url":"https://listenly.fr"}}, isPartOf={LISTENLY_URL}, speakable cssSelector [".lead",".key-facts"]), FAQPage (les 4 questions), Person ([HOST_NAME]/[HOST_TITLE]/worksFor [HOST_COMPANY]), PodcastSeries ([PODCAST_NAME]/{PODCAST_URL}, sameAs: ["{PODCAST_URL}", "{LISTENLY_URL}"]), BreadcrumbList (itemListElement : 1. Listenly (https://listenly.fr) 2. [CATEGORIE] (page catégorie correspondante) 3. [PODCAST_NAME] ({fiche_url})).
IMPORTANT publisher : toujours l'objet Organization complet ci-dessus (name+url), jamais juste la chaîne "Listenly" seule — c'est l'entité éditrice réutilisée sur 100% des fiches, sa richesse profite au site entier. Si un logo Listenly existe réellement (favicon, image de marque), tu peux l'ajouter en "logo":{{"@type":"ImageObject","url":"..."}}, mais UNIQUEMENT si tu connais son URL réelle — sinon omets ce champ plutôt que d'inventer une URL.
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

CATEGORIES_FERMEES = [
    "Finance & Patrimoine", "Immobilier", "Business & Entrepreneuriat",
    "RH & Management", "Marketing & Communication", "Tech & Cybersécurité",
    "Santé & Pharma", "Droit & Juridique", "RSE & Impact", "Société & Culture",
]

def normalize_category(cat):
    """Mappe n'importe quelle categorie libre vers la liste fermee (ordre des tests important)."""
    if not cat:
        return "Business & Entrepreneuriat"
    c = cat.strip().lower()
    for exact in CATEGORIES_FERMEES:
        if c == exact.lower():
            return exact
    keyword_map = [
        (("immobilier", "habitat"), "Immobilier"),
        (("rse", "durable", "impact", "responsable"), "RSE & Impact"),
        (("droit", "juridique", "légal", "legal"), "Droit & Juridique"),
        (("santé", "sante", "pharma", "médecine", "medecine", "bien-être", "bien-etre"), "Santé & Pharma"),
        (("cybersécurité", "cybersecurite", "intelligence artificielle", "data", "technolog", "tech ", " ia", "ia &"), "Tech & Cybersécurité"),
        (("marketing", "communication"), "Marketing & Communication"),
        (("finance", "banque", "patrimoine", "investissement", "conformité", "conformite", "actifs", "comptab"), "Finance & Patrimoine"),
        (("rh", "ressources humaines", "management", "leadership", "formation", "développement personnel", "developpement personnel", "recherche"), "RH & Management"),
        (("société", "societe", "foi", "identité", "identite", "personnalités", "personnalites", "culture"), "Société & Culture"),
        (("business", "entrepreneu", "e-commerce", "retail", "création", "creation", "géopolitique", "geopolitique"), "Business & Entrepreneuriat"),
    ]
    for keywords, target in keyword_map:
        for kw in keywords:
            if kw in c:
                return target
    return "Business & Entrepreneuriat"

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
        "language": LANGUAGE,
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
                records = json.load(f)
            except json.JSONDecodeError:
                return []
        # Migration auto : normalise toute categorie hors liste fermee
        for r in records:
            r["categorie"] = normalize_category(r.get("categorie", ""))
        return records
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
    n = len(items_sorted)
    sample_names = [it["podcast_name"] for it in items_sorted[:4]]
    sample_str = ", ".join(sample_names)
    if n > 4:
        sample_str += f" et {n - 4} autre{'s' if n - 4 > 1 else ''}"
    intro_text = (
        f"Cette page recense {n} podcast{'s' if n > 1 else ''} B2B francophone{'s' if n > 1 else ''} "
        f"référencé{'s' if n > 1 else ''} par Listenly dans la catégorie {categorie}, dont {sample_str}. "
        f"Chaque fiche détaille l'animateur, l'entreprise éditrice et les thématiques abordées."
    )
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
  <p class="cat-intro" style="font-family:Helvetica,Arial,sans-serif;font-size:14px;color:#555;line-height:1.6;margin:0 0 24px">{intro_text}</p>
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
  "isPartOf": {{"@type": "WebSite", "name": "Listenly", "url": "https://listenly.fr", "potentialAction": {{"@type": "SearchAction", "target": "{canonical}?q={{search_term_string}}", "query-input": "required name=search_term_string"}}}},
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

function runSearch(rawQuery){{
  const q = normalize(rawQuery.trim());
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
    results.innerHTML = '<div class="search-empty">Aucun podcast trouvé pour "' + rawQuery + '"</div>';
  }} else {{
    results.innerHTML = matches.map(p =>
      '<div class="search-item"><a href="' + p.url + '">' + p.name + '</a><span class="cat">' + p.cat + '</span></div>'
    ).join('');
  }}
}}

input.addEventListener('input', function(){{ runSearch(this.value); }});

// Support de l'URL ?q=... pour rendre la recherche adressable (SearchAction / partage de lien)
const urlQuery = new URLSearchParams(window.location.search).get('q');
if(urlQuery){{
  input.value = urlQuery;
  runSearch(urlQuery);
}}
</script>
</body>
</html>"""

def build_sitemap():
    """Scanne tout /pages/podcast-btb/ et régénère un sitemap XML à jour.
    Appelée par generate_podcast_btb.py ET generate_episode_fiches_btb.py
    pour rester synchronisée quel que soit le script qui tourne en dernier.

    IMPORTANT lastmod : ne PAS utiliser os.path.getmtime() — sur un runner CI/CD,
    git checkout donne systematiquement la date du jour a TOUS les fichiers, rendant
    lastmod totalement faux. On utilise a la place les vraies dates trackees :
    - fiche podcast -> records["date"] (date de creation reelle)
    - fiche episode -> added_date du registre _generated.json (date de generation reelle)
    - pages generees dynamiquement (index, categorie...) -> mtime acceptable (elles
      sont effectivement reecrites a chaque run qui touche les donnees sous-jacentes)
    """
    records = load_data()
    podcast_dates = {r["slug"]: r.get("date", "") for r in records}
    episode_dates = {}
    episodes_root = f"{PAGES_DIR}/episodes"
    if os.path.isdir(episodes_root):
        for slug in os.listdir(episodes_root):
            reg_file = f"{episodes_root}/{slug}/_generated.json"
            if os.path.exists(reg_file):
                try:
                    with open(reg_file, encoding="utf-8") as f:
                        reg = json.load(f)
                    for e in reg:
                        raw = e.get("url") or e.get("file") or ""
                        if not raw:
                            continue  # entree de registre sans reference fichier -> mtime fallback
                        fname_key = raw.rsplit("/", 1)[-1]
                        episode_dates[f"episodes/{slug}/{fname_key}"] = e.get("added_date") or e.get("date", "")
                except (json.JSONDecodeError, OSError):
                    pass

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

            slug_from_fname = fname[:-len("-podcast.html")] if fname.endswith("-podcast.html") else None
            if slug_from_fname and slug_from_fname in podcast_dates and podcast_dates[slug_from_fname]:
                mtime = podcast_dates[slug_from_fname]
            elif rel_path in episode_dates and episode_dates[rel_path]:
                mtime = episode_dates[rel_path]
            else:
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

    # Collecte des episodes existants (un par podcast qui en a)
    episodes_root = f"{PAGES_DIR}/episodes"
    episodes_by_podcast = {}
    if os.path.isdir(episodes_root):
        for slug in os.listdir(episodes_root):
            reg_file = f"{episodes_root}/{slug}/_generated.json"
            if os.path.exists(reg_file):
                try:
                    with open(reg_file, encoding="utf-8") as f:
                        reg = json.load(f)
                    if reg:
                        episodes_by_podcast[slug] = reg
                except (json.JSONDecodeError, OSError):
                    pass

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
        eps = episodes_by_podcast.get(r["slug"])
        if eps:
            for e in sorted(eps, key=lambda x: x.get("pubdate", ""), reverse=True):
                lines.append(f"  - [{e['title']}]({e['url']})")

    total_episodes = sum(len(v) for v in episodes_by_podcast.values())
    with open(f"{PAGES_DIR}/llms.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    log(f"llms.txt regenere : {len(records)} podcast(s), {total_episodes} episode(s), {len(by_category)} categorie(s)")

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

def build_dashboard():
    """Tableau de bord interne (noindex) : etat du moteur, production, sante technique.
    N'affiche QUE des donnees mesurables par le systeme — aucun chiffre SEO invente."""
    records = load_data()
    today = datetime.date.today()

    # --- Previsions : prochains crons sur 7 jours (lus depuis .github/workflows/) ---
    DAYS_FR_SHORT = {0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi", 4: "Vendredi", 5: "Samedi", 6: "Dimanche"}
    slugs_names = {r["slug"]: r.get("podcast_name", r["slug"]) for r in records}
    upcoming = []
    wf_dir = ".github/workflows"
    if os.path.isdir(wf_dir):
        now_dt = datetime.datetime.now()
        for fname in os.listdir(wf_dir):
            if not (fname.startswith("podcast-btb-") and fname.endswith(".yml")):
                continue
            wf_slug = fname[len("podcast-btb-"):-len(".yml")]
            try:
                with open(os.path.join(wf_dir, fname), encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                continue
            m = re.search(r"cron:\s*'(\d+)\s+(\d+)\s+\S+\s+\S+\s+(\d+)'", content)
            if not m:
                continue
            hour = int(m.group(2))
            cron_dow = int(m.group(3))          # cron : 0=dimanche
            py_weekday = (cron_dow - 1) % 7      # python : 0=lundi
            days_ahead = (py_weekday - now_dt.weekday()) % 7
            candidate = (now_dt + datetime.timedelta(days=days_ahead)).replace(hour=hour, minute=0, second=0, microsecond=0)
            if candidate <= now_dt:
                candidate += datetime.timedelta(days=7)
            if (candidate - now_dt).days < 7:
                name = slugs_names.get(wf_slug)
                cat = next((r.get("categorie", "Autre") for r in records if r["slug"] == wf_slug), "Autre")
                upcoming.append((candidate, name or wf_slug, name is not None, cat))
    upcoming.sort()

    # --- Collecte des episodes par podcast ---
    episodes_root = f"{PAGES_DIR}/episodes"
    ep_by_podcast = {}
    all_ep_dates = []
    if os.path.isdir(episodes_root):
        for slug in os.listdir(episodes_root):
            reg_file = f"{episodes_root}/{slug}/_generated.json"
            if not os.path.exists(reg_file):
                continue
            try:
                with open(reg_file, encoding="utf-8") as f:
                    reg = json.load(f)
            except json.JSONDecodeError:
                continue
            dates = []
            for e in reg:
                d = parse_date_any(e.get("added_date", "")) or parse_date_any(e.get("pubdate", ""))
                if d:
                    dates.append(d)
                    all_ep_dates.append(d)
            ep_by_podcast[slug] = {
                "count": len(reg),
                "last": max(dates) if dates else None,
            }

    total_episodes = sum(v["count"] for v in ep_by_podcast.values())
    week_ago = today - datetime.timedelta(days=7)
    month_ago = today - datetime.timedelta(days=30)
    eps_this_week = sum(1 for d in all_ep_dates if d >= week_ago)
    eps_this_month = sum(1 for d in all_ep_dates if d >= month_ago)

    # --- Production par semaine (8 dernieres semaines) ---
    weekly = []
    for w in range(7, -1, -1):
        start = today - datetime.timedelta(days=today.weekday(), weeks=w)
        end = start + datetime.timedelta(days=6)
        count = sum(1 for d in all_ep_dates if start <= d <= end)
        weekly.append((start, count))
    max_weekly = max((c for _, c in weekly), default=1) or 1

    # --- Sante technique ---
    slugs_valid = set(r["slug"] for r in records)
    suspicious = []
    for r in records:
        lu = r.get("listenly_url", "")
        pu = r.get("podcast_url", "")
        if lu and "listenly.fr" not in lu:
            suspicious.append((r["slug"], f"listenly_url suspect : {lu[:60]}"))
        if pu and ("linkedin.com" in pu or "postimg" in pu):
            suspicious.append((r["slug"], f"podcast_url suspect : {pu[:60]}"))
    dup_names = {}
    for r in records:
        key = r.get("podcast_name", "").strip().lower()
        dup_names.setdefault(key, []).append(r["slug"])
    duplicates = [(name, slugs) for name, slugs in dup_names.items() if len(slugs) > 1]

    # --- Repartition par categorie ---
    by_cat = {}
    for r in records:
        by_cat[r.get("categorie", "?")] = by_cat.get(r.get("categorie", "?"), 0) + 1
    cats_sorted = sorted(by_cat.items(), key=lambda x: -x[1])

    # --- Tableau par podcast ---
    rows = []
    for r in sorted(records, key=lambda x: x.get("podcast_name", "")):
        slug = r["slug"]
        ep = ep_by_podcast.get(slug, {"count": 0, "last": None})
        last_label = format_date_fr(ep["last"]) if ep["last"] else "—"
        stale = ep["last"] is not None and (today - ep["last"]).days > 14
        stale_badge = ' <span class="warn">+14j sans épisode</span>' if stale else ""
        cta = r.get("episode_cta_target", "listenly")
        ep_index_url = f"https://listenly.fr/podcast-btb/episodes/{slug}/index.html"
        ep_link = f'<a href="{ep_index_url}" target="_blank" style="font-size:11px">Voir les épisodes →</a>' if ep["count"] else '<span style="color:#bbb;font-size:11px">—</span>'
        rows.append(f"""
<tr>
  <td class="pod-name"><a href="{r.get('fiche_url','')}" target="_blank">{r.get('podcast_name','')}</a></td>
  <td>{r.get('categorie','')}</td>
  <td style="text-align:center" data-sort="{ep['count']}">{ep['count']}</td>
  <td data-sort="{ep['last'].isoformat() if ep['last'] else ''}">{last_label}{stale_badge}</td>
  <td style="text-align:center">{cta}</td>
  <td>{ep_link}</td>
</tr>""")

    DAYS_ABBR = {0: "Lun", 1: "Mar", 2: "Mer", 3: "Jeu", 4: "Ven", 5: "Sam", 6: "Dim"}
    CAT_COLORS = ["#2e6bd6", "#27ae60", "#e67e22", "#8e44ad", "#c0392b", "#16a085", "#d4a017", "#7f8c8d", "#e84393", "#2c3e50"]

    # Palette stable : couleur attribuee par ordre alphabetique des categories presentes
    cats_in_upcoming = sorted(set(cat for _, _, known, cat in upcoming if known))
    cat_color = {c: CAT_COLORS[i % len(CAT_COLORS)] for i, c in enumerate(cats_in_upcoming)}

    # Regrouper par jour (7 prochains jours a partir d'aujourd'hui)
    days_seq = [datetime.date.today() + datetime.timedelta(days=i) for i in range(7)]
    by_day = {d: {} for d in days_seq}
    orphans_count = 0
    for dt, name, known, cat in upcoming:
        d = dt.date()
        if d in by_day:
            if known:
                by_day[d][cat] = by_day[d].get(cat, 0) + 1
            else:
                orphans_count += 1
    max_day_total = max((sum(v.values()) for v in by_day.values()), default=1) or 1

    cal_cols = []
    for d in days_seq:
        cats = by_day[d]
        total = sum(cats.values())
        segments = ""
        tip_lines = []
        if total:
            for cat, n in sorted(cats.items()):
                pct = round(100 * n / total)
                seg_h = max(8, int(90 * n / max_day_total))
                segments += f'<div class="seg" style="height:{seg_h}px;background:{cat_color[cat]}"></div>'
                tip_lines.append(f'<div class="tip-row"><i style="background:{cat_color[cat]}"></i><span>{cat}</span><b>{n} · {pct}%</b></div>')
        tip_html = "".join(tip_lines) if tip_lines else '<div class="tip-row"><span>Aucun épisode prévu</span></div>'
        count_label = f"+{total} épisode{'s' if total > 1 else ''}" if total else "—"
        today_cls = " cal-today" if d == datetime.date.today() else ""
        cal_cols.append(f"""
<div class="cal-col{today_cls}">
  <div class="tooltip">{tip_html}</div>
  <div class="cal-stack">{segments or '<div class="seg seg-empty"></div>'}</div>
  <div class="cal-day">{DAYS_ABBR[d.weekday()]} {d.day}</div>
  <div class="cal-count">{count_label}</div>
</div>""")
    orphan_note = f'<p class="note" style="margin-top:6px">⚠ {orphans_count} workflow(s) orphelin(s) programmé(s) cette semaine (échoueront sans produire).</p>' if orphans_count else ""
    prevision_calendar = f"""
<div class="calendar">{''.join(cal_cols)}</div>
{orphan_note}"""

    weekly_bars = "".join(
        f'<div class="bar-col"><div class="bar" style="height:{max(6, int(70 * c / max_weekly))}px" title="{c} fiche(s)"></div><span>{s.strftime("%d/%m")}</span><b>{c}</b></div>'
        for s, c in weekly
    )
    cat_rows = "".join(f"<tr><td>{label}</td><td style='text-align:center'>{n}</td></tr>" for label, n in cats_sorted)
    susp_rows = "".join(f"<li><b>{s}</b> — {msg}</li>" for s, msg in suspicious) or "<li>Aucune anomalie détectée ✓</li>"
    dup_rows = "".join(f"<li><b>{name}</b> : {', '.join(slugs)}</li>" for name, slugs in duplicates) or "<li>Aucun doublon détecté ✓</li>"

    # --- Pages orphelines : fichiers HTML presents sur disque mais absents du sitemap ---
    sitemap_path = f"{PAGES_DIR}/sitemap-podcast-btb.xml"
    sitemap_urls = set()
    if os.path.exists(sitemap_path):
        with open(sitemap_path, encoding="utf-8") as f:
            sitemap_content = f.read()
        sitemap_urls = set(re.findall(r"<loc>(.*?)</loc>", sitemap_content))
    orphan_pages = []
    for root, dirs, files in os.walk(PAGES_DIR):
        dirs[:] = [d for d in dirs if d != "data"]
        for fname in files:
            if not fname.endswith(".html") or fname in ("historique.html", "dashboard.html"):
                continue
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, PAGES_DIR).replace(os.sep, "/")
            url = f"https://listenly.fr/podcast-btb/{rel_path}"
            if url not in sitemap_urls:
                orphan_pages.append(rel_path)
    orphan_rows = "".join(f"<li>{p}</li>" for p in orphan_pages[:20]) or "<li>Aucune page orpheline détectée ✓</li>"
    if len(orphan_pages) > 20:
        orphan_rows += f"<li>… et {len(orphan_pages) - 20} de plus</li>"

    # --- Contenu trop court : fiches episode < 8000 caracteres (signe probable de generation sans transcript ou incomplete) ---
    thin_episodes = []
    if os.path.isdir(episodes_root):
        for slug in os.listdir(episodes_root):
            pod_dir = f"{episodes_root}/{slug}"
            if not os.path.isdir(pod_dir):
                continue
            for fname in os.listdir(pod_dir):
                if fname.endswith(".html") and fname != "index.html":
                    fpath = f"{pod_dir}/{fname}"
                    try:
                        size = os.path.getsize(fpath)
                        if size < 8000:
                            thin_episodes.append((slug, fname, size))
                    except OSError:
                        pass
    thin_rows = "".join(f"<li><b>{s}</b>/{f} — {sz} octets</li>" for s, f, sz in thin_episodes[:20]) or "<li>Aucune fiche anormalement courte ✓</li>"

    cron_paused = os.path.exists(f"{PAGES_DIR}/.cron-paused")
    has_upcoming = any(k for _, _, k, _ in upcoming)
    if cron_paused:
        air_html = '<span class="badge-air off"><i></i>OFF AIR — cron en pause</span>'
    elif has_upcoming:
        air_html = '<span class="badge-air on"><i></i>ON AIR — production active</span>'
    else:
        air_html = '<span class="badge-air off"><i></i>OFF AIR — rien de programmé</span>'

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Moteur Listenly GEO — Dashboard</title>
<meta name="robots" content="noindex, nofollow">
<style>
:root{{--bg:#f4f7fe;--card:#fff;--ink:#1b2540;--sub:#8b93a7;--accent:#4a6cf7;--accent-soft:#eef2ff;--ok:#22c98d;--warn-bg:#fdecec;--warn-ink:#e05252;--shadow:0 6px 24px rgba(27,37,64,.06)}}
*{{box-sizing:border-box}}
body{{font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif;color:var(--ink);margin:0;background:var(--bg);padding:36px 4vw 60px}}
h1{{font-size:26px;margin:0;font-weight:700}}
h1 b{{color:var(--accent)}}
h2{{font-size:15px;margin:34px 0 12px;font-weight:700;letter-spacing:.01em}}
.header{{display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:10px;margin-bottom:26px}}
.sub{{color:var(--sub);font-size:13px;margin:6px 0 0}}
.badge-air{{display:inline-flex;align-items:center;gap:8px;background:var(--card);box-shadow:var(--shadow);border-radius:999px;padding:8px 16px;font-size:12px;font-weight:700;letter-spacing:.03em}}
.badge-air.on{{color:#e05252}}
.badge-air.off{{color:var(--sub)}}
.badge-air i{{width:9px;height:9px;border-radius:50%;display:inline-block}}
.badge-air.on i{{background:#e05252;animation:pulse 1.6s infinite}}
.badge-air.off i{{background:#c3c9d6}}
.wave{{display:inline-flex;align-items:center;gap:2.5px;margin-right:12px;height:22px;vertical-align:middle}}
.wave i{{width:3.5px;background:var(--accent);border-radius:2px;animation:eq 1.4s ease-in-out infinite}}
.wave i:nth-child(1){{height:8px;animation-delay:0s}}
.wave i:nth-child(2){{height:16px;animation-delay:.2s}}
.wave i:nth-child(3){{height:22px;animation-delay:.4s}}
.wave i:nth-child(4){{height:13px;animation-delay:.6s}}
.wave i:nth-child(5){{height:7px;animation-delay:.8s}}
@keyframes eq{{0%,100%{{transform:scaleY(.55)}}50%{{transform:scaleY(1)}}}}
th.sortable{{cursor:pointer;user-select:none}}
th.sortable:hover{{color:var(--accent)}}
th.sortable::after{{content:' ⇅';font-size:9px;opacity:.5}}
th.sorted-asc::after{{content:' ↑';opacity:1;color:var(--accent)}}
th.sorted-desc::after{{content:' ↓';opacity:1;color:var(--accent)}}
.pod-name{{position:relative;padding-left:26px !important}}
.pod-name::before{{content:'🎙';position:absolute;left:6px;opacity:0;transform:translateX(-4px);transition:opacity .15s,transform .15s;font-size:12px}}
tr:hover .pod-name::before{{opacity:1;transform:translateX(0)}}
@keyframes pulse{{0%{{opacity:1}}50%{{opacity:.35}}100%{{opacity:1}}}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px}}
.card{{background:var(--card);border-radius:16px;padding:20px 22px;box-shadow:var(--shadow);transition:transform .15s}}
.card:hover{{transform:translateY(-2px)}}
.card .ico{{font-size:20px;margin-bottom:8px}}
.card .num{{font-size:32px;font-weight:800;line-height:1.1}}
.card .lbl{{font-size:11px;color:var(--sub);text-transform:uppercase;letter-spacing:.06em;margin-top:4px}}
.panel{{background:var(--card);border-radius:16px;box-shadow:var(--shadow);padding:20px 22px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th{{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--sub);padding:10px 12px;border-bottom:1px solid #eef0f6}}
td{{padding:10px 12px;border-bottom:1px solid #f3f5fa;vertical-align:top}}
tr:hover td{{background:#f8faff}}
a{{color:var(--accent);text-decoration:none}}
a:hover{{text-decoration:underline}}
.warn{{background:var(--warn-bg);color:var(--warn-ink);font-size:10px;font-weight:700;padding:2px 8px;border-radius:999px;white-space:nowrap}}
.search{{width:100%;max-width:340px;border:1px solid #e4e8f2;border-radius:10px;padding:10px 14px;font-size:13px;font-family:inherit;margin-bottom:12px;outline:none}}
.search:focus{{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}}
.bars{{display:flex;gap:12px;align-items:flex-end;padding-top:10px}}
.bar-col{{display:flex;flex-direction:column;align-items:center;gap:5px;flex:1}}
.bar{{width:100%;max-width:46px;background:linear-gradient(180deg,#6d8bff,#4a6cf7);border-radius:8px 8px 3px 3px;transition:filter .15s}}
.bar-col:hover .bar{{filter:brightness(1.12)}}
.bar-col span{{font-size:10px;color:var(--sub)}}
.bar-col b{{font-size:12px}}
ul.clean{{padding:4px 0 0 18px;font-size:13px;margin:0}}
ul.clean li{{margin-bottom:6px}}
.note{{font-size:11px;color:var(--sub);margin-top:28px;line-height:1.6}}
.calendar{{display:flex;gap:10px}}
.cal-col{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:6px;padding:8px 4px;border-radius:12px;cursor:default;transition:background .15s;position:relative}}
.cal-col:hover{{background:var(--accent-soft)}}
.tooltip{{position:absolute;bottom:calc(100% + 8px);left:50%;transform:translateX(-50%) translateY(4px);background:#1b2540;color:#fff;border-radius:10px;padding:10px 12px;font-size:11.5px;white-space:nowrap;opacity:0;pointer-events:none;transition:opacity .15s,transform .15s;z-index:10;box-shadow:0 8px 24px rgba(27,37,64,.25)}}
.tooltip::after{{content:'';position:absolute;top:100%;left:50%;transform:translateX(-50%);border:6px solid transparent;border-top-color:#1b2540}}
.cal-col:hover .tooltip{{opacity:1;transform:translateX(-50%) translateY(0)}}
.tip-row{{display:flex;align-items:center;gap:7px;margin:3px 0}}
.tip-row i{{width:9px;height:9px;border-radius:3px;flex-shrink:0}}
.tip-row span{{flex:1}}
.tip-row b{{margin-left:10px;color:#aab6ff}}
.cal-today{{background:var(--accent-soft);outline:2px solid #dbe4ff}}
.cal-stack{{display:flex;flex-direction:column-reverse;width:100%;max-width:46px;min-height:96px;justify-content:flex-start}}
.seg{{width:100%;border-radius:4px;margin-top:3px;transition:transform .12s}}
.cal-col:hover .seg{{transform:scaleX(1.08)}}
.seg-empty{{height:6px;background:#e9edf7}}
.cal-day{{font-size:11px;font-weight:700;color:var(--ink)}}
.cal-count{{font-size:11.5px;color:var(--accent);font-weight:700}}
.grid2{{display:grid;grid-template-columns:2fr 1fr;gap:18px;align-items:start}}
@media(max-width:860px){{.grid2{{grid-template-columns:1fr}}body{{padding:24px 16px 50px}}}}
</style>
</head>
<body>
<div class="header">
  <div>
    <h1><span class="wave"><i></i><i></i><i></i><i></i><i></i></span>Moteur <b>Listenly GEO</b></h1>
    <p class="sub">Vue d'ensemble de la production automatisée · généré le {format_date_fr(today)}</p>
  </div>
  {air_html}
</div>

<div class="cards">
  <div class="card"><div class="ico">🎙️</div><div class="num" data-target="{len(records)}">0</div><div class="lbl">Podcasts référencés</div></div>
  <div class="card"><div class="ico">📄</div><div class="num" data-target="{total_episodes}">0</div><div class="lbl">Fiches épisode totales</div></div>
  <div class="card"><div class="ico">⚡</div><div class="num" data-target="{eps_this_week}">0</div><div class="lbl">Épisodes cette semaine</div></div>
  <div class="card"><div class="ico">📈</div><div class="num" data-target="{eps_this_month}">0</div><div class="lbl">Épisodes sur 30 jours</div></div>
</div>

<h2>Prévision semaine · {sum(1 for _, _, k, _ in upcoming if k)} fiche(s) programmée(s)</h2>
<div class="panel">
{prevision_calendar}
</div>

<div class="grid2" style="margin-top:34px">
<div>
<h2 style="margin-top:0">Production par podcast</h2>
<div class="panel">
<input class="search" id="q" type="text" placeholder="🔍 Filtrer un podcast, une catégorie..." oninput="filterTable()">
<table id="prodTable">
<tr><th>Podcast</th><th>Catégorie</th><th class="sortable" onclick="sortTable(2,true)">Épisodes</th><th class="sortable" onclick="sortTable(3,false)">Dernier épisode</th><th>CTA</th><th>Fiches générées</th></tr>
{''.join(rows)}
</table>
</div>
</div>
<div>
<h2 style="margin-top:0">Répartition par catégorie</h2>
<div class="panel">
<table>
<tr><th>Catégorie</th><th>Podcasts</th></tr>
{cat_rows}
</table>
</div>

<h2>Anomalies CTA / liens</h2>
<div class="panel"><ul class="clean">{susp_rows}</ul></div>

<h2>Doublons potentiels</h2>
<div class="panel"><ul class="clean">{dup_rows}</ul></div>

<h2>Pages orphelines (absentes du sitemap)</h2>
<div class="panel"><ul class="clean">{orphan_rows}</ul></div>

<h2>Fiches anormalement courtes (&lt; 8 Ko)</h2>
<div class="panel"><ul class="clean">{thin_rows}</ul></div>
</div>
</div>

<h2>Production hebdomadaire (8 dernières semaines)</h2>
<div class="panel"><div class="bars">{weekly_bars}</div></div>

<p class="note">Ce tableau de bord n'affiche que les données de production internes au moteur. L'impact SEO réel (impressions, clics, citations IA) se mesure uniquement dans Google Search Console et vos analytics — le lien "Voir les épisodes" ouvre la liste publique des fiches épisode générées pour chaque podcast.</p>

<script>
function filterTable(){{
  var q = document.getElementById('q').value.toLowerCase();
  var rows = document.querySelectorAll('#prodTable tr');
  for(var i=1;i<rows.length;i++){{
    rows[i].style.display = rows[i].textContent.toLowerCase().indexOf(q) !== -1 ? '' : 'none';
  }}
}}

// Compteurs animes au chargement
document.addEventListener('DOMContentLoaded', function(){{
  document.querySelectorAll('.num[data-target]').forEach(function(el){{
    var target = parseInt(el.getAttribute('data-target'), 10) || 0;
    var dur = 900, start = null;
    function step(ts){{
      if(!start) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
      if(p < 1) requestAnimationFrame(step);
    }}
    requestAnimationFrame(step);
  }});
}});

// Tri par colonne (numerique ou date ISO via data-sort)
var sortState = {{}};
function sortTable(colIdx, numeric){{
  var table = document.getElementById('prodTable');
  var rows = Array.prototype.slice.call(table.rows, 1);
  var dir = sortState[colIdx] === 'desc' ? 'asc' : 'desc';
  sortState = {{}}; sortState[colIdx] = dir;
  rows.sort(function(a, b){{
    var va = a.cells[colIdx].getAttribute('data-sort') || a.cells[colIdx].textContent;
    var vb = b.cells[colIdx].getAttribute('data-sort') || b.cells[colIdx].textContent;
    if(numeric){{ va = parseFloat(va) || 0; vb = parseFloat(vb) || 0; }}
    if(va < vb) return dir === 'asc' ? -1 : 1;
    if(va > vb) return dir === 'asc' ? 1 : -1;
    return 0;
  }});
  rows.forEach(function(r){{ table.tBodies[0] ? table.tBodies[0].appendChild(r) : table.appendChild(r); }});
  table.querySelectorAll('th').forEach(function(th){{ th.classList.remove('sorted-asc','sorted-desc'); }});
  table.rows[0].cells[colIdx].classList.add(dir === 'asc' ? 'sorted-asc' : 'sorted-desc');
}}
</script>
</body>
</html>"""

    with open(f"{PAGES_DIR}/dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    log(f"Dashboard regenere : {len(records)} podcast(s), {total_episodes} episode(s)")

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
        build_dashboard()
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
    meta["categorie"] = normalize_category(meta.get("categorie", ""))
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
    build_dashboard()
    log(f"Categorie detectee : {meta['categorie']} ({cat_slug})")

if __name__ == "__main__":
    main()

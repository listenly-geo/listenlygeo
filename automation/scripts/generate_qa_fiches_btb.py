#!/usr/bin/env python3
"""
Moteur "trafic" podcast-btb : génère UNE fiche GEO par QUESTION (pas par épisode),
au rythme d'une nouvelle fiche par run (cron hebdomadaire recommandé), en épuisant
d'abord le stock de questions extraites avant de miner un nouvel épisode.

Logique d'économie :
  - L'extraction (téléchargement audio + transcription Whisper + extraction Q/R
    réelles via Claude) ne se fait QU'UNE FOIS par épisode, quand le stock de
    questions du podcast est vide.
  - Chaque run suivant consomme une question du stock déjà extrait et ne fait
    qu'UN appel Claude (mise en forme GEO de la fiche), sans re-transcrire.
  - Quand le stock est épuisé, le run suivant mine automatiquement le prochain
    épisode non traité du flux RSS.

Chaque fiche question :
  - CTA UNIQUE (bouton + 2 liens discrets) vers LISTENLY_URL du podcast — jamais
    vers Spotify/l'audio.
  - Même niveau d'exigence GEO que le N2 du Moteur 2 (JSON-LD, bio invité E-E-A-T,
    citation verbatim, stats/entités réelles, lisibilité humaine prioritaire).
  - JSON-LD BlogPosting comme schema principal (pas QAPage — reserve aux pages communautaires multi-reponses,
    mauvais usage pour du contenu editorial d'apres les consignes Google et confirme par Search Console).

Variables requises :
  ANTHROPIC_API_KEY
  PODCAST_SLUG        — slug du podcast déjà présent dans podcasts.json (Moteur N1)
Optionnelles :
  OPENAI_API_KEY      — requis uniquement au moment de miner un nouvel épisode
  RSS_URL             — sinon lu depuis podcasts.json
"""

import os, sys, re, json, datetime, unicodedata, tempfile, shutil
import urllib.request, urllib.error
import importlib.util

# Design system des fiches question (identique au moteur audiobook). Injecte directement
# par le script APRES generation Claude — jamais envoye dans le prompt ni ecrit par Claude.
# Ca economise des tokens en entree (plus besoin de decrire/repeter ces ~50 lignes a chaque
# appel) ET en sortie (Claude ne les recopie plus dans sa reponse a chaque fois), sans
# aucun impact sur le contenu, la structure GEO ou le JSON-LD — uniquement la maniere dont
# le CSS arrive dans le fichier final.
CSS_TEMPLATE = """*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: #ffffff; color: #1a1a1a; line-height: 1.75; font-size: 17px; }}
.wrapper {{ max-width: 720px; margin: 0 auto; padding: 0 20px 60px; }}
header {{ padding: 48px 0 32px; border-bottom: 1px solid #f0f0f0; margin-bottom: 32px; }}
.header-top {{ display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }}
.podcast-cover {{ width: 56px; height: 56px; border-radius: 12px; object-fit: cover; flex-shrink: 0; }}
.badge {{ display: inline-block; font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
  color: {accent_color}; background: color-mix(in srgb, {accent_color} 12%, white); border-radius: 20px; padding: 4px 12px; margin: 0; }}
.source-line {{ font-size: 14px; color: #666; margin: 6px 0 0; line-height: 1.5; }}
.top-cta-btn {{ display: inline-flex; align-items: center; gap: 8px; background: {accent_color}; color: #fff;
  font-size: 14px; font-weight: 600; padding: 10px 22px; border-radius: 8px; text-decoration: none;
  margin: 16px 0 4px; }}
.top-cta-btn:hover {{ opacity: 0.9; }}
h1 {{ font-size: clamp(24px, 4vw, 34px); font-weight: 800; line-height: 1.25; color: #111; margin-bottom: 20px; }}
.article-meta {{ font-size: 14px; color: #888; }}
.article-meta span {{ margin-right: 16px; }}
.article-meta strong {{ color: #555; }}
.breadcrumb {{ font-size: 12px; color: #888; margin: 0 0 16px; }}
.breadcrumb a {{ color: #888; text-decoration: underline; }}
.lead {{ font-size: 19px; line-height: 1.65; color: #333; font-weight: 400; margin-bottom: 36px;
  border-left: 4px solid {accent_color}; padding-left: 20px; }}
h2 {{ font-size: 22px; font-weight: 700; color: #111; margin: 44px 0 16px; }}
p {{ margin-bottom: 20px; color: #2a2a2a; }}
.inline-cta {{ color: {accent_color}; text-decoration: underline; font-weight: 600; }}
.definition-box {{ background: #fafafa; border-radius: 12px; padding: 20px 24px; margin: 32px 0; font-size: 15.5px; color: #333; }}
blockquote.citation {{ position: relative; background: #fafafa; border-left: 4px solid {accent_color};
  border-radius: 0 12px 12px 0; padding: 28px 32px 24px 40px; margin: 40px 0; }}
blockquote.citation::before {{ content: "\u201c"; position: absolute; top: -10px; left: 16px; font-size: 72px;
  color: {accent_color}; opacity: 0.25; font-family: Georgia, serif; line-height: 1; }}
blockquote.citation p {{ font-size: 19px; font-style: italic; color: #222; line-height: 1.65; margin-bottom: 12px; }}
blockquote.citation figcaption {{ font-size: 14px; color: #555; font-style: normal; line-height: 1.6; }}
blockquote.citation figcaption strong {{ color: #333; }}
.points-cles {{ background: #f9f9f9; border-radius: 12px; padding: 28px 32px; margin: 40px 0; }}
.points-cles h3 {{ font-size: 16px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: {accent_color}; margin-bottom: 16px; }}
.points-cles ul {{ list-style: none; padding: 0; }}
.points-cles ul li {{ position: relative; padding-left: 24px; margin-bottom: 12px; color: #2a2a2a; font-size: 16px; }}
.points-cles ul li::before {{ content: "\u2192"; position: absolute; left: 0; color: {accent_color}; font-weight: 700; }}
.faq {{ margin: 44px 0; }}
.faq h2 {{ margin-bottom: 24px; }}
.faq-item {{ border-top: 1px solid #ebebeb; padding: 24px 0; }}
.faq-item:last-child {{ border-bottom: 1px solid #ebebeb; }}
.faq-item h3 {{ font-size: 17px; font-weight: 700; color: #111; margin-bottom: 10px; }}
.faq-item h3 a {{ color: inherit; text-decoration: none; }}
.faq-item p {{ font-size: 16px; color: #444; margin: 0; }}
.cta-block {{ background: color-mix(in srgb, {accent_color} 8%, white); border: 1px solid color-mix(in srgb, {accent_color} 25%, white);
  border-radius: 14px; padding: 28px 32px; margin: 40px 0; text-align: center; }}
.cta-block .cta-btn {{ display: inline-block; background: {accent_color}; color: #fff; font-size: 15px; font-weight: 600;
  padding: 12px 28px; border-radius: 8px; text-decoration: none; margin-top: 10px; }}
footer {{ border-top: 1px solid #f0f0f0; padding-top: 28px; margin-top: 48px; font-size: 13px; color: #aaa; text-align: center; }}
@media (max-width: 600px) {{
  .cta-block {{ padding: 22px 20px; }}
  blockquote.citation {{ padding: 24px 20px 20px 28px; }}
  .points-cles {{ padding: 22px 20px; }}
}}"""

# Bloc STATIQUE du prompt de generation des fiches question — strictement identique sur
# TOUS les appels dans une meme langue (seules les valeurs specifiques a chaque podcast/
# question changent, via les jetons [[...]] resolus dans le bloc dynamique fourni a la
# suite). Permet le cache de prompt Anthropic : sur un run groupe de 50 podcasts d'affilee,
# ce bloc n'est facture plein tarif qu'une fois, ~10% du prix sur les appels suivants dans
# la fenetre de cache. CHAINES NORMALES (pas des f-strings) — aucun risque de backslash
# dans une expression, contrairement au bloc dynamique construit plus bas.
STATIC_QUESTION_PROMPT_FR = """Tu es un expert GEO (Generative Engine Optimization) spécialisé dans les podcasts B2B.

Ta mission est de générer une FICHE QUESTION complète en HTML autonome pour Listenly.fr.
STYLE VISUEL : moderne, clair, aéré — PAS le style magazine Forbes/HBR des autres fiches podcast-btb.
Concept : "la réponse se trouve dans un podcast". Police sans-serif system (-apple-system, Segoe UI, Helvetica,
Arial), beaucoup de blanc, coins arrondis généreux (12-20px), pas de colonnes serrées, pas de bordures dures —
des blocs respirants façon app moderne. Cette fiche répond à UNE SEULE question précise, extraite réellement
d'un épisode — ce n'est ni une fiche podcast, ni une fiche épisode complète.

## BALISES <head> OBLIGATOIRES
<title> (reformule la question en titre accrocheur, PAS juste la question copiée-collée) ET
<meta name="description" content="..."> (140-155 caractères, résumé direct de la réponse) + og:title/og:description/og:url/
og:type="article"/og:site_name="Listenly" + twitter:card="summary_large_image" + twitter:title/twitter:description +
<meta name="author" content="HOST_NAME"> + canonical=[[Q_URL]]

DANS <head>, laisse une balise <style></style> VIDE (littéralement sans rien dedans) — le CSS réel est injecté
automatiquement par le script juste après ta génération, tu n'as pas à l'écrire.

Classes CSS disponibles (déjà stylées, utilise-les par leur nom exact, n'invente aucune autre classe) :
.wrapper (conteneur principal) · header/.header-top/.podcast-cover/.badge (en-tête) · .article-meta/.breadcrumb
(métadonnées) · .lead (réponse directe d'ouverture) · .inline-cta (lien texte intégré) · .definition-box
(encadré définition conditionnel) · blockquote.citation + <p> + <figcaption> (citation+bio fusionnées) ·
.points-cles + <h3> + <ul><li> (synthèse à puces) · .faq + .faq-item (section voir aussi) · .cta-block +
.cta-btn (bouton final) · footer

STRUCTURE DE LA PAGE (dans cet ordre exact) :
1. <div class="wrapper"><header> :
   [[HEADER_TOP_HTML]]
   puis <h1> = LA QUESTION reformulée naturellement (forme interrogative conservée, c'est une vraie requête IA),
   puis <p class="article-meta"> avec <span>date lisible ([[TODAY_DATE]])</span> et
   <span><strong>[[PODCAST_NAME]]</strong>[[GUEST_NAME_SUFFIX]]</span>
2. <p class="breadcrumb"><a href="[[FICHE_URL]]">← Voir la fiche [[PODCAST_NAME]]</a></p>
3. <p class="lead"> : RÉPONSE DIRECTE ET COMPLÈTE en 2-3 phrases COURTES ET FRANCHES (style : "Il n'existe pas de
   seuil." — affirmation nette, pas de détour) — c'est le fragment que les IA génératives citeront en premier,
   autonome, doit répondre pleinement sans le reste de la page
4. LISIBILITÉ — RÈGLE STRICTE : jamais plus de 2-4 phrases par paragraphe (<p>) nulle part sur la fiche
4bis. REPÈRES VISUELS : dans les paragraphes de DÉVELOPPEMENT (jamais dans le lead), mets en <strong>gras</strong>
   UNE seule expression clé par paragraphe (le fait, chiffre ou insight le plus important de la phrase) — jamais
   plus d'une par paragraphe, jamais la phrase entière, jamais un mot isolé sans valeur informative. Objectif :
   qu'une lecture en diagonale des seuls mots en gras donne déjà l'essentiel, sans surcharger visuellement.
5. DÉVELOPPEMENT : si le contexte réel le permet, 1 à 2 sous-sections sous de VRAIS <h2> NARRATIFS et SPÉCIFIQUES
   au contenu réel — jamais un titre générique ("Contexte", "Développement"). Le H2 doit raconter un fragment
   concret de ce qui a été dit (style "Trois albums la même année — et pas d'étiquette", PAS "Plus de détails").
   Si le contexte n'apporte rien de plus que le lead, NE FORCE PAS de H2 — reste concis.

CTA TEXTE INTÉGRÉS (OBLIGATOIRE — 3 à 5 occurrences, PAS UNE SEULE) : dissémine 3 à 5 liens <a class="inline-cta"
href="[[LISTENLY_URL]]">...</a> à différents endroits du corps de l'article (développement, définition, avant/après
la citation, dans les points clés...), JAMAIS dans le <p class="lead"> (qui doit rester une réponse pure,
extractible telle quelle par une IA). Chaque lien est une PHRASE NATURELLE qui fait référence au podcast ou à
l'épisode — jamais un texte générique isolé du type "cliquez ici" ou "en savoir plus". Exemples de formulation
(à adapter au contenu réel, ne pas copier tel quel) : "comme [[SPEAKER_NAME]] l'explique
dans <a class="inline-cta" href="[[LISTENLY_URL]]">l'épisode</a>", "un point détaillé dans
<a class="inline-cta" href="[[LISTENLY_URL]]">[[PODCAST_NAME]]</a>", "évoqué plus largement dans
<a class="inline-cta" href="[[LISTENLY_URL]]">ce podcast</a>". Le lien fait TOUJOURS partie d'une phrase
grammaticalement naturelle, jamais un fragment de texte isolé ou souligné en dehors de son contexte de phrase.
6. <div class="definition-box"> CONDITIONNEL : UNIQUEMENT si un terme technique central est explicitement défini
   dans le contexte réel fourni — jamais inventé. N'en ajoute pas si rien ne s'y prête.
6bis. HOOK DE CURIOSITÉ (OBLIGATOIRE si le contexte le permet) : juste avant la citation (ou juste avant les
   points clés s'il n'y a pas de citation), UNE phrase qui évoque un détail concret et spécifique de l'épisode
   qui N'EST PAS développé sur cette fiche (une anecdote, une méthode précise, un autre chiffre, une autre partie
   de la conversation) — formulée comme un lien <a class="inline-cta" href="[[LISTENLY_URL]]">...</a> naturel, un
   de plus parmi les 3-5 CTA déjà demandés. Objectif : donner une vraie raison d'écouter l'épisode complet, pas
   répéter ce qui est déjà dit sur la fiche. RÈGLE ABSOLUE : n'invente jamais ce détail — si le contexte fourni
   n'a réellement rien d'autre à offrir, ignore cette instruction plutôt que de forcer un hook creux.
7. <blockquote class="citation"> CONDITIONNEL (si citation réelle ET/OU invité identifié) :
   <p>"citation verbatim réelle en italique"</p>
   <figcaption><strong>[[SPEAKER_NAME]]</strong> — [titre réel], [développement réel du parcours/de la
   légitimité en 2-4 phrases courtes, à partir du contexte biographique réel fourni]</figcaption>
   Si aucune citation mais invité identifié : même bloc sans la ligne <p>, juste le figcaption avec la bio.
   Si aucun invité identifiable : pas de blockquote, passe directement à la suite.
[[RELATED_BLOCK_INSTRUCTION]]
8. <div class="points-cles"><h3>Points clés à retenir</h3><ul> : 3 à 4
   puces, chacune 1 phrase courte de synthèse fidèle au contenu réel de la fiche (pas de répétition mot pour mot
   du lead — une vraie synthèse complémentaire). N'invente rien : chaque puce doit être déductible directement du
   contenu déjà présent sur la fiche.
9. <div class="cta-block"> : UN SEUL bouton <a class="cta-btn">Écouter l'épisode sur Listenly</a> → [[LISTENLY_URL]]
   (jamais Spotify, jamais l'audio brut) — en toute fin de page, après les points clés
10. <footer> : une ligne discrète "Fiche rédigée par l'équipe éditoriale Listenly"
- PAS de FAQ sur la question PRINCIPALE elle-même (une seule question par fiche, traitée en BlogPosting) — le
  bloc "Voir aussi" (si présent, cf. instruction ci-dessus, en <div class="faq"><h2> puis
  <div class="faq-item"> par entrée) ne concerne QUE les autres questions déjà publiées, jamais un doublon
  de la question de cette fiche
- Couleur d'accent déjà gérée par les classes CSS — n'ajoute jamais de style inline supplémentaire
- COHÉRENCE DES NOMS : première mention d'une personne = prénom + nom complet, mentions suivantes = nom de
  famille seul (jamais l'inverse, jamais de variation)

## JSON-LD (head)
@graph :
- Person (HOST_NAME/HOST_TITLE/worksFor HOST_COMPANY)
[[PERSON_GUEST_INSTRUCTION]]
- BlogPosting englobant — SCHEMA PRINCIPAL de la fiche (headline=H1, author={"@type":"Organization","name":"[nom
  reel de l'invite ou de l'entreprise source, ou HOST_NAME a defaut]"}, publisher={"@type":"Organization","name":"Listenly","url":"https://listenly.fr"},
  isPartOf={"@type":"PodcastSeries","name":"[[PODCAST_NAME]]","url":"[[LISTENLY_URL]]"}, datePublished, dateModified=today ([[TODAY_DATE]]),
  image=COVER_IMAGE si disponible, description=le meta description de la page,
  speakable cssSelector [".lead"[[SPEAKABLE_EXTRA]]])
- BreadcrumbList (1. Listenly (https://listenly.fr) 2. [[PODCAST_NAME]] ([[FICHE_URL]]) 3. cette question ([[Q_URL]]))
[[FAQ_JSONLD_LINE]]
[[MENTIONS_INSTRUCTION]]
IMPORTANT — NE PAS ajouter de schema QAPage : Google reserve QAPage aux pages communautaires ou plusieurs
utilisateurs repondent a une meme question (type forum), jamais a du contenu editorial ou une seule reponse
redactionnelle est fournie a partir d'une source (ici : le podcast). Utiliser QAPage ici serait un mauvais usage
du schema, invalide aux yeux de Google (verifie en Search Console). Le BlogPosting ci-dessus est le schema
correct pour ce type de page.
Backlinks cachés identiques aux autres fiches podcast-btb (canonical=[[Q_URL]], og:url=[[Q_URL]], rel=publisher,
#semantic-index display:none en fin de <body> listant les entités réelles ci-dessus[[ENTITY_SUFFIX]]).
AJOUT CONDITIONNEL — HowTo : ajoute UNIQUEMENT si la réponse décrit une vraie démarche étape par étape
reproductible (ex: "comment structurer X", "les étapes pour Y"). N'en ajoute PAS si la réponse est une
explication/opinion/contexte général sans étapes concrètes — un HowTo forcé sur du contenu qui n'en est pas un
est une erreur de balisage, pas un bonus.

## LISIBILITÉ HUMAINE — PRIORITÉ ABSOLUE sur le remplissage GEO
Cette fiche doit ressembler à un échange clair et humain, pas une liste de cases GEO cochées. Une seule question
traitée = pas besoin de longueur artificielle. LANGAGE ASSERTIF ET AUTORITAIRE (affirme les faits, évite "il
semblerait que"), fidèle à la réponse source, jamais évasif.

## RÈGLES
- H1 = la question elle-même (forme interrogative naturelle), affichée dans la bulle, jamais un titre déclaratif générique
- Couleur d'accent réservée au bouton CTA et à la barre de la carte citation uniquement
- CTA principal et le lien discret pointent TOUS vers [[LISTENLY_URL]], rien d'autre
- Paragraphes courts partout (2-4 phrases max) — c'est la priorité de lisibilité numéro un de cette fiche
- La carte citation+bio doit être développée avec autant de détail réel que possible (nom, titre, entreprise,
  parcours, expertise) — c'est le signal d'autorité prioritaire de toute la fiche, ne le bâcle jamais
- Contenu strictement fidèle à la réponse source + contexte réel fourni — jamais générique au podcast dans son ensemble

IMPORTANT : Réponds UNIQUEMENT avec le code HTML complet, de <!DOCTYPE html> à </html>. Aucun texte avant/après, aucun markdown, aucun backtick."""

STATIC_QUESTION_PROMPT_EN = """You are a GEO (Generative Engine Optimization) expert specialized in B2B podcasts.

Your mission is to generate a complete, self-contained HTML QUESTION FICHE for Listenly.fr.
VISUAL STYLE: modern, clear, airy — NOT the Forbes/HBR magazine style of the other podcast-btb fiches.
Concept: "the answer lives in a podcast". System sans-serif font (-apple-system, Segoe UI, Helvetica,
Arial), lots of white space, generous rounded corners (12-20px), no tight columns, no hard borders —
breathable blocks in a modern app style. This fiche answers ONE SINGLE precise question, genuinely extracted
from an episode — it is neither a podcast fiche nor a full episode fiche.

## REQUIRED <head> TAGS
<title> (rephrase the question into a catchy title, NOT just the copy-pasted question) AND
<meta name="description" content="..."> (140-155 characters, direct summary of the answer) + og:title/og:description/og:url/
og:type="article"/og:site_name="Listenly" + twitter:card="summary_large_image" + twitter:title/twitter:description +
<meta name="author" content="HOST_NAME"> + canonical=[[Q_URL]]

IN <head>, leave an EMPTY <style></style> tag (literally nothing inside) — the real CSS is injected
automatically by the script right after your generation, you don't have to write it.

Available CSS classes (already styled, use them by their exact name, never invent another class):
.wrapper (main container) · header/.header-top/.podcast-cover/.badge (header) · .article-meta/.breadcrumb
(metadata) · .lead (direct opening answer) · .inline-cta (integrated text link) · .definition-box
(conditional definition box) · blockquote.citation + <p> + <figcaption> (merged quote+bio) ·
.points-cles + <h3> + <ul><li> (bullet-point summary) · .faq + .faq-item (see-also section) · .cta-block +
.cta-btn (final button) · footer

PAGE STRUCTURE (in this exact order):
1. <div class="wrapper"><header>:
   [[HEADER_TOP_HTML]]
   then <h1> = THE QUESTION rephrased naturally (keep the interrogative form, this is a real AI query),
   then <p class="article-meta"> with <span>readable date ([[TODAY_DATE]])</span> and
   <span><strong>[[PODCAST_NAME]]</strong>[[GUEST_NAME_SUFFIX]]</span>
2. <p class="breadcrumb"><a href="[[FICHE_URL]]">← See the [[PODCAST_NAME]] fiche</a></p>
3. <p class="lead">: DIRECT, COMPLETE ANSWER in 2-3 SHORT, BLUNT sentences (style: "There is no threshold." —
   a plain statement, no hedging) — this is the fragment generative AIs will quote first, it must stand alone
   and fully answer the question without the rest of the page
4. READABILITY — STRICT RULE: never more than 2-4 sentences per paragraph (<p>) anywhere on the fiche
4bis. VISUAL ANCHORS: in DEVELOPMENT paragraphs only (never in the lead), bold <strong>one</strong> key phrase
   per paragraph (the single most important fact, number, or insight in that sentence) — never more than one per
   paragraph, never the whole sentence, never an isolated word with no informational value. Goal: a reader
   skimming only the bolded words should already get the gist.
5. DEVELOPMENT: if the real context allows it, 1 to 2 sub-sections under REAL NARRATIVE and SPECIFIC <h2>
   headings tied to the real content — never a generic title ("Context", "Development"). The H2 must tell a
   concrete fragment of what was actually said (style "Three albums the same year — and no label", NOT "More
   details"). If the context adds nothing beyond the lead, DO NOT force an H2 — stay concise.

INTEGRATED TEXT CTAs (MANDATORY — 3 to 5 occurrences, NOT JUST ONE): scatter 3 to 5 <a class="inline-cta"
href="[[LISTENLY_URL]]">...</a> links across different parts of the article body (development, definition,
before/after the quote, in the key takeaways...), NEVER inside the <p class="lead"> (which must stay a pure
answer, extractable as-is by an AI). Each link is a NATURAL SENTENCE referencing the podcast or episode —
never an isolated generic text like "click here" or "learn more". Example phrasings (adapt to the real
content, don't copy verbatim): "as [[SPEAKER_NAME]] explains in
<a class="inline-cta" href="[[LISTENLY_URL]]">the episode</a>", "a point detailed in
<a class="inline-cta" href="[[LISTENLY_URL]]">[[PODCAST_NAME]]</a>", "discussed at length in
<a class="inline-cta" href="[[LISTENLY_URL]]">this podcast</a>". The link is ALWAYS part of a grammatically
natural sentence, never an isolated or underlined text fragment out of its sentence context.
6. <div class="definition-box"> CONDITIONAL: ONLY if a central technical term is explicitly defined in the
   real context provided — never invented. Don't add one if nothing calls for it.
6bis. CURIOSITY HOOK (MANDATORY if the context allows it): right before the quote block (or right before the key
   takeaways if there's no quote), ONE sentence that references a concrete, specific detail from the episode
   that is NOT covered on this fiche (an anecdote, a precise method, another number, another part of the
   conversation) — phrased as a natural <a class="inline-cta" href="[[LISTENLY_URL]]">...</a> link, counted
   among the 3-5 CTAs already required. Goal: give a real reason to listen to the full episode, not repeat what
   the fiche already says. ABSOLUTE RULE: never invent this detail — if the provided context genuinely has
   nothing else to offer, skip this instruction rather than forcing a hollow hook.
7. <blockquote class="citation"> CONDITIONAL (if a real quote AND/OR an identified guest exist):
   <p>"real verbatim quote in italics"</p>
   <figcaption><strong>[[SPEAKER_NAME]]</strong> — [real title], [real development of their background/
   legitimacy in 2-4 short sentences, based on the real biographical context provided]</figcaption>
   If there's no quote but a guest is identified: same block without the <p> line, just the figcaption with the bio.
   If no guest is identifiable: no blockquote, move straight to the next section.
[[RELATED_BLOCK_INSTRUCTION]]
8. <div class="points-cles"><h3>Key takeaways</h3><ul>: 3 to 4
   bullets, each a short sentence summarizing content faithfully from the real content of the fiche (not a
   word-for-word repeat of the lead — a genuine complementary synthesis). Invent nothing: each bullet must be
   directly deducible from content already present on the fiche.
9. <div class="cta-block">: ONE SINGLE button <a class="cta-btn">Listen to the episode on Listenly</a> → [[LISTENLY_URL]]
   (never Spotify, never the raw audio) — at the very end of the page, after the key takeaways
10. <footer>: one discreet line "Written by the Listenly editorial team"
- NO FAQ on the MAIN question itself (one question per fiche, handled as BlogPosting) — the "See also"
  block (if present, per the instruction above, as <div class="faq"><h2> then <div class="faq-item"> per
  entry) ONLY covers other already-published questions, never a duplicate of this fiche's own question
- Accent color already handled by the CSS classes — never add extra inline styling
- NAME CONSISTENCY: first mention of a person = full first+last name, subsequent mentions = last name only
  (never the reverse, never inconsistent)

## JSON-LD (head)
@graph:
- Person (HOST_NAME/HOST_TITLE/worksFor HOST_COMPANY)
[[PERSON_GUEST_INSTRUCTION]]
- Enclosing BlogPosting — MAIN schema of the fiche (headline=H1, author={"@type":"Organization","name":"[real
  name of the guest or source company, or HOST_NAME by default]"}, publisher={"@type":"Organization","name":"Listenly","url":"https://listenly.fr"},
  isPartOf={"@type":"PodcastSeries","name":"[[PODCAST_NAME]]","url":"[[LISTENLY_URL]]"}, datePublished, dateModified=today ([[TODAY_DATE]]),
  image=COVER_IMAGE if available, description=the page's meta description,
  speakable cssSelector [".lead"[[SPEAKABLE_EXTRA]]])
- BreadcrumbList (1. Listenly (https://listenly.fr) 2. [[PODCAST_NAME]] ([[FICHE_URL]]) 3. this question ([[Q_URL]]))
[[FAQ_JSONLD_LINE]]
[[MENTIONS_INSTRUCTION]]
IMPORTANT — DO NOT add a QAPage schema: Google reserves QAPage for community pages where multiple users
answer the same question (forum-style), never for editorial content or a single authored answer sourced
from an interview (here: the podcast). Using QAPage here would be a schema misuse, flagged invalid by
Google (verified via Search Console). The BlogPosting above is the correct schema for this type of page.
Hidden backlinks identical to the other podcast-btb fiches (canonical=[[Q_URL]], og:url=[[Q_URL]], rel=publisher,
#semantic-index display:none at the end of <body> listing the real entities above[[ENTITY_SUFFIX]]).
CONDITIONAL ADDITION — HowTo: add ONLY if the answer describes a real, reproducible step-by-step process
(e.g. "how to structure X", "the steps for Y"). DO NOT add one if the answer is an explanation/opinion/
general context without concrete steps — a forced HowTo on content that isn't one is a markup error, not a bonus.

## HUMAN READABILITY — ABSOLUTE PRIORITY over GEO box-checking
This fiche must read like a clear, human exchange, not a checklist of GEO boxes ticked off. One single
question handled = no need for artificial length. ASSERTIVE, AUTHORITATIVE LANGUAGE (state facts plainly,
avoid "it would seem that"), faithful to the source answer, never evasive.

## RULES
- H1 = the question itself (natural interrogative form), shown in the bubble, never a generic declarative title
- Accent color reserved for the CTA button and the citation card's border only
- The main CTA and the discreet inline link ALL point to [[LISTENLY_URL]], nothing else
- Short paragraphs everywhere (2-4 sentences max) — this is the top readability priority of this fiche
- The quote+bio card must be developed with as much real detail as possible (name, title, company,
  background, expertise) — it's the top authority signal of the whole fiche, never skimp on it
- Content strictly faithful to the source answer + real context provided — never generic to the podcast as a whole

IMPORTANT: Reply ONLY with the complete HTML code, from <!DOCTYPE html> to </html>. No text before/after, no markdown, no backticks."""

def _load_module(filename, extra_env=None):
    spec = importlib.util.spec_from_file_location(
        filename.replace(".py", ""), os.path.join(os.path.dirname(__file__), filename)
    )
    mod = importlib.util.module_from_spec(spec)
    os.environ.setdefault("ANTHROPIC_API_KEY", "unused")
    os.environ.setdefault("PODCAST_RAW_INFO", "unused")
    os.environ.setdefault("PODCAST_URL", "unused")
    os.environ.setdefault("CONTACT_URL", "unused")
    os.environ.setdefault("LISTENLY_URL", "unused")
    for k, v in (extra_env or {}).items():
        os.environ.setdefault(k, v)
    spec.loader.exec_module(mod)
    return mod

API_KEY = os.environ["ANTHROPIC_API_KEY"]
SLUG    = os.environ["PODCAST_SLUG"].strip()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
LANGUAGE_OVERRIDE = os.environ.get("LANGUAGE_OVERRIDE", "").strip().lower()
if LANGUAGE_OVERRIDE not in ("fr", "en"):
    LANGUAGE_OVERRIDE = ""

PAGES_DIR     = "pages/podcast-btb"
DATA_FILE     = f"{PAGES_DIR}/data/podcasts.json"
QUESTIONS_DIR = f"{PAGES_DIR}/questions/{SLUG}"
REGISTRY_FILE = f"{QUESTIONS_DIR}/_qa_registry.json"
PARENT_FICHE  = f"{PAGES_DIR}/{SLUG}-podcast.html"

# Inbox alimentée par les repos clients "moteur autorité N2" (sync_transcript_to_moteur_trafic.py).
# Source ADDITIONNELLE et non-bloquante : si vide ou absente, comportement RSS inchangé.
INBOX_DIR          = f"automation/inbox/moteur-trafic-transcripts/{SLUG}"
INBOX_CONSUMED_DIR = f"{INBOX_DIR}/consumed"

def log(msg): print(f"[qa-btb:{SLUG}] {msg}", flush=True)

# --- Modules réutilisés tels quels (pas de duplication de logique) ---
_podcast_mod = None
_episode_mod = None

def podcast_mod():
    global _podcast_mod
    if _podcast_mod is None:
        _podcast_mod = _load_module("generate_podcast_btb.py")
    return _podcast_mod

def episode_mod():
    global _episode_mod
    if _episode_mod is None:
        _episode_mod = _load_module("generate_episode_fiches_btb.py", extra_env={"MAX_EPISODES": "1"})
    return _episode_mod

def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"^-+|-+$", "", s)[:70]

# --- Données podcast (registre partagé Moteur N1/N2) ---
def load_podcast_record():
    if not os.path.exists(DATA_FILE):
        log("ERREUR : podcasts.json introuvable — génère d'abord la fiche podcast (Moteur N1).")
        sys.exit(1)
    with open(DATA_FILE, encoding="utf-8") as f:
        records = json.load(f)
    for r in records:
        if r["slug"] == SLUG:
            return r, records
    log(f"ERREUR : aucun podcast avec le slug '{SLUG}' dans podcasts.json")
    sys.exit(1)

def enrich_from_fiche_html(record):
    needed = ["podcast_url", "contact_url", "listenly_url", "cover_image", "accent_color"]
    if all(record.get(k) for k in needed):
        return record
    if not os.path.exists(PARENT_FICHE):
        return record
    with open(PARENT_FICHE, encoding="utf-8") as f:
        html = f.read()
    if not record.get("podcast_url"):
        m = re.search(r'class="cta-listen"[^>]*href="([^"]+)"', html)
        if m: record["podcast_url"] = m.group(1)
    if not record.get("listenly_url"):
        m = re.search(r'"PodcastSeries".*?"url":\s*"([^"]+)"', html, re.DOTALL)
        if m: record["listenly_url"] = m.group(1)
    if not record.get("cover_image"):
        m = re.search(r'class="hero-image"[^>]*src="([^"]+)"', html)
        if m: record["cover_image"] = m.group(1)
    if not record.get("accent_color"):
        m = re.search(r'\.cta-listen\{[^}]*background:\s*(#[0-9a-fA-F]{3,6})', html)
        record["accent_color"] = m.group(1) if m else "#2e8bd6"
    return record

# --- Registre du stock de questions (par podcast) ---
def load_registry():
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return {
        "known_episode_guids": [],
        "current_episode": None,   # {guid, title, pubdate, audio_url}
        "context": None,           # {guest, real_quote, key_stats, entities, transcript_excerpt}
        "pending_qa": [],          # [{"q":..., "r":...}, ...] restant à publier
        "published": [],           # [{"slug","question","url","source_episode_title","source_episode_guid","added_date"}]
    }

def save_registry(reg):
    os.makedirs(QUESTIONS_DIR, exist_ok=True)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)

# --- Consomme un transcript déjà extrait, envoyé par un repo client "moteur autorité N2" ---
def try_load_from_inbox(registry):
    if not os.path.isdir(INBOX_DIR):
        return False  # aucun client relié à ce podcast — comportement RSS inchangé

    candidates = sorted(
        f for f in os.listdir(INBOX_DIR)
        if f.endswith(".json") and os.path.isfile(os.path.join(INBOX_DIR, f))
    )
    if not candidates:
        return False  # inbox vide pour l'instant — comportement RSS inchangé

    known = set(registry["known_episode_guids"])
    os.makedirs(INBOX_CONSUMED_DIR, exist_ok=True)

    for fname in candidates:
        fpath = os.path.join(INBOX_DIR, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log(f"AVERTISSEMENT inbox : fichier illisible ignoré ({fname}: {e})")
            shutil.move(fpath, os.path.join(INBOX_CONSUMED_DIR, fname))
            continue

        guid = payload.get("episode_guid") or fname
        dest = os.path.join(INBOX_CONSUMED_DIR, fname)

        if guid in known:
            # Déjà traité (par le RSS ou un run précédent) — on absorbe le doublon sans le republier
            log(f"Inbox : épisode déjà connu, fichier ignoré sans republication ({fname})")
            shutil.move(fpath, dest)
            continue

        qa = payload.get("real_qa") or []
        if not qa:
            log(f"Inbox : aucune question dans ce fichier — ignoré ({fname})")
            registry["known_episode_guids"].append(guid)
            shutil.move(fpath, dest)
            continue

        registry["known_episode_guids"].append(guid)
        registry["current_episode"] = {
            "guid": guid,
            "title": payload.get("episode_title", ""),
            "pubdate": payload.get("pubdate", ""),
            "audio_url": "",
        }
        registry["context"] = {
            "guest": payload.get("guest") or {},
            "real_quote": payload.get("real_quote", ""),
            "key_stats": payload.get("key_stats") or [],
            "entities": payload.get("entities") or [],
            "transcript_excerpt": (payload.get("transcript_full") or "")[:4000],
        }
        registry["pending_qa"] = qa
        shutil.move(fpath, dest)
        log(f"{len(qa)} question(s) mise(s) en stock depuis l'inbox client : {payload.get('episode_title','')}")
        return True

    return False  # tous les fichiers présents étaient des doublons/vides — retombe sur le RSS

# --- Mine un nouvel épisode (transcription + extraction réelle) ---
def mine_next_episode(podcast, registry, rss_url):
    emod = episode_mod()
    log(f"Lecture RSS : {rss_url}")
    try:
        episodes = emod.parse_episodes(emod.fetch_rss(rss_url))
    except Exception as e:
        log(f"ERREUR lecture RSS : {e}")
        return False

    known = set(registry["known_episode_guids"])
    candidates = [e for e in episodes if e["guid"] not in known]
    if not candidates:
        log("Aucun nouvel épisode disponible dans le flux — stock de questions épuisé, rien à publier ce run.")
        return False

    for ep in candidates:
        if not ep.get("audio_url"):
            log(f"Épisode sans audio, ignoré : {ep['title'][:60]}")
            registry["known_episode_guids"].append(ep["guid"])
            continue
        if not OPENAI_API_KEY:
            log("ERREUR : OPENAI_API_KEY absente — impossible de miner un nouvel épisode (moteur 100% basé sur le réel).")
            return False

        log(f"Mining épisode : {ep['title']}")
        tmpdir = tempfile.mkdtemp(prefix="qa_audio_")
        try:
            audio_path = os.path.join(tmpdir, "episode.mp3")
            size = emod.download_audio(ep["audio_url"], audio_path)
            audio_path = emod.compress_audio_if_needed(audio_path, size)
            audio_path = emod.speed_up_audio(audio_path)
            whisper_lang = podcast.get("language", "fr")
            transcript = emod.transcribe(audio_path, whisper_lang)
            if not transcript:
                log("Transcription vide — épisode ignoré.")
                registry["known_episode_guids"].append(ep["guid"])
                continue
            guest, qa, real_quote, key_stats, entities = emod.extract_real_qa(transcript, ep, podcast)
        except Exception as e:
            log(f"ÉCHEC mining ({e}) — épisode ignoré, tentative du suivant.")
            registry["known_episode_guids"].append(ep["guid"])
            continue
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        if not qa:
            log("Aucune question réelle extraite — épisode ignoré.")
            registry["known_episode_guids"].append(ep["guid"])
            continue

        registry["known_episode_guids"].append(ep["guid"])
        registry["current_episode"] = {
            "guid": ep["guid"], "title": ep["title"], "pubdate": ep["pubdate"],
            "audio_url": ep["audio_url"],
        }
        registry["context"] = {
            "guest": guest, "real_quote": real_quote,
            "key_stats": key_stats, "entities": entities,
            "transcript_excerpt": transcript[:4000],
        }
        registry["pending_qa"] = qa
        log(f"{len(qa)} question(s) mise(s) en stock pour {ep['title']}")
        return True

    return False

# --- Prompt de génération d'une fiche question ---
def build_question_prompt(podcast, question, ep_title, ep_pubdate, context, q_slug, q_url, today, related_questions=None):
    listenly_url = podcast.get("listenly_url", "")
    accent_color = podcast.get("accent_color") or "#2e8bd6"
    language = podcast.get("language", "fr")
    html_lang = "en" if language == "en" else "fr"
    related_questions = related_questions or []

    STRINGS = {
        "fr": {
            "eyebrow": "Question",
            "cta_listen": "Écouter l'épisode sur Listenly",
            "about_guest_label": "À propos de",
            "source_badge": "La réponse se trouve dans ce podcast",
            "source_label": "Extrait de l'épisode",
            "source_line": "Réponse extraite du podcast {podcast_name} — écoute l'épisode complet ci-dessous.",
            "editorial_disclosure": "Fiche éditoriale rédigée par Listenly à partir de l'épisode audio réel",
            "editorial_byline": "Fiche rédigée par l'équipe éditoriale Listenly",
            "topics_label": "Sujets :",
            "see_also_label": "Voir aussi",
            "key_takeaways_label": "Points clés à retenir",
        },
        "en": {
            "eyebrow": "Question",
            "cta_listen": "Listen to the episode on Listenly",
            "about_guest_label": "About",
            "source_badge": "The answer lives in this podcast",
            "source_label": "From the episode",
            "source_line": "Answer extracted from the {podcast_name} podcast — listen to the full episode below.",
            "editorial_disclosure": "Editorial summary by Listenly based on the real audio episode",
            "editorial_byline": "Written by the Listenly editorial team",
            "topics_label": "Topics:",
            "see_also_label": "See also",
            "key_takeaways_label": "Key takeaways",
        },
    }[language]

    entities_for_meta = (context.get("entities") or [])[:3]
    meta_line_topics = " ".join([STRINGS["topics_label"]]) + " " + " · ".join(entities_for_meta) if entities_for_meta else ""

    related_with_snippet = [r for r in related_questions if r.get("answer_snippet")][:3]
    if related_with_snippet:
        related_html_hint = "\n".join(
            f'- Q: "{r["question"]}" / R (extrait réel, à reprendre fidèlement, tu peux le reformuler légèrement '
            f'mais sans changer le sens) : "{r["answer_snippet"]}" / lien : {r["url"]}'
            for r in related_with_snippet
        )
        related_block_instruction = f"""
OBLIGATOIRE — section "{STRINGS['see_also_label']}" en toute fin de page (juste avant l'encadré "Points clés à
retenir"), sous un VRAI <h2>{STRINGS['see_also_label']}</h2>. Pour chacune des {len(related_with_snippet)}
questions RÉELLES ci-dessous, déjà publiées sur ce même podcast, un bloc structuré comme suit :
  - <h3> = la question, cliquable (lien vers l'URL fournie)
  - juste en dessous, 1-2 phrases COURTES du vrai extrait de réponse, visibles directement (pas juste un lien nu)
{related_html_hint}
Ces mêmes {len(related_with_snippet)} entrées doivent AUSSI être balisées en JSON-LD FAQPage (mainEntity: tableau
de Question/acceptedAnswer, reprenant exactement le texte affiché) — un FAQPage distinct, jamais sur la question
principale de cette fiche."""
        faq_jsonld_line = "- FAQPage distinct (mainEntity: les questions liees reelles listees dans le bloc \"voir aussi\", PAS la question principale de cette fiche)"
    elif related_questions:
        related_html_hint = "\n".join(f'- "{r["question"]}" → {r["url"]}' for r in related_questions[:3])
        related_block_instruction = f"""
OBLIGATOIRE — bloc "{STRINGS['see_also_label']}" en toute fin de page (juste avant le CTA final, sous un vrai
<h2>{STRINGS['see_also_label']}</h2>, liste discrète de liens, PAS des boutons) reprenant ces
{min(3, len(related_questions))} autres questions RÉELLES déjà publiées pour ce même podcast (texte du lien = la
question exacte, href = l'URL exacte fournie, ne modifie ni l'un ni l'autre) :
{related_html_hint}"""
        faq_jsonld_line = ""
    else:
        related_block_instruction = "\nAucune autre question publiée pour ce podcast pour l'instant — pas de bloc \"voir aussi\"."
        faq_jsonld_line = ""

    guest = context.get("guest") or {}
    guest_full_name = f"{guest.get('prenom','')} {guest.get('nom','')}".strip()
    speakable_extra = ', "blockquote.citation"' if guest_full_name else ""
    real_quote = (context.get("real_quote") or "").strip()
    key_stats = context.get("key_stats") or []
    entities = context.get("entities") or []
    bio_context = (guest.get("bio_context") or "").strip()

    # Strategie GEO (validee sur donnees Search Console reelles, 30/08/2026) : les fiches qui
    # s'appuient sur la notoriete supposee d'un invite/podcast performent nettement moins bien
    # (CTR ~1.19%, position moy ~19.3) que celles centrees sur l'expertise factuelle pure
    # (CTR ~3.76%, position moy ~14.0), a volume d'impressions pourtant inferieur. Mode par
    # defaut pour TOUS les nouveaux podcasts : "expertise" (aucune invocation de notoriete).
    # Mode "autorite" reserve manuellement (champ fiche_mode dans podcasts.json) aux invites a
    # la fois experts ET reconnus sectoriellement B2B (jamais une notoriete grand public).
    fiche_mode = podcast.get("fiche_mode", "expertise")
    if fiche_mode == "autorite":
        mode_instruction = """
## MODE DE FICHE : AUTORITE SECTORIELLE (reserve, valide manuellement pour ce podcast)
Cet invite est reconnu dans son secteur B2B specifique (pas une notoriete grand public) — tu peux t'appuyer sur
cette reconnaissance sectorielle en complement des faits (ex: mentionner son role/poids reconnu dans l'industrie),
mais jamais en remplacement des faits : chiffres reels, methode concrete et citation verbatim restent
obligatoires et prioritaires sur toute mention de notoriete."""
    else:
        mode_instruction = """
## MODE DE FICHE : EXPERTISE FACTUELLE (mode par defaut)
Ne t'appuie JAMAIS sur une notoriete supposee de l'invite ou du podcast pour donner de la valeur a la reponse —
meme si le nom est cite, ne presente jamais l'invite comme "celebre", "reconnu", "star de..." ou equivalent. La
legitimite de cette fiche repose uniquement sur la precision factuelle : chiffres reels, methode concrete,
citation verbatim, titre/poste verifiable. Un lecteur qui ne connait pas du tout ce podcast ni cet invite doit
trouver la reponse tout aussi utile et credible — le contenu doit se suffire entierement a lui-meme."""

    if guest_full_name:
        second_role_line = (
            f"\n- Second rôle réel mentionné : {guest.get('titre_secondaire')} chez {guest.get('entreprise_secondaire')}"
            if guest.get("entreprise_secondaire") else ""
        )
        guest_block = f"""
IDENTITÉ RÉELLE DE L'INVITÉ (extraite de la transcription — utilise-la telle quelle, n'invente RIEN de plus) :
- Nom : {guest_full_name}
- Titre/poste : {guest.get('titre') or '(non precise — ne pas inventer)'}
- Entreprise : {guest.get('entreprise') or '(non precisee — ne pas inventer)'}{second_role_line}
- Contexte biographique réel mentionné : {bio_context or '(aucun element supplementaire mentionne)'}

Cette identité et ce contexte biographique doivent être intégrés dans la carte citation+bio décrite plus bas
(section CARTE CITATION + BIO FUSIONNÉE) — c'est le signal d'autorité (E-E-A-T) le plus important de la fiche,
développe-le vraiment (mais sans jamais inventer un fait absent du contexte fourni — si le contexte biographique
est mince, reste bref plutôt que de meubler)."""
        guest_org_part = f', "worksFor":{{"@type":"Organization","name":"{guest.get("entreprise","")}"}}' if guest.get("entreprise") else ""
        guest_desc_part = f', "description":"{bio_context}"' if bio_context else ""
        guest_knows_about = ', "knowsAbout":[' + ",".join(f'"{e}"' for e in entities[:5]) + ']' if entities else ""
        person_guest_instruction = (
            f"AJOUT OBLIGATOIRE — Person distincte pour l'INVITÉ, la plus complète possible avec le matériel réel disponible : "
            f'{{"@type":"Person","name":"{guest_full_name}","jobTitle":"{guest.get("titre","")}"{guest_org_part}{guest_desc_part}{guest_knows_about}}}. '
            f"Si la transcription mentionne explicitement une URL, un site, un profil LinkedIn ou toute référence "
            f"vérifiable pour cet invité, ajoute-la en \"sameAs\" (tableau d'URLs) — UNIQUEMENT si elle est réellement "
            f"mentionnée, jamais inventée ou déduite."
        )
    else:
        guest_block = "\nAucun invité distinct identifiable — ne pas inventer d'identité, pas de carte citation+bio (simple pull-quote sans attribution si une citation existe)."
        person_guest_instruction = ""

    if real_quote:
        quote_block = f'\nCITATION VERBATIM RÉELLE (utilisable AVEC attribution nommée si elle éclaire CETTE question précise, sinon ignore-la) :\n"{real_quote}"'
    else:
        quote_block = "\nAucune citation verbatim disponible — pull-quote analytique SANS attribution."

    stats_block = "\n".join(f"- {s}" for s in key_stats) or "(aucune)"
    entities_block = ", ".join(entities) or "(aucune)"

    if entities:
        mentions_instruction = '- mentions : tableau d\'objets {"@type":"Thing","name":"..."} un par entité RÉELLE pertinente pour CETTE question'
    else:
        mentions_instruction = ""

    # UX/CVR fix (30/08/2026) : sur les fiches publiees, le concept "reponse extraite d'un
    # podcast" etait porte par un badge minuscule, et le SEUL bouton d'acces au podcast etait
    # tout en bas de page (cta-block final) -- un visiteur qui lit juste la reponse en haut
    # n'a aucune raison de scroller jusque-la. On ajoute donc une phrase d'explication claire
    # + un vrai bouton CTA visible des le haut de page (en plus du bouton final, pas a la
    # place), tous deux 100% generes en Python (jamais par le LLM) pour une fiabilite totale
    # sur les 682+ fiches existantes comme sur toutes les futures.
    cover_image = podcast.get('cover_image', '')
    source_line_text = STRINGS['source_line'].format(podcast_name=podcast['podcast_name'])
    top_cta_html = (
        '<a class="top-cta-btn" href="' + listenly_url + '">🎧 ' + STRINGS['cta_listen'] + '</a>'
    )
    if cover_image:
        header_top_html = (
            '<div class="header-top"><img class="podcast-cover" src="' + cover_image +
            '" alt="' + podcast['podcast_name'] + '"><div><span class="badge">' +
            STRINGS['source_badge'] + '</span><p class="source-line">' + source_line_text +
            '</p></div></div>' + top_cta_html
        )
    else:
        header_top_html = (
            '<span class="badge">' + STRINGS['source_badge'] + '</span><p class="source-line">' +
            source_line_text + '</p>' + top_cta_html
        )

    static_prompt = STATIC_QUESTION_PROMPT_EN if language == "en" else STATIC_QUESTION_PROMPT_FR

    guest_name_suffix = f" · {guest_full_name}" if guest_full_name else ""
    speaker_name = guest_full_name or podcast.get("host_name", "")
    entity_suffix = f" plus entity {guest_full_name}" if guest_full_name else ""

    dynamic_prompt = f"""## LA QUESTION RÉELLE À TRAITER (extraite fidèlement de la transcription de l'épisode)
Question : {question['q']}
Réponse (telle qu'extraite, fidèle à la transcription) : {question['r']}

## CONTEXTE RÉEL DE L'ÉPISODE SOURCE (matériel réel — priorité absolue sur toute invention)
- Épisode source : {ep_title} ({ep_pubdate or "date non renseignée"})
- Extrait de transcription (contexte, pas à citer intégralement) : "{context['transcript_excerpt'][:2500]}"
{guest_block}
{quote_block}

STATISTIQUES/CHIFFRES/DATES RÉELS de l'épisode (utilise UNIQUEMENT ceux pertinents pour CETTE question) :
{stats_block}

ENTITÉS NOMMÉES RÉELLES de l'épisode (utilise UNIQUEMENT celles pertinentes pour CETTE question) : {entities_block}

RÈGLE ABSOLUE : développe et illustre la réponse ci-dessus fidèlement — n'invente jamais un fait qui ne s'appuie
ni sur la réponse fournie, ni sur les stats/entités listées. Si le contexte plus large n'a rien à ajouter à cette
question précise, reste concis plutôt que de meubler.

{mode_instruction}
## CONTEXTE DU PODCAST PARENT
- PODCAST_NAME : {podcast['podcast_name']}
- HOST_NAME : {podcast.get('host_name','')}
- HOST_TITLE : {podcast.get('host_title','')}
- HOST_COMPANY : {podcast.get('host_company','')}
- CATEGORIE : {podcast.get('categorie','Général')}
- Fiche podcast parente (lien retour obligatoire) : {podcast['fiche_url']}

## CTA — UNIQUE OBJECTIF DE CONVERSION (IMPORTANT, NON NÉGOCIABLE)
- Le bouton principal ET le lien texte discret dans le corps pointent TOUS vers : {listenly_url}
  (fiche Listenly du podcast — JAMAIS Spotify, JAMAIS l'audio brut, JAMAIS de CTA contact)
- ACCENT_COLOR : {accent_color}
- COVER_IMAGE : {podcast.get('cover_image') or "(aucune)"}
- FICHE_URL (URL de CETTE fiche question — og:url/canonical) : {q_url}

## LANGUE DE RÉDACTION : {"ANGLAIS (ENGLISH)" if language == "en" else "FRANÇAIS"}
Rédige TOUT le contenu en {"anglais" if language == "en" else "français"}. Balise <html lang="{html_lang}">.

## RÉSOLUTION DES JETONS [[...]]
Les instructions générales ci-dessus (partie précédente du message) utilisent des jetons entre doubles crochets
— remplace-les PARTOUT où ils apparaissent par leur vraie valeur ci-dessous, jamais par le texte du jeton lui-même :
- [[TODAY_DATE]] = {today}
- [[PODCAST_NAME]] = {podcast['podcast_name']}
- [[FICHE_URL]] = {podcast['fiche_url']}
- [[LISTENLY_URL]] = {listenly_url}
- [[Q_URL]] = {q_url}
- [[HEADER_TOP_HTML]] = {header_top_html}
- [[GUEST_NAME_SUFFIX]] = {guest_name_suffix or "(chaîne vide — aucun invité identifié)"}
- [[SPEAKER_NAME]] = {speaker_name}
- [[SPEAKABLE_EXTRA]] = {speakable_extra or "(chaîne vide)"}
- [[FAQ_JSONLD_LINE]] = {faq_jsonld_line or "(chaîne vide — pas de FAQPage sur cette fiche)"}
- [[MENTIONS_INSTRUCTION]] = {mentions_instruction or "(chaîne vide — aucune entité à lister)"}
- [[ENTITY_SUFFIX]] = {entity_suffix or "(chaîne vide)"}
- [[PERSON_GUEST_INSTRUCTION]] = {person_guest_instruction or "(chaîne vide — aucun invité distinct identifiable)"}
- [[RELATED_BLOCK_INSTRUCTION]] = {related_block_instruction}"""

    return static_prompt, dynamic_prompt

def render_questions_block(podcast, published):
    """Bloc 'Questions couvertes' injecte directement dans la fiche N1 (podcast). Remplace
    depuis le 01/09/2026 la page index separee (questions/<slug>/index.html), qui etait du
    thin content a l'echelle du site (nombreuses fiches N1 classees 'Detectee, non indexee'
    par Google Search Console). La fiche N1, deja substantielle, devient le hub complet du
    podcast -- toute l'autorite de lien se concentre sur une seule page forte au lieu de se
    diviser entre une page riche et une page quasi vide.

    Rendu en cartes (01/09/2026, retour utilisateur : l'ancien rendu en simple liste etait
    "ecrase" en bas de page, incoherent avec le reste de la fiche qui utilise des cartes) --
    palette neutre volontairement (pas la couleur d'accent du podcast, non reutilisable ici
    de facon fiable) pour rester coherent quel que soit le podcast."""
    language = podcast.get("language", "fr")
    heading = "Questions couvertes" if language != "en" else "Questions covered"
    n = len(published)
    subtitle = (
        f"{n} question{'s' if n > 1 else ''} explorée{'s' if n > 1 else ''} dans ce podcast" if language != "en"
        else f"{n} question{'s' if n != 1 else ''} explored from this podcast"
    )

    items = "\n".join(
        """  <a class="qc-item" href="{url}">
    <div class="qc-q">{question}</div>
    <div class="qc-meta">{date} · {ep_title}</div>
  </a>""".format(
            url=q["url"], question=q["question"],
            date=q.get("added_date", ""), ep_title=q.get("source_episode_title", "")
        )
        for q in sorted(published, key=lambda x: x.get("added_date", ""), reverse=True)
    )

    return """
<style>
.qc-wrap {{ margin-top:48px; padding-top:32px; border-top:1px solid #ececec; }}
.qc-title {{ font-size:21px; font-weight:800; margin:0 0 4px; color:#0a0a0a; }}
.qc-sub {{ font-size:13px; color:#888; margin:0 0 20px; }}
.qc-list {{ display:flex; flex-direction:column; gap:10px; }}
.qc-item {{ display:block; padding:16px 20px; border:1px solid #ececec; border-radius:12px;
  text-decoration:none; color:inherit; background:#fafafa; transition:border-color .15s, box-shadow .15s, background .15s; }}
.qc-item:hover {{ border-color:#c9c9c9; background:#fff; box-shadow:0 3px 12px rgba(0,0,0,.06); }}
.qc-q {{ font-weight:700; font-size:15px; color:#111; line-height:1.4; margin-bottom:5px; }}
.qc-meta {{ font-size:12px; color:#999; }}
</style>
<div class="questions-covered qc-wrap">
  <h2 class="qc-title">{heading}</h2>
  <p class="qc-sub">{subtitle}</p>
  <div class="qc-list">
{items}
  </div>
</div>
""".format(heading=heading, subtitle=subtitle, items=items)


def update_n1_questions_block(podcast, published):
    """Injecte/met a jour le bloc 'Questions couvertes' dans la fiche N1 sur disque, entre des
    marqueurs HTML. Si les marqueurs sont absents (fiche N1 generee avant cette fonctionnalite),
    insere le bloc juste avant </body> -- auto-migration progressive des anciennes fiches, sans
    script de backfill separe necessaire."""
    n1_path = "{pages_dir}/{slug}-podcast.html".format(pages_dir=PAGES_DIR, slug=SLUG)
    if not os.path.exists(n1_path):
        log("AVERTISSEMENT : fiche N1 introuvable (" + n1_path + ") — bloc questions non mis à jour.")
        return
    with open(n1_path, encoding="utf-8") as f:
        n1_html = f.read()

    block = render_questions_block(podcast, published)
    start_marker = "<!-- QUESTIONS_COVERED_START -->"
    end_marker = "<!-- QUESTIONS_COVERED_END -->"
    if start_marker in n1_html and end_marker in n1_html:
        pre = n1_html.split(start_marker)[0]
        post = n1_html.split(end_marker)[1]
        new_html = pre + start_marker + block + end_marker + post
    else:
        insertion = start_marker + block + end_marker
        if "</body>" in n1_html:
            new_html = n1_html.replace("</body>", insertion + "\n</body>", 1)
        else:
            new_html = n1_html + insertion

    with open(n1_path, "w", encoding="utf-8") as f:
        f.write(new_html)
    log("Bloc 'Questions couvertes' mis à jour sur la fiche N1.")


def _unused_render_questions_index(podcast, published):
    language = podcast.get("language", "fr")
    html_lang = "en" if language == "en" else "fr"

    STRINGS = {
        "fr": {
            "eyebrow": "Listenly · Questions",
            "title_prefix": "Questions autour de",
            "desc_multi": "Retrouvez les {n} questions traitées par {name}, référencées par Listenly.",
            "desc_single": "Retrouvez la question traitée par {name}, référencée par Listenly.",
            "footer_link": "Voir la fiche podcast",
        },
        "en": {
            "eyebrow": "Listenly · Questions",
            "title_prefix": "Questions about",
            "desc_multi": "Explore the {n} questions covered by {name}, indexed by Listenly.",
            "desc_single": "Explore the question covered by {name}, indexed by Listenly.",
            "footer_link": "View the podcast page",
        },
    }[language]

    items = "\n".join(f"""
<div class="item">
  <a class="title" href="{q['url']}">{q['question']}</a>
  <div class="meta">{q.get('added_date','')} · {q.get('source_episode_title','')}</div>
</div>""" for q in sorted(published, key=lambda x: x.get("added_date",""), reverse=True))

    title = f"{STRINGS['title_prefix']} {podcast['podcast_name']}"
    n = len(published)
    description = (STRINGS["desc_multi"] if n > 1 else STRINGS["desc_single"]).format(n=n, name=podcast["podcast_name"])
    canonical = f"https://listenly.fr/podcast-btb/questions/{SLUG}/index.html"
    style = """
body{font-family:Helvetica,Arial,sans-serif;color:#1a1a1a;margin:0;background:#fff}
.wrapper{max-width:760px;margin:0 auto;padding:40px 20px 64px}
.eyebrow{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#666;margin-bottom:10px}
h1{font-size:clamp(24px,4vw,34px);font-weight:800;color:#0a0a0a;margin:0 0 24px}
.item{border-bottom:1px solid #f0f0f0;padding:16px 0}
.item a.title{font-size:17px;font-weight:700;color:#111;text-decoration:none}
.item a.title:hover{text-decoration:underline}
.item .meta{font-size:12px;color:#888;margin-top:4px}
footer{font-size:12px;color:#aaa;border-top:1px solid #eee;margin-top:40px;padding-top:16px}
"""
    return f"""<!DOCTYPE html>
<html lang="{html_lang}">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<style>{style}</style>
</head>
<body>
<div class="wrapper">
  <div class="eyebrow">{STRINGS['eyebrow']}</div>
  <h1>{title}</h1>
  {items}
  <footer>© {podcast['podcast_name']} — <a href="{podcast['fiche_url']}">{STRINGS['footer_link']}</a></footer>
</div>
</body>
</html>"""

def main():
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and os.path.exists(f"{PAGES_DIR}/.cron-paused-qa"):
        log("Cron moteur trafic (fiches question) en pause (fichier .cron-paused-qa present) — run ignore.")
        return

    pmod = podcast_mod()
    podcast, all_records = load_podcast_record()
    podcast = enrich_from_fiche_html(podcast)
    if LANGUAGE_OVERRIDE:
        podcast["language"] = LANGUAGE_OVERRIDE
        log(f"Langue forcée pour ce run : {LANGUAGE_OVERRIDE}")
    rss_url = os.environ.get("RSS_URL", "").strip() or podcast.get("rss_url", "")
    if not rss_url:
        log("ERREUR : aucun RSS_URL — ni en variable, ni dans podcasts.json.")
        sys.exit(1)
    if not podcast.get("listenly_url"):
        log("ERREUR : listenly_url manquant — impossible de fixer le CTA.")
        sys.exit(1)

    registry = load_registry()

    if not registry["pending_qa"]:
        mined = try_load_from_inbox(registry)
        if not mined:
            mined = mine_next_episode(podcast, registry, rss_url)
        save_registry(registry)
        if not mined:
            log("Rien de neuf à publier ce run — resynchronisation sitemap/dashboard quand même.")
            try:
                pmod.build_sitemap(); pmod.build_llms_txt(); pmod.build_historique(); pmod.build_dashboard()
            except Exception as e:
                log(f"AVERTISSEMENT : sync sitemap/dashboard échouée ({e})")
            return

    question = registry["pending_qa"].pop(0)
    context = registry["context"]
    ep = registry["current_episode"]
    today = datetime.date.today().isoformat()

    q_slug = slugify(question["q"]) or f"question-{len(registry['published'])+1}"
    os.makedirs(QUESTIONS_DIR, exist_ok=True)
    out_file = f"{QUESTIONS_DIR}/{q_slug}.html"
    if os.path.exists(out_file):
        q_slug = f"{q_slug}-{len(registry['published'])+1}"
        out_file = f"{QUESTIONS_DIR}/{q_slug}.html"
    q_url = f"https://listenly.fr/podcast-btb/questions/{SLUG}/{q_slug}.html"

    log(f"Génération fiche question : {question['q'][:80]}")
    emod = episode_mod()
    related_questions = list(reversed(registry["published"]))[:3]
    try:
        static_prompt, dynamic_prompt = build_question_prompt(podcast, question, ep["title"], ep.get("pubdate",""), context, q_slug, q_url, today, related_questions)
        # Haiku (moins cher, ~2x moins couteux que Sonnet) pour toute la generation de ce
        # moteur, y compris l'extraction/minage — decision explicite de reduire les couts
        # au maximum. A surveiller : fidelite des citations/chiffres extraits du transcript.
        # Bloc statique marque pour le cache de prompt Anthropic (voir call_claude) : sur un
        # run groupe de plusieurs podcasts d'affilee, seul le 1er appel paie plein tarif dessus.
        html_out = emod.clean_html(emod.call_claude(dynamic_prompt, static_prompt=static_prompt))
    except Exception as e:
        log(f"ERREUR génération fiche question : {e} — question remise en stock.")
        registry["pending_qa"].insert(0, question)
        save_registry(registry)
        sys.exit(1)

    if not html_out.lower().startswith("<!doctype"):
        log("ERREUR sortie invalide — question remise en stock.")
        registry["pending_qa"].insert(0, question)
        save_registry(registry)
        sys.exit(1)

    real_css = CSS_TEMPLATE.format(accent_color=podcast.get("accent_color") or "#2e8bd6")
    if "<style></style>" in html_out:
        html_out = html_out.replace("<style></style>", f"<style>{real_css}</style>", 1)
    elif "<style>" in html_out and "</style>" in html_out:
        # Claude a quand meme ecrit un peu de CSS malgre l'instruction — on remplace son
        # contenu par le vrai template plutot que de le laisser tel quel (fail-safe).
        html_out = re.sub(r"<style>.*?</style>", f"<style>{real_css}</style>", html_out, count=1, flags=re.DOTALL)
        log("AVERTISSEMENT : Claude a ecrit du CSS malgre l'instruction — remplace par le template reel.")
    else:
        log("ERREUR : aucune balise <style> trouvee dans la sortie — question remise en stock.")
        registry["pending_qa"].insert(0, question)
        save_registry(registry)
        sys.exit(1)

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_out)
    log(f"✓ Fiche question écrite : {out_file}")

    answer_snippet = question["r"].strip()
    if len(answer_snippet) > 160:
        answer_snippet = answer_snippet[:157].rsplit(" ", 1)[0] + "…"

    registry["published"].append({
        "slug": q_slug, "question": question["q"], "url": q_url,
        "source_episode_title": ep["title"], "source_episode_guid": ep["guid"],
        "added_date": today, "answer_snippet": answer_snippet,
    })
    if not registry["pending_qa"]:
        registry["current_episode"] = None
        registry["context"] = None
        log("Stock de questions épuisé pour cet épisode — le prochain run minera un nouvel épisode.")
    save_registry(registry)

    # Consolidation du 01/09/2026 : la page index separee (questions/<slug>/index.html) est
    # remplacee par un bloc "Questions couvertes" injecte directement dans la fiche N1 --
    # Google classait massivement ces pages index en "Detectee, non indexee" (thin content a
    # l'echelle du site). Voir update_n1_questions_block(). L'ancienne generation d'index.html
    # est retiree ; les URLs deja indexees redirigent vers la fiche N1 (voir .htaccess).
    update_n1_questions_block(podcast, registry["published"])

    for r in all_records:
        if r["slug"] == SLUG:
            r.update(podcast)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    try:
        pmod.build_sitemap(); pmod.build_llms_txt(); pmod.build_historique(); pmod.build_dashboard()
    except Exception as e:
        log(f"AVERTISSEMENT : sitemap/dashboard non régénérés ({e})")

if __name__ == "__main__":
    main()

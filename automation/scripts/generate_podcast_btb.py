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

MODEL      = "claude-sonnet-4-6"
PAGES_DIR  = "pages/podcast-btb"

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

def build_prompt(slug, today):
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
- CONTACT_URL (CTA contact, bouton "💼 Contacter [HOST_NAME]", LinkedIn hôte) : {CONTACT_URL}
- LISTENLY_URL (canonical + backlink) : {LISTENLY_URL}
- ACCENT_COLOR : {ACCENT_COLOR}
- COVER_IMAGE : {COVER_IMAGE or "(aucune fournie — omets l'image dans l'episode-card, ne mets pas de balise img cassée)"}
- Slug : {slug}
- Date de génération : {today}

## EXTRACTION OBLIGATOIRE AVANT DE RÉDIGER

1. LE H1 est le NOM DU PODCAST lui-même (PODCAST_NAME) — PAS une question, PAS un slogan. Juste le nom exact du podcast.
2. 4 POINTS CLÉS — faits autonomes citables par une IA, une phrase standalone chacun
3. 3-4 ANGLES GEO — questions que des professionnels poseraient à une IA sur ce sujet
4. UNE CITATION FORTE — inventée mais crédible, attribuée au HOST_NAME déduit, 15-25 mots, ton expert
5. 4 FAQ — vraies requêtes IA, réponses 2-3 phrases autonomes, sans mentionner le nom du podcast

## STRUCTURE HTML OBLIGATOIRE

### CSS (identique Moteur N2)
- body : Georgia, serif, #1a1a1a, line-height 1.75
- .wrapper : max-width 720px, margin auto, padding 32px 20px 64px
- .pod-badge : inline-flex, background {ACCENT_COLOR}+15, border {ACCENT_COLOR}+40, border-radius 20px, sans-serif 13px, color {ACCENT_COLOR}
- .hero-image : width 100%, max-width 200px, border-radius 12px, display block, margin 16px 0 (uniquement si COVER_IMAGE fournie)
- h1 : clamp(24px,4vw,36px), font-weight 700, color #111
- .meta-line : sans-serif 14px, color #666, flex wrap, gap 12px
- .cta-listen : background {ACCENT_COLOR}, color #fff, sans-serif 15px bold, padding 12px 24px, border-radius 8px
- .divider : border-top 2px solid #f0f0f0
- .lead-label : sans-serif 11px, font-weight 700, uppercase, letter-spacing .1em, color {ACCENT_COLOR}
- .lead : font-size 19px, italic, border-left 3px solid {ACCENT_COLOR}, padding-left 20px
- .key-box : background #f8f9fa, border-radius 10px, padding 24px 28px
- .key-box li : padding-left 24px, ::before content "→" color {ACCENT_COLOR}
- .article-body h2 : sans-serif 20px bold, border-top 1px solid #eee, margin-top 40px
- .article-body p : font-size 17px, color #2a2a2a
- .quote-block : border-left 3px solid {ACCENT_COLOR}, bg {ACCENT_COLOR}+08, italic 17px
- .faq-item h3 : 17px font-weight 600
- .episode-card : border 1px solid #e8e8e8, border-radius 12px, flex
- .episode-card img : width 140px, object-fit cover (uniquement si COVER_IMAGE fournie)
- .card-contact : background {ACCENT_COLOR}, color #fff, padding 8px 16px, border-radius 6px
- footer : sans-serif 12px, color #aaa, border-top 1px solid #eee
- #semantic-index : display none

### SECTIONS (ordre exact)
1. BADGE "🎙 [PODCAST_NAME] · Référencé sur Listenly"
2. HERO IMAGE : si {COVER_IMAGE or "aucune"} fournie, affiche <img class="hero-image" src="[COVER_IMAGE]" alt="[PODCAST_NAME]"> juste après le badge, avant le H1. Si aucune COVER_IMAGE fournie, n'affiche aucune balise img ici.
3. H1 = [PODCAST_NAME] (le nom du podcast lui-même, jamais une question)
4. META LINE : "Animé par [HOST_NAME] · [HOST_TITLE] chez [HOST_COMPANY] · [CATEGORIE] · ⏱ X min de lecture"
5. CTA GROUPE : "▶ Écouter le podcast" → {PODCAST_URL} ; "💼 Contacter [HOST_NAME]" → {CONTACT_URL}
6. DIVIDER
7. LEAD LABEL "Ce que couvre [PODCAST_NAME]" + LEAD (3-4 phrases citables)
8. KEY-BOX "📌 Les points clés" (4 bullets "→")
9. DIVIDER
10. ARTICLE BODY — 4 H2 exactement :
   - "Ce que ce podcast couvre vraiment"
   - "Pour qui ce podcast est essentiel" (3 profils d'audience)
   - "Ce que les épisodes révèlent vraiment" (patterns récurrents dans les titres)
   - "Ce que ça change concrètement"
11. QUOTE BLOCK « citation » — [HOST_NAME], [HOST_TITLE]
12. CTA MID discret "Découvrir tous les épisodes de [PODCAST_NAME]" → {PODCAST_URL}
13. DIVIDER
14. FAQ "❓ Le podcast répond à ces questions" (4 Q/R) + JSON-LD FAQPage obligatoire (mêmes questions). N'utilise JAMAIS la formulation "on répond" — toujours "le podcast répond" ou "il répond".
15. EPISODE CARD bas de page : cover si {COVER_IMAGE or "aucune"}, "Découvrir [PODCAST_NAME]", sous-titre [HOST_NAME] · [PODCAST_NAME], card-listen → {PODCAST_URL}, card-contact → {CONTACT_URL}
16. FOOTER : © [PODCAST_NAME] — [HOST_COMPANY] + lien "Analyse structurée par Listenly" → https://listenly.fr (dofollow, color #ccc)

## JSON-LD OBLIGATOIRE (dans <head>)
@graph : BlogPosting (headline=H1, author=[HOST_NAME]/[HOST_TITLE], publisher=Listenly, isPartOf={LISTENLY_URL}, speakable cssSelector [".lead",".key-box"]), FAQPage (les 4 questions), Person ([HOST_NAME]/[HOST_TITLE]/worksFor [HOST_COMPANY]), PodcastSeries ([PODCAST_NAME]/{PODCAST_URL}).

## BACKLINKS LISTENLY CACHÉS (obligatoires)
Dans <head> : canonical={LISTENLY_URL}, rel="publisher" href="https://listenly.fr", meta name="data-provider" content="Listenly".
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

def audit(html):
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
    return issues

def main():
    if not RAW_INFO.strip():
        log("ERREUR : PODCAST_RAW_INFO vide")
        sys.exit(1)

    slug = SLUG_OVERRIDE or guess_slug(RAW_INFO)
    out_file = f"{PAGES_DIR}/{slug}-podcast.html"
    log(f"Slug utilisé : {slug}")

    if os.path.exists(out_file):
        log(f"Fiche deja presente : {out_file} — skip.")
        return

    os.makedirs(PAGES_DIR, exist_ok=True)
    today = datetime.date.today().isoformat()

    try:
        html_out = clean_html(call_claude(build_prompt(slug, today)))
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

    issues = audit(html_out)
    if issues:
        log(f"AUDIT — {len(issues)} point(s) : {' | '.join(issues)}")
    else:
        log("AUDIT OK — tous criteres valides")

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_out)
    log(f"✓ Fiche ecrite : {out_file}")
    log(f"URL finale : https://listenly.fr/podcast-btb/{slug}-podcast.html")

if __name__ == "__main__":
    main()

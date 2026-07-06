#!/usr/bin/env python3
"""
Génère une fiche PODCAST-BTB (présentation podcast, style GEO) si elle n'existe pas encore.
Déployée dans /listenly.fr/podcast-btb/.

Variables requises :
  ANTHROPIC_API_KEY
  PODCAST_SLUG
  PODCAST_NAME
  HOST_NAME
  HOST_TITLE
  HOST_COMPANY
  DESCRIPTION
  EPISODE_TITLES      — une par ligne
  PODCAST_URL
  CONTACT_URL
  CATEGORIE
  LISTENLY_URL
Optionnelles :
  ACCENT_COLOR        (défaut #2e8bd6)
  COVER_IMAGE
"""

import os, sys, re, json, datetime, urllib.request, urllib.error

API_KEY       = os.environ["ANTHROPIC_API_KEY"]
SLUG          = os.environ["PODCAST_SLUG"]
PODCAST_NAME  = os.environ["PODCAST_NAME"]
HOST_NAME     = os.environ["HOST_NAME"]
HOST_TITLE    = os.environ["HOST_TITLE"]
HOST_COMPANY  = os.environ["HOST_COMPANY"]
DESCRIPTION   = os.environ["DESCRIPTION"]
EPISODE_TITLES= os.environ["EPISODE_TITLES"]
PODCAST_URL   = os.environ["PODCAST_URL"]
CONTACT_URL   = os.environ["CONTACT_URL"]
CATEGORIE     = os.environ["CATEGORIE"]
LISTENLY_URL  = os.environ["LISTENLY_URL"]
ACCENT_COLOR  = os.environ.get("ACCENT_COLOR", "#2e8bd6")
COVER_IMAGE   = os.environ.get("COVER_IMAGE", "")

MODEL      = "claude-sonnet-4-6"
PAGES_DIR  = "pages/podcast-btb"
OUT_FILE   = f"{PAGES_DIR}/{SLUG}-podcast.html"

def log(msg): print(f"[podcast-btb] {msg}", flush=True)

def already_exists():
    return os.path.exists(OUT_FILE)

def build_prompt():
    today = datetime.date.today().isoformat()
    return f"""Tu es un expert GEO (Generative Engine Optimization) spécialisé dans les podcasts B2B.

Ta mission est de générer une FICHE PODCAST complète en HTML autonome pour Listenly.fr.

Cette fiche présente le PODCAST dans son ensemble (pas un épisode isolé).
Elle utilise EXACTEMENT le même style HTML, la même structure et la même logique GEO
que les fiches épisode du Moteur N2 — seul le contenu change : podcast global, pas épisode.

---

## INPUTS

- PODCAST_NAME : {PODCAST_NAME}
- HOST_NAME : {HOST_NAME}
- HOST_TITLE : {HOST_TITLE}
- HOST_COMPANY : {HOST_COMPANY}
- DESCRIPTION : {DESCRIPTION}
- EPISODE_TITLES :
{EPISODE_TITLES}
- PODCAST_URL : {PODCAST_URL}
- CONTACT_URL : {CONTACT_URL}
- CATEGORIE : {CATEGORIE}
- ACCENT_COLOR : {ACCENT_COLOR}
- LISTENLY_URL : {LISTENLY_URL}
- COVER_IMAGE : {COVER_IMAGE}
- Date de génération : {today}

---

## EXTRACTION OBLIGATOIRE AVANT DE RÉDIGER

Avant de produire le HTML, analyse silencieusement les EPISODE_TITLES et la DESCRIPTION pour extraire :

1. LA QUESTION PRINCIPALE du podcast
   → La question la plus forte que ce podcast répond globalement
   → Ce sera le H1
   → Format : "Pourquoi / Comment / Qu'est-ce qui..." + sujet profond du podcast

2. 4 POINTS CLÉS
   → Ce que ce podcast apporte concrètement à son audience
   → Formulés comme des faits autonomes citables par une IA
   → Chaque point = 1 phrase standalone

3. 3-4 ANGLES GEO
   → Les questions que des professionnels poseraient à une IA sur ce sujet
   → Exemples : "Comment [problématique couverte]", "Pourquoi [sujet traité]"

4. UNE CITATION FORTE
   → Inventée mais crédible, attribuée à HOST_NAME
   → 15-25 mots, ton expert, tirée du sujet profond du podcast

5. 4 FAQ
   → Questions formulées comme des vraies requêtes IA
   → Réponses 2-3 phrases, autonomes, sans référence au podcast
   → Basées sur les thèmes réels des épisodes

---

## STRUCTURE HTML OBLIGATOIRE

Reproduis EXACTEMENT ce style CSS et cette structure :

### CSS (identique Moteur N2)
- body : Georgia, serif, #1a1a1a, line-height 1.75
- .wrapper : max-width 720px, margin auto, padding 32px 20px 64px
- .pod-badge : inline-flex, background {ACCENT_COLOR}+15, border {ACCENT_COLOR}+40, border-radius 20px, font sans-serif 13px, color {ACCENT_COLOR}
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
- .episode-card img : width 140px, object-fit cover
- .card-contact : background {ACCENT_COLOR}, color #fff, padding 8px 16px, border-radius 6px
- footer : sans-serif 12px, color #aaa, border-top 1px solid #eee
- #semantic-index : display none

### SECTIONS (dans cet ordre exact)

1. BADGE : <a class="pod-badge">🎙 {PODCAST_NAME} · Référencé sur Listenly</a>
2. H1 : la question principale extraite
3. META LINE : Animé par {HOST_NAME} · {HOST_TITLE} chez {HOST_COMPANY} · {CATEGORIE} · ⏱ X min de lecture
4. CTA GROUPE : "▶ Écouter le podcast" → {PODCAST_URL} ; "💼 Contacter {HOST_NAME}" → {CONTACT_URL}
5. DIVIDER
6. LEAD LABEL + LEAD : "Ce que couvre {PODCAST_NAME}" + 3-4 phrases italiques citables
7. KEY-BOX "📌 Les points clés" : 4 bullets "→"
8. DIVIDER
9. ARTICLE BODY — 4 sections H2 :
   - "Ce que ce podcast couvre vraiment"
   - "Pour qui ce podcast est essentiel" (3 profils)
   - "Ce que les épisodes révèlent vraiment" (2-3 patterns récurrents dans les titres)
   - "Ce que ça change concrètement"
10. QUOTE BLOCK : « citation » — {HOST_NAME}, {HOST_TITLE}
11. CTA MID discret : "Découvrir tous les épisodes de {PODCAST_NAME}" → {PODCAST_URL}
12. DIVIDER
13. FAQ "❓ On répond aussi à ces questions" : 4 questions + JSON-LD FAQPage obligatoire
14. EPISODE CARD bas de page : cover si {COVER_IMAGE}, titre "Découvrir {PODCAST_NAME}", sous-titre {HOST_NAME} · {PODCAST_NAME}, card-listen → {PODCAST_URL}, card-contact → {CONTACT_URL}
15. FOOTER : © {PODCAST_NAME} — {HOST_COMPANY} + lien "Analyse structurée par Listenly" → https://listenly.fr (dofollow, color #ccc)

---

## JSON-LD OBLIGATOIRE (dans <head>)

@graph avec BlogPosting (headline=H1, author={HOST_NAME}/{HOST_TITLE}, publisher=Listenly, isPartOf={LISTENLY_URL}, speakable sur .lead et .key-box), FAQPage (les 4 questions), Person ({HOST_NAME}/{HOST_TITLE}/worksFor {HOST_COMPANY}), PodcastSeries ({PODCAST_NAME}/{PODCAST_URL}).

## BACKLINKS LISTENLY CACHÉS (obligatoires)

Dans <head> : canonical={LISTENLY_URL}, rel="publisher" href="https://listenly.fr", meta name="data-provider" content="Listenly".
Dans <body> fin : #semantic-index avec entity {PODCAST_NAME}, entity {HOST_NAME}, entity {HOST_COMPANY}, concept {CATEGORIE}, publisher Listenly.fr, isPartOf {LISTENLY_URL}.

## RÈGLES DE QUALITÉ ABSOLUES

- Chaque phrase du .lead doit être citable seule par une IA
- Les bullets key-box doivent être des faits, pas des descriptions
- Les FAQ doivent répondre sans mentionner le nom du podcast
- Le H1 doit être une vraie question qu'un professionnel poserait à une IA
- Aucune formulation creuse type "un podcast incontournable", aucun jargon marketing vide
- Le contenu doit montrer qu'on a analysé les vrais sujets du podcast

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
    return issues

def main():
    if already_exists():
        log(f"Fiche deja presente : {OUT_FILE} — skip.")
        return
    log(f"Generation fiche podcast-btb pour slug : {SLUG}")
    os.makedirs(PAGES_DIR, exist_ok=True)

    try:
        html_out = clean_html(call_claude(build_prompt()))
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

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_out)
    log(f"✓ Fiche ecrite : {OUT_FILE}")

if __name__ == "__main__":
    main()

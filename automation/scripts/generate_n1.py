#!/usr/bin/env python3
"""
Génère la fiche Niveau 1 (présentation podcast) si elle n'existe pas encore.
Lit PODCAST_RAW_INFO (texte brut) et laisse Claude extraire nom/host/tagline/description.

Variables requises :
  ANTHROPIC_API_KEY
  PODCAST_SLUG
  PODCAST_RAW_INFO    — texte brut copié-collé (description Ausha, Spotify, etc.)
  SPOTIFY_SHOW_URL
  PODCAST_IMAGE_URL
  LISTENLY_SHOW_URL
  PLAUSIBLE_DOMAIN
"""

import os, sys, re, json, datetime, urllib.request, urllib.error

API_KEY      = os.environ["ANTHROPIC_API_KEY"]
SLUG         = os.environ["PODCAST_SLUG"]
RAW_INFO     = os.environ.get("PODCAST_RAW_INFO", "")
SPOTIFY_URL  = os.environ["SPOTIFY_SHOW_URL"]
IMAGE_URL    = os.environ.get("PODCAST_IMAGE_URL", "")
LISTENLY_URL = os.environ.get("LISTENLY_SHOW_URL", f"https://listenly.fr/podcast/show/{SLUG}")
PLAUSIBLE    = os.environ.get("PLAUSIBLE_DOMAIN", "listenly.fr")
MODEL        = "claude-sonnet-4-6"
PAGES_DIR    = "pages"
OUT_FILE     = f"{PAGES_DIR}/{SLUG}-podcast.html"

def log(msg): print(f"[n1] {msg}", flush=True)

def already_exists():
    return os.path.exists(OUT_FILE)

def build_prompt():
    today = datetime.date.today().isoformat()
    return f"""Tu es un expert GEO (Generative Engine Optimization). Génère une page HTML complète et autonome pour LA PRÉSENTATION d'un podcast, optimisée pour être citée par les IA (ChatGPT, Perplexity, Gemini, Claude).

INFORMATIONS BRUTES DU PODCAST (extrais toi-même nom, host, tagline, description, thématiques) :
---
{RAW_INFO}
---

À partir de ces infos brutes, tu dois déduire :
- Le nom exact du podcast
- Le(s) host(s)
- Une tagline percutante (si pas explicite, crées-en une)
- La description / positionnement
- Les grandes thématiques

RÈGLE FONDAMENTALE — FICHE FIGÉE :
Cette page présente LE PODCAST dans son ensemble. Elle NE MENTIONNE JAMAIS un épisode précis ou une date précise. Elle doit rester valable dans 2 ans.
Écrire pour l'IA : répondre aux VRAIES questions sur le SUJET DE FOND — jamais "que dit ce podcast".

DONNÉES FIXES :
- URL Spotify (CTA) : {SPOTIFY_URL}
- URL Listenly canonique : {LISTENLY_URL}
- Image cover : {IMAGE_URL}
- Date de génération : {today}
- Slug : {SLUG}

CONTRAINTES TECHNIQUES (respecter EXACTEMENT) :

1. Script Plausible dans <head> juste après canonical :
   <script defer data-domain="{PLAUSIBLE}" src="https://plausible.io/js/script.tagged-events.js"></script>

2. CTA NIVEAU 1 = SPOTIFY — RÈGLE ABSOLUE SANS EXCEPTION.
   Les 3 boutons principaux (topbar, hero, footer) pointent OBLIGATOIREMENT vers {SPOTIFY_URL}
   href="{SPOTIFY_URL}" target="_blank" rel="noopener"
   Classe Plausible : plausible-event-name=Spotify+Click--{SLUG}
   Texte bouton hero EXACT : "▶ Écouter sur Spotify"
   Texte bouton topbar EXACT : "▶ Écouter sur Spotify"
   JAMAIS de lien Listenly dans un bouton CTA de cette page.
   Le lien Listenly ({LISTENLY_URL}) n'apparaît QUE dans : canonical, JSON-LD url, BreadcrumbList.

3. Banderole sous le hero, libellé EXACT :
   "Fiche lisible par les modèles IA :" + badges ChatGPT · Perplexity · Gemini · Google AI · Copilot · Claude

4. Structure obligatoire :
   - Topbar sticky (logo Listenly + nom podcast + CTA Spotify)
   - Hero (cover + nom + tagline + pills thématiques + CTA Spotify)
   - Banderole IA
   - Section "À propos" : sujet de fond, positionnement
   - Grille "Thématiques explorées" : 6-8 thématiques FIGÉES
   - Mega FAQ : 6-8 questions sur le SUJET DE FOND (vraies questions de recherche)
   - FAQ accordion : 4-5 questions complémentaires
   - Section Host
   - Pour aller plus loin
   - Footer avec mention auteur + autorité éditoriale
   - Vector DB caché

5. JSON-LD @graph :
   - WebPage (speakable cssSelector vers .faq-a et .lead)
   - PodcastSeries (url={LISTENLY_URL}, author, publisher)
   - FAQPage (EXACTEMENT les mêmes 5-6 questions que la mega FAQ visible)
   - BreadcrumbList
   - Organization "Listenly" url "https://listenly.fr" comme publisher
   - "La rédaction Listenly" comme author
   - datePublished et dateModified = {today}

6. Vector DB caché :
   <div id="semantic-index" style="display:none" aria-hidden="true" lang="fr">
   5 blocs data-type : primary-entities, concepts, synonyms-acronyms, related-searches, guest-entities
   related-searches : 12+ vraies questions ("comment...", "quel...", "pourquoi...")

7. Design sombre style Spotify (fond ~#0a0a0e, Helvetica), accent cohérent, responsive 700px, prefers-reduced-motion.

8. Meta SEO :
   - title : 50-65 caractères MAXIMUM
   - meta description : 140-155 caractères MAXIMUM
   - canonical : https://listenly.fr/fiche-geo-ia/{SLUG}-podcast.html
   - og:url : https://listenly.fr/fiche-geo-ia/{SLUG}-podcast.html (OBLIGATOIRE — URL de la fiche elle-même)
   - og:image = {IMAGE_URL}
   - twitter:url : https://listenly.fr/fiche-geo-ia/{SLUG}-podcast.html

9. STATISTIQUES : uniquement si source réelle nommée ET datée. Sinon zéro chiffre.

10. Footer : "Rédigé par La rédaction Listenly" + ligne d'autorité éditoriale.

IMPORTANT : Réponds UNIQUEMENT avec le code HTML complet, depuis <!DOCTYPE html> jusqu'à </html>. Aucun texte avant ou après."""

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
    m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
    if m:
        l = len(m.group(1))
        if not (50 <= l <= 65): issues.append(f"title {l} car (50-65)")
    if html.count("<h1") > 1: issues.append("plus d un H1")
    if "semantic-index" not in html: issues.append("vector DB absente")
    if "FAQPage" not in html: issues.append("FAQPage absente")
    if "speakable" not in html: issues.append("speakable absent")
    if "datePublished" not in html: issues.append("datePublished absent")
    if SPOTIFY_URL not in html: issues.append("CTA Spotify absent")
    if "Fiche lisible par les mod" not in html: issues.append("banderole IA absente")
    return issues

def main():
    if already_exists():
        log(f"Fiche N1 deja presente : {OUT_FILE} — skip.")
        return
    if not RAW_INFO:
        log("ERREUR : PODCAST_RAW_INFO vide")
        sys.exit(1)

    log(f"Generation fiche N1 pour slug : {SLUG}")
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
        log("AUDIT OK — tous criteres GEO valides")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_out)
    log(f"✓ Fiche N1 ecrite : {OUT_FILE}")

if __name__ == "__main__":
    main()



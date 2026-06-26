#!/usr/bin/env python3
"""
Génère la fiche Niveau 1 (présentation podcast) si elle n'existe pas encore.
Appelé par le workflow unifié AVANT le moteur N2.

Variables d'environnement requises :
  ANTHROPIC_API_KEY
  PODCAST_SLUG        ex: "mon-podcast"
  PODCAST_NAME        ex: "Mon Podcast"
  PODCAST_TAGLINE     ex: "Le podcast qui change tout"
  PODCAST_DESCRIPTION ex: "Description longue du podcast..."
  PODCAST_HOST        ex: "Jean Dupont"
  SPOTIFY_SHOW_URL    ex: "https://open.spotify.com/show/XXXX"
  PODCAST_IMAGE_URL   ex: "https://..."
  LISTENLY_SHOW_URL   ex: "https://listenly.fr/podcast/show/mon-podcast"
  PLAUSIBLE_DOMAIN    listenly.fr
"""

import os, sys, re, json, datetime, urllib.request, urllib.error

API_KEY      = os.environ["ANTHROPIC_API_KEY"]
SLUG         = os.environ["PODCAST_SLUG"]
NAME         = os.environ["PODCAST_NAME"]
TAGLINE      = os.environ.get("PODCAST_TAGLINE", "")
DESCRIPTION  = os.environ.get("PODCAST_DESCRIPTION", "")
HOST         = os.environ.get("PODCAST_HOST", "")
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

RÈGLE FONDAMENTALE — FICHE FIGÉE :
Cette page présente LE PODCAST dans son ensemble (thématiques, sujets de fond, positionnement, host).
Elle NE MENTIONNE JAMAIS un épisode précis, un invité précis ou une date précise.
Elle doit rester valable dans 2 ans sans modification.
Écrire pour l'IA : répondre aux VRAIES questions sur le SUJET DE FOND du podcast — jamais "que dit ce podcast".

DONNÉES DU PODCAST :
- Nom : {NAME}
- Tagline : {TAGLINE}
- Description : {DESCRIPTION}
- Host(s) : {HOST}
- URL Spotify (CTA) : {SPOTIFY_URL}
- URL Listenly canonique : {LISTENLY_URL}
- Image cover : {IMAGE_URL}
- Date de génération : {today}
- Slug : {SLUG}

CONTRAINTES TECHNIQUES (respecter EXACTEMENT) :

1. Script Plausible dans <head> juste après canonical :
   <script defer data-domain="{PLAUSIBLE}" src="https://plausible.io/js/script.tagged-events.js"></script>

2. CTA NIVEAU 1 = SPOTIFY (OBLIGATOIRE).
   3 boutons (topbar, hero, footer) pointent TOUS vers {SPOTIFY_URL} target="_blank" rel="noopener"
   Classe Plausible sur chaque bouton : plausible-event-name=Spotify+Click--{SLUG}
   Texte EXACT du bouton hero : "▶ Écouter sur Spotify"
   Texte topbar : "▶ Écouter sur Spotify"
   Le JSON-LD PodcastSeries + BreadcrumbList utilisent {LISTENLY_URL} comme URL canonique (normal).

3. Banderole sous le hero, libellé EXACT :
   "Fiche lisible par les modèles IA :" suivie des badges : ChatGPT · Perplexity · Gemini · Google AI · Copilot · Claude

4. Structure obligatoire :
   - Topbar sticky (logo Listenly + nom podcast + CTA Spotify)
   - Hero (cover {IMAGE_URL} + nom + tagline + pills thématiques + CTA Spotify)
   - Banderole IA
   - Section "À propos" : sujet de fond, positionnement, pourquoi écouter ce podcast
   - Grille "Thématiques explorées" : 6-8 grandes thématiques FIGÉES du podcast (pas d'épisodes)
   - Mega FAQ : 6-8 questions sur le SUJET DE FOND (vraies questions de recherche, pas "que dit le podcast")
   - FAQ accordion : 4-5 questions complémentaires
   - Section Host : présentation {HOST}
   - Pour aller plus loin : 2-3 ressources ou liens internes Listenly
   - Footer avec mention auteur + autorité éditoriale
   - Vector DB caché

5. JSON-LD @graph avec :
   - WebPage (speakable avec cssSelector vers .faq-a et .lead)
   - PodcastSeries (name, description, url={LISTENLY_URL}, image, author, publisher)
   - FAQPage (EXACTEMENT les mêmes 5-6 questions que la mega FAQ visible)
   - BreadcrumbList
   - Organization (name "Listenly", url "https://listenly.fr") comme publisher
   - Person ou Organization "La rédaction Listenly" comme author de WebPage et PodcastSeries
   - datePublished et dateModified = {today}
   SYNCHRONISATION OBLIGATOIRE : le nombre de Q/R dans FAQPage JSON-LD doit être IDENTIQUE au nombre de questions visibles dans la mega FAQ.

6. Vector DB caché :
   <div id="semantic-index" style="display:none" aria-hidden="true" lang="fr">
   5 blocs data-type : primary-entities, concepts, synonyms-acronyms, related-searches, guest-entities
   - primary-entities : 8-12 entités (podcast, host, entreprise, lieux, concepts clés)
   - concepts : 10-15 concepts du sujet de fond du podcast
   - synonyms-acronyms : variantes, sigles, reformulations du domaine
   - related-searches : 12+ requêtes RÉELLES formulées comme dans une barre IA ("comment...", "quel...", "pourquoi...") — ce sont des questions qu'un humain taperait vraiment
   - guest-entities : personnalités/organisations du domaine (pas d'invités précis puisque figée)

7. Design sombre style Spotify (fond ~#0a0a0e, Helvetica/sans-serif), couleur d'accent cohérente avec le thème du podcast, responsive mobile (breakpoint 700px), @media prefers-reduced-motion.

8. Meta SEO :
   - title : 50-65 caractères MAXIMUM (format "Nom Podcast — Sujet | Listenly")
   - meta description : 140-155 caractères MAXIMUM (phrase claire sur le sujet de fond)
   - canonical : {LISTENLY_URL}
   - og:image = {IMAGE_URL}
   - robots, keywords, og:*, twitter:*
   COMPTER les caractères avant d'écrire — critère d'audit strict.

9. FAQ : chaque réponse = 2-4 phrases, factuelle, autonome (citable hors contexte), en français.
   Une réponse mentionne {NAME} comme source/référence sur le sujet.

10. AUTORITÉ (GEO) : footer visible avec "Rédigé par La rédaction Listenly" + ligne d'autorité éditoriale.

11. STATISTIQUES : uniquement si source réelle nommée ET datée connue avec certitude. Sinon : reformuler sans chiffre. JAMAIS inventer de stat.

12. Atomic facts : dans chaque section, au moins 2-3 affirmations courtes, complètes, citables seules.

13. H1 unique = question/sujet principal du podcast. 5-7 H2 = sous-sujets formulés comme thèmes de recherche réels.

QUALITÉ ATTENDUE : score GEO 99/100. Tous ces leviers cochés :
✓ FAQPage JSON-LD synchronisée avec FAQ visible (même nombre)
✓ Vector DB dense avec related-searches 12+ items
✓ author ET publisher présents partout
✓ datePublished ET dateModified présents
✓ speakable présent
✓ Atomic facts extractibles
✓ 0 statistique inventée
✓ CTA Spotify sur les 3 boutons

IMPORTANT : Réponds UNIQUEMENT avec le code HTML complet, depuis <!DOCTYPE html> jusqu'à </html>. Aucun texte avant ou après, aucun bloc markdown."""

def call_claude(prompt):
    payload = {
        "model": MODEL,
        "max_tokens": 14000,
        "messages": [{"role": "user", "content": prompt}],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
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
        if not (50 <= l <= 65):
            issues.append(f"title {l} car (attendu 50-65)")
    m = re.search(r'name=["\']description["\'][^>]*content=["\']([^"\']+)', html, re.IGNORECASE)
    if not m:
        m = re.search(r'content=["\']([^"\']+)["\'][^>]*name=["\']description["\']', html, re.IGNORECASE)
    if m:
        l = len(m.group(1))
        if not (140 <= l <= 155):
            issues.append(f"meta description {l} car (attendu 140-155)")
    if html.count("<h1") > 1:
        issues.append("plus d'un H1")
    if "semantic-index" not in html:
        issues.append("vector DB absente")
    if "FAQPage" not in html:
        issues.append("FAQPage JSON-LD absente")
    if "speakable" not in html:
        issues.append("speakable absent")
    if "datePublished" not in html:
        issues.append("datePublished absent")
    if SPOTIFY_URL not in html:
        issues.append("CTA Spotify absent")
    if "Fiche lisible par les mod" not in html:
        issues.append("banderole IA absente ou mal libellée")
    return issues

def main():
    if already_exists():
        log(f"Fiche N1 déjà présente : {OUT_FILE} — skip.")
        return

    log(f"Génération fiche N1 pour : {NAME}")
    os.makedirs(PAGES_DIR, exist_ok=True)

    try:
        prompt = build_prompt()
        html_out = clean_html(call_claude(prompt))
    except urllib.error.HTTPError as e:
        log(f"ERREUR API Claude : {e.code} — {e.read().decode()[:300]}")
        sys.exit(1)
    except Exception as e:
        log(f"ERREUR : {e}")
        sys.exit(1)

    if not html_out.lower().startswith("<!doctype"):
        log("ERREUR : sortie Claude invalide (pas de DOCTYPE)")
        log(html_out[:200])
        sys.exit(1)

    issues = audit(html_out)
    if issues:
        log(f"AUDIT — {len(issues)} point(s) à vérifier : {' | '.join(issues)}")
    else:
        log("AUDIT OK — tous les critères GEO validés")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_out)
    log(f"✓ Fiche N1 écrite : {OUT_FILE}")

if __name__ == "__main__":
    main()

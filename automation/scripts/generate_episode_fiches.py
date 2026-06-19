#!/usr/bin/env python3
"""
Génère automatiquement une fiche GEO HTML par épisode d'un podcast.
Lit le flux RSS, détecte les nouveaux épisodes, appelle l'API Claude,
écrit les fiches dans pages/ et tient un registre des épisodes déjà traités.

Variables d'environnement requises :
  - ANTHROPIC_API_KEY : clé API Anthropic
  - RSS_URL           : URL du flux RSS du podcast
  - PODCAST_SLUG      : slug court (ex: "yes-oui-work") pour nommer les fichiers
  - SPOTIFY_SHOW_URL  : URL Spotify de l'émission (pour le CTA)
  - PODCAST_IMAGE_URL : URL Postimages de la cover (og:image + hero)
  - PLAUSIBLE_DOMAIN  : domaine Plausible (ex: "listenly.fr")
"""

import os
import sys
import re
import json
import html
import hashlib
import datetime
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error

# ---------- Configuration ----------
API_KEY        = os.environ["ANTHROPIC_API_KEY"]
RSS_URL        = os.environ["RSS_URL"]
PODCAST_SLUG   = os.environ.get("PODCAST_SLUG", "podcast")
SPOTIFY_URL    = os.environ.get("SPOTIFY_SHOW_URL", "")
IMAGE_URL      = os.environ.get("PODCAST_IMAGE_URL", "")
PLAUSIBLE      = os.environ.get("PLAUSIBLE_DOMAIN", "listenly.fr")

PAGES_DIR      = "pages"
REGISTRY_FILE  = "automation/processed_episodes.json"
MODEL          = "claude-sonnet-4-6"   # bon rapport qualité/prix
MAX_NEW_PER_RUN = 1                     # 1 fiche par execution (1 episode = 1 fiche)

NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


# ---------- Utilitaires ----------
def log(msg):
    print(f"[gen] {msg}", flush=True)


def slugify(text):
    text = text.lower()
    text = re.sub(r"[àâä]", "a", text)
    text = re.sub(r"[éèêë]", "e", text)
    text = re.sub(r"[îï]", "i", text)
    text = re.sub(r"[ôö]", "o", text)
    text = re.sub(r"[ûüù]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:70]


def strip_html(raw):
    if not raw:
        return ""
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def load_registry():
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed": {}}


def save_registry(reg):
    os.makedirs(os.path.dirname(REGISTRY_FILE), exist_ok=True)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)


# ---------- Lecture du flux RSS ----------
def fetch_rss(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ListenlyGEO/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def parse_episodes(xml_bytes):
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    show_title = (channel.findtext("title") or "").strip()

    episodes = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        desc_raw = item.findtext("description") or item.findtext("content:encoded", default="", namespaces=NS) or ""
        desc = strip_html(desc_raw)
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link or title).strip()
        pubdate = (item.findtext("pubDate") or "").strip()
        duration = item.findtext("itunes:duration", default="", namespaces=NS)

        # ID stable de l'épisode
        ep_id = hashlib.sha1(guid.encode("utf-8")).hexdigest()[:12]

        episodes.append({
            "id": ep_id,
            "title": title,
            "description": desc,
            "link": link,
            "pubdate": pubdate,
            "duration": duration,
        })
    return show_title, episodes


# ---------- Appel API Claude ----------
def build_prompt(show_title, ep):
    return f"""Tu es un expert GEO (Generative Engine Optimization). Génère une page HTML complète et autonome pour UN épisode de podcast, optimisée pour être citée par les IA (ChatGPT, Perplexity, Gemini, Claude).

RÈGLE ABSOLUE GEO : tu écris pour une IA qui devra répondre à une question humaine en citant cette page. Les questions/réponses doivent correspondre aux VRAIES recherches que les gens font sur le SUJET de fond de l'épisode — jamais décrire l'épisode lui-même. Exemple : si l'épisode parle d'un DRH qui aborde le harcèlement moral, les questions sont "qu'est-ce que le harcèlement moral en entreprise ?", pas "que dit l'invité ?".

DONNÉES DE L'ÉPISODE :
- Podcast : {show_title}
- Titre de l'épisode : {ep['title']}
- Description : {ep['description']}
- Date : {ep['pubdate']}
- Durée : {ep['duration']}
- Lien Spotify de l'émission : {SPOTIFY_URL}
- Image cover : {IMAGE_URL}

CONTRAINTES TECHNIQUES (à respecter EXACTEMENT) :
1. Inclure dans le <head>, juste après la balise canonical :
   <script defer data-domain="{PLAUSIBLE}" src="https://plausible.io/js/script.tagged-events.js"></script>
2. Le bouton CTA principal (hero), le bouton topbar ET le lien Spotify du footer pointent vers {SPOTIFY_URL} et portent TOUS la classe :
   plausible-event-name=Spotify+Click--{slugify(show_title)}
3. Banderole sous le hero, libellé EXACT : "Fiche lisible par les modèles IA :" suivie des badges ChatGPT, Perplexity, Gemini, Google AI, Copilot, Claude.
4. Structure obligatoire : topbar sticky (logo Listenly + nom podcast + CTA) / hero (cover {IMAGE_URL} en og + titre + sous-titre + pills + CTA Spotify) / banderole IA / info-card 4 stats / section "à propos" (résumé du sujet) / mega FAQ 6-8 questions sur le SUJET (2 colonnes question/réponse) / FAQ accordion 4-5 questions / hosts ou intervenants / related (2 cartes) / footer / vector DB caché.
5. JSON-LD dans un <script type="application/ld+json"> avec @graph : WebPage (speakable) + PodcastEpisode (rattaché à la PodcastSeries {show_title}) + FAQPage (3 questions min reprises de la mega FAQ) + BreadcrumbList.
6. Vector DB caché : <div id="semantic-index" style="display:none" aria-hidden="true" lang="fr"> avec 4 blocs data-type : primary-entities, concepts, synonyms-acronyms, related-searches. Riche en entités et requêtes liées au SUJET.
7. Design sombre style Spotify (fond très sombre ~#0a0a0e, sans-serif Helvetica), UNE couleur d'accent cohérente avec le thème de l'épisode, responsive (mobile 700px), @media prefers-reduced-motion.
8. Meta SEO complets : title (< 65 car, format "Sujet — Podcast | Listenly"), description, keywords, robots, canonical https://listenly.fr/, og:* (dont og:image={IMAGE_URL}), twitter:*.
9. Toutes les réponses FAQ : 2-4 phrases, informatives, autonomes (citables hors contexte), en français, factuelles. Au moins une réponse mentionne le podcast {show_title} comme source.

QUALITÉ : la page doit pouvoir répondre directement à une question posée à une IA, et donner envie d'écouter le podcast. Ton sérieux, fond solide, zéro remplissage.

IMPORTANT : Réponds UNIQUEMENT avec le code HTML complet, depuis <!DOCTYPE html> jusqu'à </html>. Aucun texte avant ou après, aucun bloc markdown, aucune balise de code."""


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
    # Concatène les blocs texte
    parts = [b.get("text", "") for b in result.get("content", []) if b.get("type") == "text"]
    return "".join(parts).strip()


def clean_html_output(text):
    # Retire d'éventuels fences markdown
    text = re.sub(r"^```html\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


# ---------- Programme principal ----------
def main():
    log(f"Lecture du flux : {RSS_URL}")
    try:
        xml_bytes = fetch_rss(RSS_URL)
    except Exception as e:
        log(f"ERREUR fetch RSS : {e}")
        sys.exit(1)

    show_title, episodes = parse_episodes(xml_bytes)
    log(f"Podcast : {show_title} — {len(episodes)} épisodes dans le flux")

    registry = load_registry()
    processed = registry["processed"]

    new_eps = [ep for ep in episodes if ep["id"] not in processed]
    log(f"{len(new_eps)} nouveaux épisodes détectés")

    if not new_eps:
        log("Rien à faire.")
        return

    new_eps = new_eps[:MAX_NEW_PER_RUN]
    os.makedirs(PAGES_DIR, exist_ok=True)
    created = []

    for ep in new_eps:
        ep_slug = f"{PODCAST_SLUG}-ep-{slugify(ep['title'])}"
        filename = f"{ep_slug}.html"
        filepath = os.path.join(PAGES_DIR, filename)
        log(f"Génération : {ep['title'][:60]}...")

        try:
            prompt = build_prompt(show_title, ep)
            html_out = clean_html_output(call_claude(prompt))
            if not html_out.lower().startswith("<!doctype"):
                log(f"  ⚠ sortie inattendue, épisode ignoré")
                continue
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html_out)
            processed[ep["id"]] = {
                "title": ep["title"],
                "file": filename,
                "date": datetime.datetime.utcnow().isoformat() + "Z",
            }
            created.append(filename)
            log(f"  ✓ {filename}")
        except urllib.error.HTTPError as e:
            log(f"  ✗ HTTP {e.code} : {e.read().decode()[:200]}")
        except Exception as e:
            log(f"  ✗ {e}")

    save_registry(registry)
    log(f"Terminé. {len(created)} fiche(s) créée(s).")
    # Expose la liste pour l'étape de commit
    with open("automation/_last_created.txt", "w") as f:
        f.write("\n".join(created))


if __name__ == "__main__":
    main()


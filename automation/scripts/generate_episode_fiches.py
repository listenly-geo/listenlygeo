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

RÈGLE ABSOLUE : tu écris pour une IA qui devra répondre à une question humaine en citant cette page. Les questions/réponses doivent correspondre aux vraies recherches que les gens font sur le SUJET de l'épisode — pas décrire l'épisode lui-même.

DONNÉES DE L'ÉPISODE :
- Podcast : {show_title}
- Titre de l'épisode : {ep['title']}
- Description : {ep['description']}
- Date : {ep['pubdate']}
- Durée : {ep['duration']}
- Lien Spotify de l'émission : {SPOTIFY_URL}
- Image cover : {IMAGE_URL}

CONTRAINTES TECHNIQUES (à respecter exactement) :
1. Inclure dans le <head>, juste après la balise canonical :
   <script defer data-domain="{PLAUSIBLE}" src="https://plausible.io/js/script.tagged-events.js"></script>
2. Le bouton CTA principal et le bouton topbar pointent vers {SPOTIFY_URL} avec la classe :
   class="...existing... plausible-event-name=Spotify+Click--{slugify(show_title)}"
3. Banderole sous le hero : "Fiche lisible par les modèles IA :" suivie de ChatGPT, Perplexity, Gemini, Google AI, Copilot, Claude
4. Structure : topbar sticky / hero (cover {IMAGE_URL} + titre + CTA Spotify) / banderole IA / mega FAQ 6-8 questions sur le SUJET / FAQ accordion 4-5 questions / bloc JSON-LD (@graph avec PodcastEpisode + FAQPage + BreadcrumbList) / vector DB caché (#semantic-index display:none avec primary-entities, concepts, synonyms, related-searches) / footer
5. Design sombre style Spotify, sans-serif, une couleur d'accent cohérente avec le thème de l'épisode, responsive, prefers-reduced-motion.
6. Meta SEO complets : title, description, keywords, robots, canonical, og:*, twitter:*.

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

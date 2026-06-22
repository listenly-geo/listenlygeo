#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MarketForge GEO Système — Générateur d'articles de blog GEO depuis un podcast.

Flux :
  1. Lit le flux RSS du podcast client
  2. Détecte les nouveaux épisodes (registre JSON)
  3. Télécharge le MP3, le prépare pour Whisper (compression si > 25 Mo)
  4. Transcrit l'audio via OpenAI Whisper
  5. Génère un article de blog GEO + FAQ via Claude
  6. Produit un fichier HTML (avec emplacement audio réservé)
  7. Met à jour le registre

Variables d'environnement (configurées par le client dans GitHub) :
  OPENAI_API_KEY      : clé OpenAI (Whisper)
  ANTHROPIC_API_KEY   : clé Anthropic (Claude)
  RSS_URL             : flux RSS du podcast
  BLOG_NAME           : nom du blog / podcast
  COMPANY_NAME        : nom de l'entreprise cliente
  BLOG_IMAGE_URL      : image par défaut (og:image)
  SITE_BASE_URL       : URL de base où seront publiés les articles (ex: https://client.fr/articles)
  AUTHOR_NAME         : auteur affiché (défaut: la rédaction)
  ACCENT_COLOR        : couleur d'accent hex (défaut #2e8bd6)
  MAX_NEW_PER_RUN     : nb max d'articles par run (défaut 1)
  AUDIO_WEBHOOK_URL   : (optionnel, futur) webhook Zapier audio. Si absent → badge "bientôt".
"""

import os
import re
import sys
import json
import html
import subprocess
import unicodedata
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import requests

# ----------------------------------------------------------------------------
# Configuration depuis l'environnement
# ----------------------------------------------------------------------------
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
RSS_URL           = os.environ.get("RSS_URL", "")
BLOG_NAME         = os.environ.get("BLOG_NAME", "Notre Podcast")
COMPANY_NAME      = os.environ.get("COMPANY_NAME", "")
BLOG_IMAGE_URL    = os.environ.get("BLOG_IMAGE_URL", "")
SITE_BASE_URL     = os.environ.get("SITE_BASE_URL", "").rstrip("/")
AUTHOR_NAME       = os.environ.get("AUTHOR_NAME", "La rédaction")
ACCENT_COLOR      = os.environ.get("ACCENT_COLOR", "#2e8bd6")
MAX_NEW_PER_RUN   = int(os.environ.get("MAX_NEW_PER_RUN", "1"))
AUDIO_WEBHOOK_URL = os.environ.get("AUDIO_WEBHOOK_URL", "").strip()

ANTHROPIC_MODEL = "claude-sonnet-4-6"
WHISPER_MODEL   = "whisper-1"
WHISPER_MAX_BYTES = 24 * 1024 * 1024  # 24 Mo de marge sous la limite 25 Mo

OUTPUT_DIR   = os.environ.get("OUTPUT_DIR", "articles")
REGISTRY_PATH = os.path.join("automation", f"processed_{re.sub(r'[^a-z0-9]+', '-', BLOG_NAME.lower()).strip('-') or 'podcast'}.json")


# ----------------------------------------------------------------------------
# Utilitaires
# ----------------------------------------------------------------------------
def log(msg):
    print(f"[geo] {msg}", flush=True)


def slugify(text, maxlen=90):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:maxlen].strip("-") or "episode"


def load_registry():
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"processed": {}}
    return {"processed": {}}


def save_registry(reg):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)


# ----------------------------------------------------------------------------
# 1. Lecture du flux RSS
# ----------------------------------------------------------------------------
def fetch_rss_episodes():
    log(f"Lecture du flux : {RSS_URL}")
    r = requests.get(RSS_URL, timeout=30, headers={"User-Agent": "MarketForgeGEO/1.0"})
    r.raise_for_status()
    root = ET.fromstring(r.content)

    # namespaces courants
    ns = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("Flux RSS invalide : pas de <channel>")

    episodes = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        guid = (item.findtext("guid") or title).strip()
        desc = (item.findtext("description") or "").strip()
        pubdate = (item.findtext("pubDate") or "").strip()
        link = (item.findtext("link") or "").strip()

        # URL de l'audio (enclosure)
        audio_url = ""
        enclosure = item.find("enclosure")
        if enclosure is not None:
            audio_url = enclosure.get("url", "")

        episodes.append({
            "guid": guid,
            "title": title,
            "description": desc,
            "pubdate": pubdate,
            "link": link,
            "audio_url": audio_url,
        })
    log(f"{len(episodes)} épisodes dans le flux")
    return episodes


# ----------------------------------------------------------------------------
# 2. Téléchargement + préparation MP3
# ----------------------------------------------------------------------------
def download_audio(url, dest):
    log(f"Téléchargement audio : {url[:80]}...")
    with requests.get(url, stream=True, timeout=120, headers={"User-Agent": "MarketForgeGEO/1.0"}) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
    size = os.path.getsize(dest)
    log(f"Audio téléchargé : {size/1024/1024:.1f} Mo")
    return size


def compress_audio_if_needed(src, size):
    """Si le MP3 dépasse la limite Whisper, on le ré-encode en débit plus bas via ffmpeg."""
    if size <= WHISPER_MAX_BYTES:
        return src
    log("Fichier trop gros pour Whisper → compression ffmpeg (mono 32k)...")
    out = src.rsplit(".", 1)[0] + "_compressed.mp3"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-ac", "1", "-ar", "16000", "-b:a", "32k", out],
            check=True, capture_output=True
        )
        new_size = os.path.getsize(out)
        log(f"Compressé : {new_size/1024/1024:.1f} Mo")
        if new_size > WHISPER_MAX_BYTES:
            log("Toujours trop gros après compression — Whisper risque d'échouer.")
        return out
    except Exception as e:
        log(f"Échec compression ({e}) — on tente l'original.")
        return src


# ----------------------------------------------------------------------------
# 3. Transcription Whisper
# ----------------------------------------------------------------------------
def transcribe(audio_path):
    log("Transcription Whisper en cours...")
    with open(audio_path, "rb") as f:
        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={"file": (os.path.basename(audio_path), f, "audio/mpeg")},
            data={"model": WHISPER_MODEL, "language": "fr"},
            timeout=900,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Whisper erreur {resp.status_code}: {resp.text[:300]}")
    text = resp.json().get("text", "").strip()
    log(f"Transcription OK : {len(text)} caractères")
    return text


# ----------------------------------------------------------------------------
# 4. Génération de l'article GEO via Claude — HTML complet, niveau fiche Listenly
# ----------------------------------------------------------------------------
ARTICLE_PROMPT = """Tu es un expert GEO (Generative Engine Optimization). Génère une page HTML complète et autonome : un ARTICLE DE BLOG optimisé pour être cité par les IA (ChatGPT, Perplexity, Gemini, Claude), à partir de la TRANSCRIPTION d'un épisode de podcast.

RÈGLE ABSOLUE GEO : tu écris pour une IA qui devra répondre à une question humaine en citant cette page. Les questions/réponses doivent correspondre aux VRAIES recherches que les gens font sur le SUJET DE FOND de l'épisode — jamais décrire l'épisode lui-même. Exemple : si l'épisode parle d'un DRH qui aborde le harcèlement moral, les questions sont "qu'est-ce que le harcèlement moral en entreprise ?", pas "que dit l'invité ?". Mais tu peux citer l'invité comme source/expert (entité nommée = autorité).

DONNÉES :
- Podcast : {blog_name}
- Entreprise éditrice : {company}
- Titre de l'épisode : {ep_title}
- Description : {ep_desc}
- Couleur d'accent : {accent}
- Image de couverture (og:image) : {image_url}
- URL de publication : {page_url}

TRANSCRIPTION COMPLÈTE DE L'ÉPISODE (ta source principale — exploite-la en profondeur) :
\"\"\"
{transcript}
\"\"\"

CONTRAINTES TECHNIQUES (à respecter EXACTEMENT) :

1. STRUCTURE de l'article (dans cet ordre) :
   - <header> : nom du podcast (eyebrow), <h1> = une QUESTION/recherche réelle sur le sujet (pas le titre de l'épisode), méta (auteur + date{invite_meta}).
   - Réponse directe en intro (classe "lead") : 2-3 phrases extractibles répondant à la question du H1.
   - Banderole IA, libellé EXACT : "Article lisible par les modèles IA :" suivie de : ChatGPT · Perplexity · Gemini · Google AI · Copilot · Claude
   - Corps : 4-6 sections <h2> (sous-titres = sous-questions réelles du sujet), paragraphes riches et factuels nourris par la transcription. Cite l'invité nommément comme source d'expertise.
   - Bloc "Points clés" (atomic facts) : 4-6 puces courtes, autonomes, extractibles telles quelles par une IA.
   - Section FAQ : 5 questions/réponses sur le SUJET (2-4 phrases chacune, autonomes, citables hors contexte, factuelles). Au moins une réponse mentionne le podcast {blog_name} comme source.
   - <footer> : mention d'auteur visible "Rédigé par {author}" + courte ligne d'autorité éditoriale.
   - Vector DB caché (voir point 4).

2. JSON-LD dans <script type="application/ld+json"> avec @graph contenant :
   - BlogPosting (headline, description, datePublished {today}, dateModified {today}, author, publisher, image, mainEntityOfPage {page_url}, keywords)
   - FAQPage (les 5 questions de la FAQ)
   - Person pour l'invité s'il est identifiable (name de l'invité){person_hint}
   - Organization (l'éditeur : {company})
   - L'author DOIT être présent dans le BlogPosting.

3. META : title 50-65 caractères MAX (format "Sujet — {blog_name}"), meta description 140-155 caractères MAX, keywords, robots index/follow, canonical {page_url}, og:* (dont og:image={image_url}, og:type=article), twitter:card=summary_large_image. RESPECTE STRICTEMENT ces longueurs.

4. Vector DB caché : <div id="semantic-index" style="display:none" aria-hidden="true" lang="fr"> avec 4 blocs data-type : primary-entities, concepts, synonyms-acronyms, related-searches. Riche en entités (invité, entreprise, concepts du sujet) et requêtes liées au SUJET.

5. RÈGLE STATISTIQUES (TRÈS IMPORTANT) : n'inclure un chiffre QUE s'il provient de la transcription OU d'une source réelle nommée et datée que tu connais avec certitude. Sinon, reformule sans chiffre. N'invente JAMAIS de statistique.

6. DESIGN : article de blog éditorial CLAIR (fond clair #fff, corps en serif lisible, titres en sans-serif), accent {accent}, responsive (max 720px), @media prefers-reduced-motion. Sobre et premium (style éditorial type magazine pro).

7. NE PAS inclure de lecteur ni de mention audio (option gérée ailleurs).

QUALITÉ : la page doit répondre directement à une question posée à une IA. Fond solide tiré de la transcription, zéro remplissage, ton sérieux.

IMPORTANT : Réponds UNIQUEMENT avec le code HTML complet, depuis <!DOCTYPE html> jusqu'à </html>. Aucun texte avant ou après, aucun bloc markdown."""


def _extract_json(raw):
    """Parsing JSON robuste : gère fences, préfixes, et erreurs mineures."""
    raw = raw.strip()
    # Retirer d'éventuels fences markdown
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()
    # Si on a prérempli avec '{', la réponse commence après → on remet le '{'
    if not raw.startswith("{"):
        raw = "{" + raw
    # Tentative directe
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Tentative : isoler du premier { au dernier }
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = raw[start:end+1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    # Dernière tentative : retirer les virgules traînantes avant } ou ]
    cleaned = re.sub(r",(\s*[}\]])", r"\1", raw)
    return json.loads(cleaned)  # lève l'erreur si vraiment impossible


def generate_article_html(transcript, ep, slug):
    """Demande à Claude de produire directement le HTML complet de l'article GEO."""
    log("Génération de l'article GEO (HTML) via Claude...")
    transcript_trimmed = transcript[:28000]
    page_url = f"{SITE_BASE_URL}/{slug}.html" if SITE_BASE_URL else f"{slug}.html"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prompt = ARTICLE_PROMPT.format(
        blog_name=BLOG_NAME,
        company=COMPANY_NAME or BLOG_NAME,
        ep_title=ep["title"],
        ep_desc=re.sub(r"<[^>]+>", " ", ep["description"])[:1500],
        accent=ACCENT_COLOR,
        image_url=BLOG_IMAGE_URL or "",
        page_url=page_url,
        author=AUTHOR_NAME,
        today=today,
        invite_meta=" + invité si nommé dans la transcription",
        person_hint=" — déduis le nom depuis la transcription/description",
        transcript=transcript_trimmed,
    )
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": ANTHROPIC_MODEL,
            "max_tokens": 14000,
            "messages": [
                {"role": "user", "content": prompt},
                # Prefill : force Claude à démarrer directement par le HTML.
                {"role": "assistant", "content": "<!DOCTYPE html>"},
            ],
        },
        timeout=600,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Claude erreur {resp.status_code}: {resp.text[:300]}")
    html_out = resp.json()["content"][0]["text"]
    # Le prefill a mangé le <!DOCTYPE html>, on le remet
    if not html_out.lstrip().lower().startswith("<!doctype"):
        html_out = "<!DOCTYPE html>" + html_out
    # Nettoyer d'éventuels fences markdown résiduels
    html_out = re.sub(r"^```html\s*", "", html_out.strip())
    html_out = re.sub(r"\s*```$", "", html_out)
    # Vérification minimale
    if "</html>" not in html_out.lower():
        raise RuntimeError("HTML incomplet (pas de </html>) — réponse tronquée ?")
    log(f"Article HTML généré : {len(html_out)} caractères")
    return html_out


# ----------------------------------------------------------------------------
# 5. (FUTUR) Génération audio via webhook Zapier — emplacement réservé
# ----------------------------------------------------------------------------
def generate_audio(article, ep):
    """
    Si AUDIO_WEBHOOK_URL est défini, on enverra l'article au webhook Zapier
    qui renvoie une URL .mp3 synchrone. Sinon, on retourne None (badge "bientôt").
    """
    if not AUDIO_WEBHOOK_URL:
        return None
    # --- À ACTIVER QUAND PRÊT ---
    # payload = {
    #     "titre_episode": article["titre"],
    #     "contenu_episode": article["reponse_directe"] + " " + " ".join(s["contenu"] for s in article["sections"]),
    #     "nom_entreprise": COMPANY_NAME,
    #     "nom_podcast": BLOG_NAME,
    #     ... (autres champs de ton JSON Zapier)
    # }
    # r = requests.post(AUDIO_WEBHOOK_URL, json=payload, timeout=300)
    # r.raise_for_status()
    # return r.json().get("audio_url")
    return None


# ----------------------------------------------------------------------------
# 6. Construction du HTML de l'article
# ----------------------------------------------------------------------------
def build_html(article, ep, audio_url, slug):
    e = html.escape
    accent = ACCENT_COLOR
    page_url = f"{SITE_BASE_URL}/{slug}.html" if SITE_BASE_URL else f"{slug}.html"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    img = BLOG_IMAGE_URL

    sections_html = ""
    for s in article.get("sections", []):
        sections_html += f"<h2>{e(s.get('sous_titre',''))}</h2>\n<p>{s.get('contenu','')}</p>\n"

    points_html = ""
    if article.get("points_cles"):
        points_html = "<ul class='points'>" + "".join(f"<li>{e(p)}</li>" for p in article["points_cles"]) + "</ul>"

    faq_html = ""
    faq_jsonld = []
    for q in article.get("faq", []):
        faq_html += f"<div class='faq-item'><div class='faq-q'>{e(q.get('question',''))}</div><div class='faq-a'>{e(q.get('reponse',''))}</div></div>\n"
        faq_jsonld.append({
            "@type": "Question",
            "name": q.get("question", ""),
            "acceptedAnswer": {"@type": "Answer", "text": q.get("reponse", "")},
        })

    # Bloc audio : affiché UNIQUEMENT si une URL audio existe.
    # Sinon, rien n'est affiché (l'option audio sera proposée plus tard
    # dans le backend client, pas sur l'article public).
    if audio_url:
        audio_block = f"""
    <div class="audio-block">
      <div class="audio-label">🎧 Version audio de cet article</div>
      <audio controls preload="none" src="{e(audio_url)}"></audio>
    </div>"""
        audio_jsonld = f""",
    "audio": {{
      "@type": "AudioObject",
      "contentUrl": "{e(audio_url)}",
      "encodingFormat": "audio/mpeg"
    }}"""
    else:
        audio_block = ""   # aucun encart audio tant qu'il n'y a pas d'URL
        audio_jsonld = ""

    invite = article.get("invite", "")
    tags = article.get("tags", [])
    keywords = ", ".join(tags)

    jsonld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": article.get("titre", ""),
        "description": article.get("meta_description", ""),
        "datePublished": today,
        "dateModified": today,
        "author": {"@type": "Organization", "name": AUTHOR_NAME if not COMPANY_NAME else COMPANY_NAME},
        "publisher": {"@type": "Organization", "name": COMPANY_NAME or BLOG_NAME},
        "keywords": keywords,
        "mainEntityOfPage": {"@type": "WebPage", "@id": page_url},
    }
    if img:
        jsonld["image"] = img

    faqld = ""
    if faq_jsonld:
        faqld = "," + json.dumps({
            "@type": "FAQPage",
            "mainEntity": faq_jsonld,
        }, ensure_ascii=False)[1:-1]  # injecté dans @graph plus bas

    # On assemble un @graph : BlogPosting (+audio) + FAQPage
    graph_blogposting = json.dumps(jsonld, ensure_ascii=False)
    # insère le bloc audio dans le blogposting
    graph_blogposting = graph_blogposting[:-1] + audio_jsonld + "}"

    graph_items = [graph_blogposting]
    if faq_jsonld:
        graph_items.append(json.dumps({"@type": "FAQPage", "mainEntity": faq_jsonld}, ensure_ascii=False))
    graph = '{"@context":"https://schema.org","@graph":[' + ",".join(graph_items) + "]}"

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(article.get('titre',''))}</title>
<meta name="description" content="{e(article.get('meta_description',''))}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="author" content="{e(COMPANY_NAME or AUTHOR_NAME)}">
{f'<link rel="canonical" href="{e(page_url)}">' if SITE_BASE_URL else ''}
<meta property="og:type" content="article">
<meta property="og:title" content="{e(article.get('titre',''))}">
<meta property="og:description" content="{e(article.get('meta_description',''))}">
{f'<meta property="og:url" content="{e(page_url)}">' if SITE_BASE_URL else ''}
{f'<meta property="og:image" content="{e(img)}">' if img else ''}
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">
{graph}
</script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#fff;color:#1a1a25;font-family:Georgia,'Times New Roman',serif;line-height:1.75;-webkit-font-smoothing:antialiased}}
  .wrap{{max-width:720px;margin:0 auto;padding:0 24px}}
  .top{{font-family:Arial,sans-serif;font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:{accent};padding:48px 0 0}}
  h1{{font-family:Arial,sans-serif;font-size:clamp(1.8rem,4.5vw,2.6rem);font-weight:800;letter-spacing:-.02em;line-height:1.15;margin:14px 0 18px;color:#10101a}}
  .meta{{font-family:Arial,sans-serif;font-size:13px;color:#6b6b78;margin-bottom:28px}}
  .lead{{font-size:1.25rem;line-height:1.6;color:#2a2a38;font-weight:600;border-left:3px solid {accent};padding-left:18px;margin:22px 0 30px}}
  h2{{font-family:Arial,sans-serif;font-size:1.4rem;font-weight:700;margin:34px 0 12px;color:#15151f}}
  p{{margin:0 0 18px}}
  .points{{background:#f6f8fb;border-radius:10px;padding:20px 20px 20px 40px;margin:24px 0}}
  .points li{{margin-bottom:8px}}
  .audio-block{{font-family:Arial,sans-serif;background:#0e0e16;color:#fff;border-radius:12px;padding:20px;margin:30px 0}}
  .audio-label{{font-size:13px;font-weight:700;letter-spacing:.05em;margin-bottom:12px}}
  .audio-block audio{{width:100%}}
  .faq{{margin:40px 0;font-family:Arial,sans-serif}}
  .faq h2{{margin-bottom:18px}}
  .faq-item{{border-top:1px solid #e8e8ee;padding:16px 0}}
  .faq-q{{font-weight:700;font-size:15px;margin-bottom:6px;color:#15151f}}
  .faq-a{{font-size:15px;color:#41414e;line-height:1.6}}
  .footer{{font-family:Arial,sans-serif;border-top:1px solid #e8e8ee;margin-top:40px;padding:24px 0 60px;font-size:13px;color:#8a8a96}}
  .ai-banner{{font-family:Arial,sans-serif;font-size:12px;color:#8a8a96;background:#f6f8fb;border-radius:8px;padding:10px 14px;margin:30px 0}}
</style>
</head>
<body>
<article class="wrap">
  <div class="top">{e(BLOG_NAME)}</div>
  <h1>{e(article.get('titre',''))}</h1>
  <div class="meta">Par {e(COMPANY_NAME or AUTHOR_NAME)} · {datetime.now().strftime('%d/%m/%Y')}{f' · Avec {e(invite)}' if invite else ''}</div>

  <p class="lead">{e(article.get('reponse_directe',''))}</p>
{audio_block}

{sections_html}
{points_html}

  <div class="ai-banner">Article lisible par les modèles IA : ChatGPT · Perplexity · Gemini · Google AI · Copilot · Claude</div>

  <div class="faq">
    <h2>Questions fréquentes</h2>
    {faq_html}
  </div>

  <div class="footer">
    {e(BLOG_NAME)}{f' — {e(COMPANY_NAME)}' if COMPANY_NAME else ''} · Article généré à partir de l'épisode du podcast.
  </div>
</article>
</body>
</html>"""


# ----------------------------------------------------------------------------
# Programme principal
# ----------------------------------------------------------------------------
def main():
    # Vérifs de config
    missing = [k for k, v in {
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "RSS_URL": RSS_URL,
    }.items() if not v]
    if missing:
        log(f"ERREUR : variables manquantes : {', '.join(missing)}")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    reg = load_registry()
    episodes = fetch_rss_episodes()

    new_eps = [ep for ep in episodes if ep["guid"] not in reg["processed"]]
    log(f"{len(new_eps)} nouveaux épisodes détectés")
    new_eps = new_eps[:MAX_NEW_PER_RUN]

    created = 0
    for ep in new_eps:
        if not ep["audio_url"]:
            log(f"Pas d'audio pour '{ep['title']}' — ignoré")
            reg["processed"][ep["guid"]] = {"skipped": "no_audio", "title": ep["title"]}
            continue
        try:
            tmp_mp3 = os.path.join("/tmp", slugify(ep["title"]) + ".mp3")
            size = download_audio(ep["audio_url"], tmp_mp3)
            audio_for_whisper = compress_audio_if_needed(tmp_mp3, size)

            transcript = transcribe(audio_for_whisper)

            # Slug provisoire basé sur le titre de l'épisode (sert à l'URL canonique)
            slug = slugify(ep["title"])
            html_out = generate_article_html(transcript, ep, slug)

            out_path = os.path.join(OUTPUT_DIR, f"{slug}.html")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html_out)
            log(f"✓ Article créé : {out_path}")

            reg["processed"][ep["guid"]] = {
                "title": ep["title"],
                "slug": slug,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            created += 1
        except Exception as ex:
            log(f"✗ Échec sur '{ep['title']}' : {ex}")
        finally:
            for p in [locals().get("tmp_mp3"), locals().get("audio_for_whisper")]:
                if p and os.path.exists(p) and p.startswith("/tmp"):
                    try: os.remove(p)
                    except Exception: pass

    save_registry(reg)
    log(f"Terminé. {created} article(s) créé(s).")


if __name__ == "__main__":
    main()

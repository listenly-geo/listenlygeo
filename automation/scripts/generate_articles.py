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
# 4. Génération de l'article GEO via Claude
# ----------------------------------------------------------------------------
ARTICLE_PROMPT = """Tu es un rédacteur expert en GEO (Generative Engine Optimization) : tu écris des articles de blog optimisés pour être cités par les IA (ChatGPT, Perplexity, Gemini).

À partir de la TRANSCRIPTION d'un épisode de podcast ci-dessous, rédige un ARTICLE DE BLOG complet et un bloc FAQ, en français.

RÈGLES GEO ABSOLUES :
- Titre = une question ou formulation que de vraies personnes recherchent (pas le titre de l'épisode tel quel).
- Commence par une RÉPONSE DIRECTE de 2-3 phrases (l'IA doit pouvoir l'extraire).
- Structure en sections avec sous-titres <h2> clairs, chacun traitant un sujet de l'épisode.
- Cite nommément l'invité, son entreprise, les concepts (les entités nommées renforcent l'autorité).
- N'invente JAMAIS de statistique. Si tu cites un chiffre, il doit venir de la transcription.
- Termine par une FAQ de 4 questions/réponses basées sur le contenu réel.
- Reste fidèle à la transcription : pas d'extrapolation hasardeuse.

CONTEXTE :
- Podcast : {blog_name}
- Entreprise : {company}
- Titre original de l'épisode : {ep_title}
- Description de l'épisode : {ep_desc}

TRANSCRIPTION :
\"\"\"
{transcript}
\"\"\"

Réponds UNIQUEMENT avec un JSON valide (aucun texte autour), de la forme :
{{
  "titre": "le titre de l'article (question/recherche réelle, 50-65 caractères)",
  "meta_description": "meta description 140-155 caractères",
  "reponse_directe": "la réponse directe d'intro, 2-3 phrases",
  "sections": [
    {{"sous_titre": "...", "contenu": "paragraphe(s) en texte, peut contenir <strong> et <em>"}}
  ],
  "points_cles": ["point clé 1", "point clé 2", "point clé 3"],
  "faq": [
    {{"question": "...", "reponse": "..."}}
  ],
  "invite": "nom de l'invité si identifiable, sinon vide",
  "tags": ["mot-clé1", "mot-clé2", "mot-clé3"]
}}
"""


def generate_article(transcript, ep):
    log("Génération de l'article GEO via Claude...")
    # On borne la transcription pour rester raisonnable en tokens
    transcript_trimmed = transcript[:24000]
    prompt = ARTICLE_PROMPT.format(
        blog_name=BLOG_NAME,
        company=COMPANY_NAME or "—",
        ep_title=ep["title"],
        ep_desc=re.sub(r"<[^>]+>", " ", ep["description"])[:1500],
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
            "max_tokens": 4000,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=300,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Claude erreur {resp.status_code}: {resp.text[:300]}")
    raw = resp.json()["content"][0]["text"].strip()
    # Nettoyage d'éventuels fences
    raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # tentative d'extraction du premier objet JSON
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            raise RuntimeError("Réponse Claude non parseable en JSON")
        data = json.loads(m.group())
    log(f"Article généré : {data.get('titre','?')}")
    return data


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
            article = generate_article(transcript, ep)
            audio_url = generate_audio(article, ep)  # None pour l'instant (badge "bientôt")

            slug = slugify(article.get("titre") or ep["title"])
            html_out = build_html(article, ep, audio_url, slug)
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

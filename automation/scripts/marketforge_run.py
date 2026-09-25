#!/usr/bin/env python3
"""
Lanceur Marketforge AI Visibility Hub (workflow marketforge-hub.yml).

Réutilise le moteur trafic SANS le modifier : generate_podcast_btb.py et
generate_qa_fiches_btb.py sont chargés comme modules, et seules deux fonctions sont
enveloppées, dans ce process uniquement (les workflows podcast existants ne passent
jamais par ici) :
  - generate_podcast_btb.build_prompt : pour un client sans podcast, la page hub
    décrit l'entreprise et ses contenus au lieu d'un podcast ;
  - generate_qa_fiches_btb.build_question_prompt : pour une question issue d'une
    vidéo, d'un webinar, d'un article, d'un document ou d'une page web, la fiche
    parle de cette source (libellés, bouton, JSON-LD) au lieu d'un épisode de podcast.
Les questions issues d'un podcast passent inchangées.

Commandes :
  hub     crée la page hub d'entreprise si absente (client sans podcast)
          env : PODCAST_SLUG, HUB_NAME, CTA_URL, SOURCES_JSON, LANGUAGE, ANTHROPIC_API_KEY
  fiches  1) transforme les sources non-podcast en transcripts dans l'inbox du moteur
          (vidéo/webinar : yt-dlp + transcription du moteur ; article/site : texte de la
          page ; document : texte du PDF), puis extrait les vraies questions (fonction
          du moteur) ; 2) génère MAX_FICHES fiches via le main() du moteur.
          env : PODCAST_SLUG, SOURCES_JSON, MAX_FICHES, MAX_SOURCES_PER_RUN, LANGUAGE_OVERRIDE,
                RSS_URL, ANTHROPIC_API_KEY, GROQ_API_KEY/OPENAI_API_KEY
"""

import hashlib
import html
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
SLUG = os.environ.get("PODCAST_SLUG", "").strip()
LANG = (os.environ.get("LANGUAGE_OVERRIDE") or os.environ.get("LANGUAGE") or "fr").strip().lower()
SOURCES = json.loads(os.environ.get("SOURCES_JSON") or "[]")
MAX_SOURCES_PER_RUN = int(os.environ.get("MAX_SOURCES_PER_RUN", "2") or "2")
MAX_TEXT_CHARS = 60000
MAX_MEDIA_SECONDS = 5400  # 90 min max par vidéo/webinar (coût de transcription)
INBOX_DIR = f"automation/inbox/moteur-trafic-transcripts/{SLUG}"

KINDS = {
    # kind: (fr: une/la/cette/de la, accord, en, JSON-LD, bouton fr, bouton en)
    "video": ("une vidéo", "la vidéo", "cette vidéo", "de la vidéo", "e", "video", "VideoObject",
              "Voir la vidéo", "Watch the video"),
    "webinar": ("un webinar", "le webinar", "ce webinar", "du webinar", "", "webinar", "VideoObject",
                "Voir le webinar", "Watch the webinar"),
    "article": ("un article", "l'article", "cet article", "de l'article", "", "article", "Article",
                "Lire l'article", "Read the article"),
    "document": ("un document", "le document", "ce document", "du document", "", "document", "DigitalDocument",
                 "Consulter le document", "Open the document"),
    "website": ("une page du site", "la page", "cette page", "de la page", "e", "web page", "WebPage",
                "Voir la page", "View the page"),
}


def log(msg):
    print(f"[marketforge:{SLUG}] {msg}", flush=True)


def load_module(filename, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def source_guid(url):
    return "mf-" + hashlib.sha1(url.strip().encode()).hexdigest()[:16]


# ------------------------------------------------------------------ libellés par source

def question_override(kind, title, source_url):
    a, the, this, of, e, en, schema, btn_fr, btn_en = KINDS[kind]
    if LANG == "en":
        return (
            f"\n\n## SOURCE OF THIS PAGE (overrides every instruction above)\n"
            f"This page does NOT come from a podcast: the source is a {en} titled \"{title}\" ({source_url}). "
            f"Wherever the instructions mention a podcast, an episode, listening or audio, refer to the {en} "
            f"instead — never write \"listen\", \"episode\" or \"podcast\". The visible call-to-action button text "
            f"is \"{btn_en}\". In the JSON-LD, replace the PodcastSeries entity with a {schema} describing this "
            f"{en} (url: {source_url})."
        )
    return (
        f"\n\n## SOURCE DE CETTE FICHE (prioritaire sur toutes les consignes ci-dessus)\n"
        f"Cette fiche n'est PAS tirée d'un podcast : la source est {a} intitulé{e} « {title} » ({source_url}). "
        f"Partout où les consignes parlent de podcast, d'épisode, d'écoute ou d'audio, parle de {the} — "
        f"n'écris jamais « écouter », « épisode » ni « podcast ». Le texte du bouton d'appel à l'action visible "
        f"est « {btn_fr} ». Les libellés « Extrait de l'épisode » deviennent « Extrait {of} », « La réponse se "
        f"trouve dans ce podcast » devient « La réponse se trouve dans {this} ». Dans le JSON-LD, remplace "
        f"l'entité PodcastSeries par un {schema} décrivant {this} (url : {source_url})."
    )


def hub_override(name, cta_url, sources):
    listing = "\n".join(f"- {KINDS.get(s['type'], KINDS['website'])[5]} : {s['value']}" for s in sources) or "- (aucune)"
    return (
        f"\n\n## TYPE DE PAGE (prioritaire sur toutes les consignes ci-dessus)\n"
        f"Cette page n'est PAS la fiche d'un podcast : c'est la page hub des contenus experts de l'entreprise "
        f"« {name} » (site : {cta_url}). Ses contenus sources sont :\n{listing}\n"
        f"Partout où les consignes parlent de podcast, d'épisodes, d'animateur ou d'écoute, parle de l'entreprise, "
        f"de ses contenus et de son expertise. N'invente aucun épisode, aucun invité ni aucune plateforme d'écoute. "
        f"Dans le JSON-LD, remplace PodcastSeries par une Organization (name « {name} », url {cta_url}). "
        f"Le bouton d'appel à l'action renvoie vers {cta_url} avec le texte « Découvrir {name} »."
    )


# ------------------------------------------------------------------ extraction du contenu

class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg", "button"}
    BLOCK = {"p", "h1", "h2", "h3", "h4", "li", "blockquote", "td", "div", "section", "article", "br"}

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.parts = []
        self.title = ""
        self._in_title = False
        self.og_title = ""

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            a = dict(attrs)
            if a.get("property") == "og:title" and a.get("content"):
                self.og_title = a["content"]
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.depth:
            self.parts.append(data)


def fetch(url, max_bytes=20_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; MarketforgeBot/1.0)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read(max_bytes), resp.headers.get("Content-Type", "")


def page_text(url):
    raw, ctype = fetch(url)
    if "pdf" in ctype.lower() or url.lower().split("?")[0].endswith(".pdf"):
        return pdf_text(raw, url)
    p = _TextExtractor()
    p.feed(raw.decode("utf-8", errors="replace"))
    lines = [re.sub(r"\s+", " ", l).strip() for l in "".join(p.parts).split("\n")]
    text = "\n".join(l for l in lines if len(l) > 40)  # écarte menus, boutons, mentions courtes
    title = html.unescape((p.og_title or p.title).strip()) or url
    return title, text


def pdf_text(raw, url):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    text = "\n".join((page.extract_text() or "") for page in reader.pages[:80])
    title = ((reader.metadata or {}).get("/Title") or "").strip() or url.rsplit("/", 1)[-1]
    return title, text


def media_transcript(url, emod, tmpdir):
    meta = json.loads(subprocess.run(
        ["yt-dlp", "-J", "--no-playlist", url], check=True, capture_output=True, text=True, timeout=180).stdout)
    title = meta.get("title") or url
    out = os.path.join(tmpdir, "media.%(ext)s")
    cmd = ["yt-dlp", "--no-playlist", "-f", "bestaudio/best", "-x", "--audio-format", "mp3",
           "--audio-quality", "5", "-o", out, url]
    if (meta.get("duration") or 0) > MAX_MEDIA_SECONDS:
        log(f"Média de {int(meta['duration'] // 60)} min : seules les {MAX_MEDIA_SECONDS // 60} premières minutes sont transcrites.")
        cmd[1:1] = ["--download-sections", f"*0-{MAX_MEDIA_SECONDS}"]
    subprocess.run(cmd, check=True, capture_output=True, timeout=1800)
    path = os.path.join(tmpdir, "media.mp3")
    path = emod.compress_audio_if_needed(path, os.path.getsize(path))
    path = emod.speed_up_audio(path)
    transcript, segments = emod.transcribe(path, LANG)
    return title, transcript, segments


def source_note(kind, title):
    a = KINDS[kind][0]
    return (f"[SOURCE : {a} intitulé{KINDS[kind][4]} « {title} » — ce n'est PAS un podcast. "
            f"L'« invité » est la personne qui s'exprime ou l'auteur, s'il est nommé ; sinon laisse l'invité vide.]\n\n")


def ingest(qamod):
    """Écrit dans l'inbox du moteur les questions réelles de chaque source non traitée."""
    todo = [s for s in SOURCES if s.get("type") in KINDS and s.get("value", "").startswith("http")]
    if not todo:
        return
    registry = qamod.load_registry()
    known = set(registry.get("known_episode_guids", []))
    consumed_dir = os.path.join(INBOX_DIR, "consumed")
    already = set(os.listdir(INBOX_DIR)) | (set(os.listdir(consumed_dir)) if os.path.isdir(consumed_dir) else set()) \
        if os.path.isdir(INBOX_DIR) else set()
    podcast, _ = qamod.load_podcast_record()
    if LANG in ("fr", "en"):
        podcast["language"] = LANG
    emod = qamod.episode_mod()
    os.makedirs(INBOX_DIR, exist_ok=True)

    done = 0
    for src in todo:
        guid = source_guid(src["value"])
        if guid in known or f"{guid}.json" in already:
            continue
        if done >= MAX_SOURCES_PER_RUN:
            log("Limite de sources par run atteinte — les suivantes passeront au prochain run.")
            break
        done += 1
        kind = src["type"]
        log(f"Source {kind} : {src['value']}")
        tmpdir = tempfile.mkdtemp(prefix="mf_src_")
        payload = {"episode_guid": guid, "source_kind": kind, "source_url": src["value"], "real_qa": []}
        try:
            if kind in ("video", "webinar"):
                title, text, segments = media_transcript(src["value"], emod, tmpdir)
            else:
                title, text = page_text(src["value"])
                segments = None
            text = (text or "").strip()[:MAX_TEXT_CHARS]
            payload["episode_title"] = title
            if len(text) < 800:
                log(f"Contenu trop court ou illisible ({len(text)} caractères) — source ignorée.")
            else:
                ep = {"guid": guid, "title": title, "pubdate": "", "audio_url": ""}
                guest, qa, quote, stats, entities = emod.extract_real_qa(source_note(kind, title) + text, ep, podcast, segments)
                published = [p.get("question", "") for p in registry.get("published", [])]
                qa = qamod.filter_quality_qa(qa, published, podcast)
                for q in qa:
                    q["source_kind"] = kind
                    q["source_url"] = src["value"]
                    q["source_title"] = title
                payload.update(real_qa=qa, guest=guest, real_quote=quote, key_stats=stats,
                               entities=entities, transcript_full=text)
                log(f"{len(qa)} question(s) retenue(s) : {title}")
        except Exception as e:  # une source en échec n'arrête ni les autres ni les fiches
            log(f"ÉCHEC source ({type(e).__name__}: {str(e)[:300]}) — marquée traitée pour ne pas la repayer.")
            payload.setdefault("episode_title", src["value"])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        with open(os.path.join(INBOX_DIR, f"{guid}.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------ commandes

def cmd_hub():
    name = os.environ.get("HUB_NAME", "").strip() or SLUG
    cta = os.environ.get("CTA_URL", "").strip()
    if os.path.exists(f"pages/podcast-btb/{SLUG}-podcast.html"):
        log("Page hub déjà présente.")
        return
    try:
        _, about = page_text(cta)
    except Exception as e:
        log(f"Site injoignable ({e}) — description minimale.")
        about = ""
    os.environ["PODCAST_RAW_INFO"] = (
        f"Nom du podcast : {name}\n\nType : page hub des contenus experts de l'entreprise {name} (ce n'est pas un podcast)\n"
        f"Site : {cta}\n\nPrésentation (texte réel du site) :\n{about[:6000]}"
    )
    os.environ.setdefault("PODCAST_URL", cta)
    os.environ.setdefault("LISTENLY_URL", cta)
    os.environ.pop("RSS_URL", None)
    n1 = load_module("generate_podcast_btb.py", "generate_podcast_btb")
    original = n1.build_prompt

    def build_prompt(*args, **kwargs):
        return original(*args, **kwargs) + hub_override(name, cta, SOURCES)

    n1.build_prompt = build_prompt
    n1.main()


def cmd_fiches():
    qamod = load_module("generate_qa_fiches_btb.py", "generate_qa_fiches_btb")
    original = qamod.build_question_prompt

    def build_question_prompt(podcast, question, *args, **kwargs):
        static_prompt, dynamic_prompt = original(podcast, question, *args, **kwargs)
        kind = question.get("source_kind")
        if kind in KINDS:
            dynamic_prompt += question_override(kind, question.get("source_title", ""), question.get("source_url", ""))
        return static_prompt, dynamic_prompt

    qamod.build_question_prompt = build_question_prompt

    try:
        ingest(qamod)
    except Exception as e:
        log(f"ÉCHEC ingestion ({e}) — on continue avec les fiches déjà en stock.")

    n = max(1, min(5, int(re.sub(r"\D", "", os.environ.get("MAX_FICHES", "3")) or 3)))
    for i in range(n):
        log(f"--- fiche {i + 1}/{n} ---")
        try:
            qamod.main()
        except SystemExit as e:
            if e.code not in (0, None):
                log(f"Arrêt du moteur (code {e.code}).")
                break


if __name__ == "__main__":
    {"hub": cmd_hub, "fiches": cmd_fiches}[sys.argv[1]]()

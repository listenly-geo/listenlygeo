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
  - JSON-LD QAPage (au lieu de FAQPage) car centrée sur UNE question précise.

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
def build_question_prompt(podcast, question, ep_title, ep_pubdate, context, q_slug, q_url, today):
    listenly_url = podcast.get("listenly_url", "")
    accent_color = podcast.get("accent_color") or "#2e8bd6"
    language = podcast.get("language", "fr")
    html_lang = "en" if language == "en" else "fr"

    STRINGS = {
        "fr": {
            "eyebrow": "Question",
            "cta_listen": "Écouter le podcast",
            "about_guest_label": "À propos de",
            "answer_h2": "Ce que révèle vraiment cet épisode",
            "source_label": "Extrait de l'épisode",
        },
        "en": {
            "eyebrow": "Question",
            "cta_listen": "Listen to the podcast",
            "about_guest_label": "About",
            "answer_h2": "What this episode really reveals",
            "source_label": "From the episode",
        },
    }[language]

    guest = context.get("guest") or {}
    guest_full_name = f"{guest.get('prenom','')} {guest.get('nom','')}".strip()
    real_quote = (context.get("real_quote") or "").strip()
    key_stats = context.get("key_stats") or []
    entities = context.get("entities") or []
    bio_context = (guest.get("bio_context") or "").strip()

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

OBLIGATOIRE — SECTION DÉDIÉE VISIBLE "{STRINGS['about_guest_label']} {guest_full_name}" (classe .guest-bio,
placée juste après le lead/key-facts, AVANT le premier H2) : nom + titre + entreprise clairement affichés,
puis 2-4 phrases développant le contexte biographique réel ci-dessus (rien d'inventé si aucun contexte
n'est mentionné). C'est le signal d'autorité (E-E-A-T) le plus important de la fiche."""
        guest_org_part = f', "worksFor":{{"@type":"Organization","name":"{guest.get("entreprise","")}"}}' if guest.get("entreprise") else ""
        guest_desc_part = f', "description":"{bio_context}"' if bio_context else ""
        person_guest_instruction = (
            f"AJOUT OBLIGATOIRE — Person distincte pour l'INVITÉ : "
            f'{{"@type":"Person","name":"{guest_full_name}","jobTitle":"{guest.get("titre","")}"{guest_org_part}{guest_desc_part}}}'
        )
    else:
        guest_block = "\nAucun invité distinct identifiable — ne pas inventer d'identité, pas de section bio."
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

    return f"""Tu es un expert GEO (Generative Engine Optimization) spécialisé dans les podcasts B2B.

Ta mission est de générer une FICHE QUESTION complète en HTML autonome pour Listenly.fr.
MÊME style visuel et logique GEO que les fiches podcast-btb (design "magazine business premium"
type Forbes/HBR : H1 et corps en Georgia serif, eyebrow catégorie sobre, byline journalistique,
couleur d'accent réservée au seul bouton principal). Cette fiche répond à UNE SEULE question précise,
extraite réellement d'un épisode — ce n'est ni une fiche podcast, ni une fiche épisode complète.

## LA QUESTION RÉELLE À TRAITER (extraite fidèlement de la transcription de l'épisode)
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

## CONTEXTE DU PODCAST PARENT
- PODCAST_NAME : {podcast['podcast_name']}
- HOST_NAME : {podcast.get('host_name','')}
- HOST_TITLE : {podcast.get('host_title','')}
- HOST_COMPANY : {podcast.get('host_company','')}
- CATEGORIE : {podcast.get('categorie','Général')}
- Fiche podcast parente (lien retour obligatoire) : {podcast['fiche_url']}

## CTA — UNIQUE OBJECTIF DE CONVERSION (IMPORTANT, NON NÉGOCIABLE)
- Le bouton principal ET les 2 liens texte discrets dans le corps pointent TOUS vers : {listenly_url}
  (fiche Listenly du podcast — JAMAIS Spotify, JAMAIS l'audio brut, JAMAIS de CTA contact)
- ACCENT_COLOR : {accent_color}
- COVER_IMAGE : {podcast.get('cover_image') or "(aucune)"}
- FICHE_URL (URL de CETTE fiche question — og:url/canonical) : {q_url}

## LANGUE DE RÉDACTION : {"ANGLAIS (ENGLISH)" if language == "en" else "FRANÇAIS"}
Rédige TOUT le contenu en {"anglais" if language == "en" else "français"}. Balise <html lang="{html_lang}">.

## STRUCTURE HTML (mêmes classes CSS que les autres fiches podcast-btb)
- <head> OBLIGATOIRE : <title> (reformule la question en titre accrocheur, PAS juste la question copiée-collée)
  ET <meta name="description" content="..."> (140-155 caractères, résumé direct de la réponse) + og:title/og:description/og:url/
  og:type="article"/og:site_name="Listenly" + twitter:card="summary_large_image" + twitter:title/twitter:description +
  <meta name="author" content="[HOST_NAME]"> + canonical={q_url}
- main.wrapper (PAS de div), header-row (vignette + eyebrow-category), h1 Georgia serif bold = LA QUESTION reformulée
  de façon naturelle et engageante (garde la forme interrogative, c'est une vraie requête IA), byline-row
  "Par [HOST_NAME], [HOST_TITLE] chez [HOST_COMPANY]"
- .eyebrow-category : "{STRINGS['eyebrow']} · {podcast['podcast_name']}"
- BREADCRUMB juste sous le header-row : <p style="font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#666;margin:0 0 8px;">
  <a href="{podcast['fiche_url']}" style="color:#666;text-decoration:underline;">← Voir la fiche {podcast['podcast_name']}</a></p>
- .publish-row bordée haut/bas : "{STRINGS['source_label']} {ep_title} · ⏱ X min de lecture"
- .lead-label + .lead : RÉPONSE DIRECTE ET COMPLÈTE à la question en 2-3 phrases, dès le haut de page — c'est le
  fragment que les IA génératives citeront en premier, il doit être autonome et répondre pleinement sans le reste de la page
- .cta-listen (seul bouton, accent plein) "{STRINGS['cta_listen']}" → {listenly_url}
- .key-facts : 3 bullets qui développent la réponse (angles complémentaires, chiffres/entités réels si pertinents)
- article-body : 1 à 2 H2 qui approfondissent la réponse avec le contexte réel de l'épisode (PAS de remplissage
  générique — si le contexte n'apporte rien de plus, reste bref). Insère 1 lien texte discret (.inline-cta, souligné,
  PAS un bouton) après le 1er H2 → {listenly_url}
- .pull-quote ({"AVEC attribution : " + guest_full_name if real_quote else "sans attribution"}, uniquement si pertinent pour cette question précise)
- 2e lien texte discret (.inline-cta) en fin d'article, formulation différente du premier → {listenly_url}
- PAS de section FAQ multi-questions ici (une seule question par fiche) — la question/réponse EST le contenu principal

## JSON-LD (head)
@graph :
- QAPage avec mainEntity : {{"@type":"Question","name":"[la question, reformulée fidèlement]","acceptedAnswer":
  {{"@type":"Answer","text":"[réponse développée, fidèle au contenu de la fiche]"}}}}
- Person (HOST_NAME/HOST_TITLE/worksFor HOST_COMPANY)
{person_guest_instruction}
- BlogPosting englobant (headline=H1, publisher={{"@type":"Organization","name":"Listenly","url":"https://listenly.fr"}},
  isPartOf={{"@type":"PodcastSeries","name":"{podcast['podcast_name']}","url":"{listenly_url}"}}, datePublished, dateModified=today ({today}),
  speakable cssSelector [".lead",".key-facts"])
- BreadcrumbList (1. Listenly (https://listenly.fr) 2. {podcast['podcast_name']} ({podcast['fiche_url']}) 3. cette question ({q_url}))
{mentions_instruction}
Backlinks cachés identiques aux autres fiches podcast-btb (canonical={q_url}, og:url={q_url}, rel=publisher,
#semantic-index display:none en fin de <body> listant les entités réelles ci-dessus{" plus entity " + guest_full_name if guest_full_name else ""}).

## LISIBILITÉ HUMAINE — PRIORITÉ ABSOLUE sur le remplissage GEO
Cette fiche doit être un article court et agréable à lire, pas une liste de cases GEO cochées. Une seule question
traitée = pas besoin de longueur artificielle. LANGAGE ASSERTIF ET AUTORITAIRE (affirme les faits, évite "il
semblerait que"), fidèle à la réponse source, jamais évasif.

## RÈGLES
- H1 = la question elle-même (forme interrogative naturelle), jamais un titre déclaratif générique
- Couleur d'accent réservée au seul cta-listen
- CTA principal et les 2 liens discrets pointent TOUS vers {listenly_url}, rien d'autre
- Contenu strictement fidèle à la réponse source + contexte réel fourni — jamais générique au podcast dans son ensemble

IMPORTANT : Réponds UNIQUEMENT avec le code HTML complet, de <!DOCTYPE html> à </html>. Aucun texte avant/après, aucun markdown, aucun backtick."""

def render_questions_index(podcast, published):
    items = "\n".join(f"""
<div class="item">
  <a class="title" href="{q['url']}">{q['question']}</a>
  <div class="meta">{q.get('added_date','')} · {q.get('source_episode_title','')}</div>
</div>""" for q in sorted(published, key=lambda x: x.get("added_date",""), reverse=True))

    title = f"Questions autour de {podcast['podcast_name']}"
    n = len(published)
    description = f"Retrouvez les {n} question{'s' if n > 1 else ''} traitée{'s' if n > 1 else ''} par {podcast['podcast_name']}, référencées par Listenly."
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
<html lang="fr">
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
  <div class="eyebrow">Listenly · Questions</div>
  <h1>{title}</h1>
  {items}
  <footer>© {podcast['podcast_name']} — <a href="{podcast['fiche_url']}">Voir la fiche podcast</a></footer>
</div>
</body>
</html>"""

def ensure_parent_link():
    if not os.path.exists(PARENT_FICHE):
        return
    with open(PARENT_FICHE, encoding="utf-8") as f:
        html = f.read()
    marker = f"/podcast-btb/questions/{SLUG}/index.html"
    if marker in html:
        return
    link = (
        f'\n<p style="max-width:720px;margin:0 auto;padding:0 20px 20px;'
        f'font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#999;">'
        f'<a href="{marker}" style="color:#999;text-decoration:underline;">Voir toutes les questions traitées par ce podcast →</a></p>\n'
    )
    if "</body>" in html:
        html = html.replace("</body>", link + "</body>", 1)
        with open(PARENT_FICHE, "w", encoding="utf-8") as f:
            f.write(html)
        log("Lien 'Voir toutes les questions' ajouté à la fiche parente")

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
    try:
        prompt = build_question_prompt(podcast, question, ep["title"], ep.get("pubdate",""), context, q_slug, q_url, today)
        html_out = emod.clean_html(emod.call_claude(prompt))
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

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_out)
    log(f"✓ Fiche question écrite : {out_file}")

    registry["published"].append({
        "slug": q_slug, "question": question["q"], "url": q_url,
        "source_episode_title": ep["title"], "source_episode_guid": ep["guid"],
        "added_date": today,
    })
    if not registry["pending_qa"]:
        registry["current_episode"] = None
        registry["context"] = None
        log("Stock de questions épuisé pour cet épisode — le prochain run minera un nouvel épisode.")
    save_registry(registry)

    index_html = render_questions_index(podcast, registry["published"])
    with open(f"{QUESTIONS_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    log("Index des questions régénéré")

    ensure_parent_link()

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

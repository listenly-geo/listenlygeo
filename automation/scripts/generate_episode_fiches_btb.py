#!/usr/bin/env python3
"""
Moteur N2 podcast-btb : génère une fiche par ÉPISODE à partir du flux RSS
d'un podcast déjà référencé via generate_podcast_btb.py (Moteur N1).

Ne régénère jamais un épisode déjà traité (registre par podcast).

Variables requises :
  ANTHROPIC_API_KEY
  PODCAST_SLUG        — slug du podcast déjà présent dans podcasts.json
Optionnelles (sinon lues depuis pages/podcast-btb/data/podcasts.json) :
  RSS_URL
  PODCAST_URL, CONTACT_URL, LISTENLY_URL, COVER_IMAGE, ACCENT_COLOR
  MAX_EPISODES        — nombre max de nouveaux épisodes traités par run (défaut 3)
  USE_TRANSCRIPT      — "true" pour activer le TEST d'extraction audio reelle (Whisper +
                        Claude) sur ce podcast au lieu de generer depuis titre/description
                        seuls. Necessite OPENAI_API_KEY + ffmpeg installe sur le runner.
                        Fallback automatique et silencieux vers le mode habituel si
                        l'audio/la transcription echoue pour une raison quelconque.
  OPENAI_API_KEY      — requis uniquement si USE_TRANSCRIPT=true
"""

import os, sys, re, json, datetime, unicodedata, subprocess, tempfile
import urllib.request, urllib.error
import xml.etree.ElementTree as ET
import importlib.util

def _load_gen_module():
    spec = importlib.util.spec_from_file_location(
        "gen_podcast_btb", os.path.join(os.path.dirname(__file__), "generate_podcast_btb.py")
    )
    mod = importlib.util.module_from_spec(spec)
    os.environ.setdefault("ANTHROPIC_API_KEY", "unused")
    os.environ.setdefault("PODCAST_RAW_INFO", "unused")
    os.environ.setdefault("PODCAST_URL", "unused")
    os.environ.setdefault("CONTACT_URL", "unused")
    os.environ.setdefault("LISTENLY_URL", "unused")
    spec.loader.exec_module(mod)
    return mod

API_KEY = os.environ["ANTHROPIC_API_KEY"]
SLUG    = os.environ["PODCAST_SLUG"].strip()
MAX_EPISODES = int(os.environ.get("MAX_EPISODES", "3") or "3")

# --- Test transcript audio reel (Moteur 3) : desactive par defaut, opt-in par podcast ---
USE_TRANSCRIPT = os.environ.get("USE_TRANSCRIPT", "false").strip().lower() == "true"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
WHISPER_MODEL = "whisper-1"
WHISPER_MAX_BYTES = 24 * 1024 * 1024

MODEL       = "claude-sonnet-4-6"
PAGES_DIR   = "pages/podcast-btb"
DATA_FILE   = f"{PAGES_DIR}/data/podcasts.json"
EPISODES_DIR = f"{PAGES_DIR}/episodes/{SLUG}"
REGISTRY_FILE = f"{EPISODES_DIR}/_generated.json"
PARENT_FICHE = f"{PAGES_DIR}/{SLUG}-podcast.html"
NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}

def log(msg): print(f"[episode-btb:{SLUG}] {msg}", flush=True)

def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"^-+|-+$", "", s)[:70]

def clean_text(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&amp;", "&").replace("&nbsp;", " ")
          .replace("&#39;", "'").replace("&rsquo;", "'").replace("&quot;", '"'))
    return re.sub(r"\s+", " ", s).strip()

# --- Bloc test transcript reel (repris du Moteur 3 / MarketForge GEO) ---
def download_audio(url, dest):
    log("Téléchargement audio...")
    req = urllib.request.Request(url, headers={"User-Agent": "ListenlyGEO/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
    size = os.path.getsize(dest)
    log(f"Audio : {size/1024/1024:.1f} Mo")
    return size

def compress_audio_if_needed(src, size):
    if size <= WHISPER_MAX_BYTES:
        return src
    log("Compression ffmpeg (fichier > 24 Mo)...")
    out = src.rsplit(".", 1)[0] + "_compressed.mp3"
    subprocess.run(["ffmpeg", "-y", "-i", src, "-ac", "1", "-ar", "16000", "-b:a", "32k", out],
                   check=True, capture_output=True)
    return out

def transcribe(audio_path):
    log("Transcription Whisper...")
    boundary = "----ListenlyGEOBoundary"
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()
    filename = os.path.basename(audio_path)
    body = bytearray()
    def add_field(name, value):
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8"))
    add_field("model", WHISPER_MODEL)
    add_field("language", "fr")
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: audio/mpeg\r\n\r\n".encode("utf-8"))
    body.extend(audio_bytes)
    body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=bytes(body),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3300) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Whisper erreur {e.code}: {e.read()[:300]}")
    text = result.get("text", "").strip()
    log(f"Transcription : {len(text)} chars")
    return text

EXTRACT_REAL_QA_PROMPT = """Tu es un expert GEO (Generative Engine Optimization) pour podcasts B2B. Les moteurs IA (Perplexity, ChatGPT, Google AI Overviews) fonctionnent par récupération de fragments : ils retiennent en priorité les passages contenant des CITATIONS VERBATIM ATTRIBUÉES, des STATISTIQUES/CHIFFRES PRÉCIS, et des ENTITÉS NOMMÉES réelles — bien plus qu'un texte généraliste. Ton objectif est d'extraire ce matériel réel pour maximiser la citabilité, sans jamais inventer.

À partir de la transcription réelle ci-dessous, extrais :

1. INVITÉ réel de cet épisode (la personne interrogée, PAS l'animateur) : prénom, nom, titre/poste, entreprise, tels que mentionnés. Si non identifiable clairement, renvoie des champs vides — n'invente JAMAIS.

2. TOUTES les vraies questions distinctes et solides abordées, avec leurs vraies réponses. Pas de plafond fixe. N'invente JAMAIS de question pour atteindre un quota.
   CRITÈRE : question réellement posée/implicite, réponse claire et autonome basée uniquement sur ce qui a été dit, chaque question couvre un angle DISTINCT, reformulée comme une vraie requête IA.

3. UNE citation verbatim forte (15-30 mots, mot pour mot ou très proche) dite RÉELLEMENT par l'invité — la phrase la plus dense/marquante de la conversation, adaptée à être attribuée nommément (elle sera affichée avec le nom de l'invité). Si aucune phrase assez forte et citable n'existe, renvoie une chaîne vide plutôt que d'en fabriquer une.

4. 3 à 6 STATISTIQUES/CHIFFRES/DATES PRÉCIS réellement mentionnés dans la conversation (montants, pourcentages, dates d'échéance, durées, seuils légaux...) — pas des généralités, des chiffres exacts tels que dits. Formule chaque statistique avec son CONTEXTE/SOURCE quand il est mentionné (ex: "loi de finances 2026 : amendes doublées" plutôt que juste "amendes doublées") — un chiffre daté et sourcé est plus citable par une IA qu'un chiffre isolé.

5. 5 à 10 ENTITÉS NOMMÉES réelles mentionnées dans la conversation (lois, dispositifs, entreprises, outils, organismes, lieux) — les vrais noms propres cités, pas des concepts génériques.

Podcast : {podcast_name} | Épisode : {ep_title}

TRANSCRIPTION :
\"\"\"{transcript}\"\"\"

Réponds UNIQUEMENT avec un JSON, sans markdown, sans backtick :
{{
  "guest": {{"prenom": "...", "nom": "...", "titre": "...", "entreprise": "..."}},
  "qa": [
    {{"q": "Question reelle reformulee comme requete IA", "r": "Reponse 2-3 phrases tiree fidelement de la transcription"}},
    {{"q": "...", "r": "..."}}
  ],
  "real_quote": "citation verbatim ou chaine vide",
  "key_stats": ["chiffre/date/seuil precis 1", "..."],
  "entities": ["entite nommee reelle 1", "..."]
}}"""

def extract_real_qa(transcript, ep, podcast):
    log("Extraction identite invite + vraies questions/reponses + citation + stats + entites depuis le transcript...")
    prompt = EXTRACT_REAL_QA_PROMPT.format(
        podcast_name=podcast["podcast_name"],
        ep_title=ep["title"],
        transcript=transcript[:28000],
    )
    raw = call_claude(prompt)
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    idx = raw.find("{")
    if idx > 0:
        raw = raw[idx:]
    data = json.loads(raw)
    guest = data.get("guest", {}) or {}
    qa = data.get("qa", []) or []
    real_quote = (data.get("real_quote") or "").strip()
    key_stats = data.get("key_stats", []) or []
    entities = data.get("entities", []) or []
    log(f"Invite detecte : {guest.get('prenom','')} {guest.get('nom','')} ({guest.get('titre','') or 'titre inconnu'}, {guest.get('entreprise','') or 'entreprise inconnue'})".strip())
    log(f"{len(qa)} question(s) reelle(s) extraite(s)")
    for i, item in enumerate(qa):
        log(f"  Q{i+1}: {item['q'][:70]}")
    log(f"Citation reelle extraite : {'oui' if real_quote else 'non trouvee'}")
    log(f"{len(key_stats)} statistique(s)/chiffre(s) reel(s), {len(entities)} entite(s) nommee(s) reelle(s)")
    return guest, qa, real_quote, key_stats, entities

def get_real_transcript_material(ep, podcast):
    """Tente le pipeline audio->transcript->Q/R reelles + identite invite + citation + stats + entites.
    Retourne None si echec (fallback silencieux vers la generation habituelle basee sur titre/description)."""
    if not ep.get("audio_url"):
        log("AVERTISSEMENT transcript : pas d'URL audio dans le flux RSS pour cet episode — fallback.")
        return None
    if not OPENAI_API_KEY:
        log("AVERTISSEMENT transcript : OPENAI_API_KEY absente — fallback.")
        return None
    tmpdir = tempfile.mkdtemp(prefix="ep_audio_")
    try:
        audio_path = os.path.join(tmpdir, "episode.mp3")
        size = download_audio(ep["audio_url"], audio_path)
        audio_path = compress_audio_if_needed(audio_path, size)
        transcript = transcribe(audio_path)
        if not transcript:
            log("AVERTISSEMENT transcript : transcription vide — fallback.")
            return None
        guest, real_qa, real_quote, key_stats, entities = extract_real_qa(transcript, ep, podcast)
        return {
            "transcript_excerpt": transcript[:4000],
            "real_qa": real_qa,
            "guest": guest,
            "real_quote": real_quote,
            "key_stats": key_stats,
            "entities": entities,
        }
    except Exception as e:
        log(f"AVERTISSEMENT transcript : echec pipeline ({e}) — fallback generation habituelle.")
        return None
    finally:
        try:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

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
    """Comble les champs manquants (anciennes fiches générées avant l'enrichissement)
    en les extrayant directement du HTML déjà publié."""
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
    if not record.get("contact_url"):
        m = re.search(r'class="cta-contact"[^>]*href="([^"]+)"', html)
        if m: record["contact_url"] = m.group(1)
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

def fetch_rss(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

def parse_episodes(xml_bytes):
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("Flux RSS invalide : pas de <channel>")
    episodes = []
    for item in channel.findall("item"):
        title_el = item.find("title")
        title = clean_text(title_el.text) if title_el is not None and title_el.text else ""
        if not title:
            continue
        guid_el = item.find("guid")
        link_el = item.find("link")
        guid = (guid_el.text.strip() if guid_el is not None and guid_el.text
                else (link_el.text.strip() if link_el is not None and link_el.text else title))
        desc_el = item.find("description")
        if desc_el is None:
            desc_el = item.find("itunes:summary", NS)
        description = clean_text(desc_el.text) if desc_el is not None and desc_el.text else ""
        pubdate_el = item.find("pubDate")
        pubdate = pubdate_el.text.strip() if pubdate_el is not None and pubdate_el.text else ""
        enclosure = item.find("enclosure")
        audio_url = enclosure.attrib.get("url", "") if enclosure is not None else ""
        episodes.append({
            "guid": guid, "title": title, "description": description,
            "pubdate": pubdate, "audio_url": audio_url,
            "link": link_el.text.strip() if link_el is not None and link_el.text else "",
        })
    return episodes

def load_registry():
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_registry(reg):
    os.makedirs(EPISODES_DIR, exist_ok=True)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)

def build_episode_prompt(podcast, ep, ep_slug, ep_url, today, real_material=None):
    listenly_url = podcast.get("listenly_url", "")
    podcast_url = podcast.get("podcast_url", "")
    cta_target = podcast.get("episode_cta_target", "listenly")
    cta_url = listenly_url if cta_target == "listenly" else podcast_url
    accent_color = podcast.get("accent_color") or "#2e8bd6"

    if real_material:
        real_qa_json = json.dumps(real_material["real_qa"], ensure_ascii=False, indent=2)
        guest = real_material.get("guest") or {}
        guest_full_name = f"{guest.get('prenom','')} {guest.get('nom','')}".strip()
        real_quote = (real_material.get("real_quote") or "").strip()
        key_stats = real_material.get("key_stats") or []
        entities = real_material.get("entities") or []

        if guest_full_name:
            guest_block = f"""
IDENTITÉ RÉELLE DE L'INVITÉ (extraite de la transcription — utilise-la telle quelle, n'invente RIEN de plus) :
- Nom : {guest_full_name}
- Titre/poste : {guest.get('titre') or '(non precise dans la transcription — ne pas inventer)'}
- Entreprise : {guest.get('entreprise') or '(non precisee dans la transcription — ne pas inventer)'}

OBLIGATOIRE : ajoute un court paragraphe d'introduction (2-3 phrases) présentant qui est {guest_full_name}
avant la première citation ou mention de ses propos — un lecteur qui ne connaît pas cette personne doit
comprendre son autorité/légitimité sur le sujet avant de lire ses propos. N'invente aucun détail biographique
au-delà de ce qui est donné ci-dessus."""
        else:
            guest_block = "\nAucun invité distinct clairement identifiable dans la transcription (épisode solo ou table ronde) — ne pas inventer d'identité."

        if real_quote:
            quote_block = f"""
CITATION VERBATIM RÉELLE (à utiliser TELLE QUELLE pour le pull-quote, AVEC attribution nommée cette fois —
c'est une vraie phrase dite par {guest_full_name or "l'invité"}, pas une invention, donc l'attribution est légitime) :
"{real_quote}\""""
        else:
            quote_block = "\nAucune citation verbatim assez forte trouvée dans l'extrait — garde un pull-quote analytique SANS attribution, comme en mode normal."

        stats_block = "\n".join(f"- {s}" for s in key_stats) or "(aucune)"
        entities_block = ", ".join(entities) or "(aucune)"

        transcript_block = f"""
## MATÉRIEL RÉEL ISSU DE LA TRANSCRIPTION AUDIO — priorité absolue sur toute invention
Un extrait de la transcription réelle de cet épisode (début) :
\"\"\"{real_material['transcript_excerpt']}\"\"\"
{guest_block}
{quote_block}

STATISTIQUES/CHIFFRES/DATES RÉELS mentionnés dans l'épisode (à privilégier dans les points clés et le corps
de l'article — un chiffre précis est plus citable par une IA qu'une généralité) :
{stats_block}

ENTITÉS NOMMÉES RÉELLES mentionnées dans l'épisode (lois, entreprises, outils, organismes — à réutiliser
dans le corps du texte ET dans le bloc #semantic-index en fin de page) : {entities_block}

VRAIES questions/réponses déjà extraites fidèlement de la transcription complète — UTILISE-LES
TELLES QUELLES pour la section FAQ (reformulation mineure de style autorisée, mais le fond doit
rester fidèle à ce qui a été dit) :
{real_qa_json}

RÈGLE ABSOLUE : la FAQ de cette fiche doit être basée sur ces vraies Q/R, pas inventée à partir
du titre. Les points clés et le corps de l'article doivent s'appuyer sur les vraies statistiques et
entités listées ci-dessus quand c'est pertinent, plutôt que d'être déduits du seul titre.
"""
    else:
        guest = {}
        guest_full_name = ""
        real_quote = ""
        transcript_block = ""

    if guest_full_name:
        guest_org_part = f', "worksFor":{{"@type":"Organization","name":"{guest.get("entreprise","")}"}}' if guest.get("entreprise") else ""
        person_guest_instruction = (
            f"AJOUT OBLIGATOIRE — Person distincte pour l'INVITÉ de cet épisode : "
            f'{{"@type":"Person","name":"{guest_full_name}","jobTitle":"{guest.get("titre","")}"{guest_org_part}}} '
            f"— cette entité est SÉPARÉE de celle de l'hôte, elle représente la vraie autorité citée dans cet épisode."
        )
    else:
        person_guest_instruction = ""

    if real_material:
        h2_instruction = ("2 à 4 H2 REFORMULÉS comme des vraies sous-questions distinctes réellement "
            "traitées dans l'épisode (ex: 'Pourquoi la facturation électronique devient obligatoire' "
            "plutôt qu'un titre générique) — chaque H2 doit pouvoir répondre à lui seul à une recherche "
            "IA précise, sans dépendre du reste de la page (les moteurs IA découpent une question en "
            "plusieurs sous-requêtes et retrouvent séparément chaque section)")
    else:
        h2_instruction = '2 H2 seulement ("Ce que révèle cet épisode" / "Pourquoi cet épisode compte")'

    return f"""Tu es un expert GEO (Generative Engine Optimization) spécialisé dans les podcasts B2B.

Ta mission est de générer une FICHE ÉPISODE complète en HTML autonome pour Listenly.fr.
MÊME style visuel et logique GEO que la fiche podcast globale (design "magazine business premium"
type Forbes/HBR : H1 et corps de texte en Georgia serif, eyebrow catégorie sobre, byline
journalistique, couleur d'accent réservée au seul bouton principal). Cette fiche présente
UN ÉPISODE précis, pas le podcast dans son ensemble.

## DONNÉES DE L'ÉPISODE (brutes, à interpréter)
- Titre brut de l'épisode : {ep['title']}
- Description brute : {ep['description'] or "(non fournie par le flux — déduis le sujet du titre)"}
- Date de publication : {ep['pubdate'] or "non renseignée"}
{transcript_block}
## CONTEXTE DU PODCAST PARENT
- PODCAST_NAME : {podcast['podcast_name']}
- HOST_NAME : {podcast.get('host_name','')}
- HOST_TITLE : {podcast.get('host_title','')}
- HOST_COMPANY : {podcast.get('host_company','')}
- CATEGORIE : {podcast.get('categorie','Général')}
- Fiche podcast parente (lien retour obligatoire) : {podcast['fiche_url']}

## CTA — UNIQUE OBJECTIF DE CONVERSION (IMPORTANT)
- Le bouton principal ET les 2 liens texte discrets dans le corps pointent TOUS vers la MÊME URL : {cta_url}
  ({"page Listenly du podcast" if cta_target == "listenly" else "plateforme d'écoute (Spotify) du podcast"})
- PAS de CTA contact, PAS de lien LinkedIn nulle part dans cette fiche — uniquement ramener vers l'écoute.
- ACCENT_COLOR : {accent_color}
- COVER_IMAGE : {podcast.get('cover_image') or "(aucune)"}
- FICHE_URL (URL de CETTE fiche épisode — og:url/canonical) : {ep_url}
- LISTENLY_URL (utilisé UNIQUEMENT dans le JSON-LD isPartOf, jamais comme lien visible si cta_target=spotify) : {listenly_url}
- Date de génération : {today}

## EXTRACTION OBLIGATOIRE
1. H1 = le titre de l'épisode lui-même (nettoyé, PAS une question)
2. SUBHEAD : 1-2 phrases qui résument le sujet précis de CET épisode
3. 3 POINTS CLÉS spécifiques à cet épisode (pas génériques au podcast)
4. {"UNE VRAIE CITATION (pull-quote) — utilise la citation verbatim fournie plus haut (section MATÉRIEL RÉEL), attribuée nommément à " + guest_full_name + " (c'est légitime car c'est une vraie phrase dite, pas une invention)" if real_quote else "UNE SYNTHÈSE ANALYTIQUE (pull-quote) tirée du sujet de l'épisode, SANS attribution — jamais présentée comme des propos réellement tenus par [HOST_NAME]"}
5. {"TOUTES les vraies questions/réponses fournies plus haut (section MATÉRIEL RÉEL) — n'en oublie aucune, ne les résume pas en 3, la fiche doit toutes les reprendre" if real_material else "3 FAQ précises sur le sujet de CET épisode (vraies requêtes IA, réponses autonomes sans mentionner le podcast)"}

## STRUCTURE HTML — MÊME CSS QUE LA FICHE PODCAST (repris à l'identique, mêmes classes) :
- <head> OBLIGATOIRE : <title> ET <meta name="description" content="..."> (140-155 caractères, résumant le sujet précis de CET épisode, jamais omise) + og:title/og:description/og:url/og:type="article"/og:site_name="Listenly" + <meta name="twitter:card" content="summary_large_image"> + twitter:title (identique à og:title, 50-70 car.) + twitter:description (identique à og:description, 150-200 car.) + <meta name="author" content="[HOST_NAME]"> + <meta name="format-detection" content="telephone=no"> + canonical={ep_url}
- main.wrapper (PAS de div), header-row (vignette + eyebrow-category côte à côte), h1 Georgia serif bold, byline-row "Par [HOST_NAME], [HOST_TITLE] chez [HOST_COMPANY]"
- .eyebrow-category : "Épisode · {podcast['podcast_name']}"
- BREADCRUMB juste sous le header-row : <p style="font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#666;margin:0 0 8px;"><a href="{podcast['fiche_url']}" style="color:#666;text-decoration:underline;">← Voir la fiche {podcast['podcast_name']}</a></p>
- .publish-row bordée haut/bas : "Épisode de {podcast['podcast_name']} · ⏱ X min de lecture"
- .cta-listen (seul bouton, accent plein) "Écouter le podcast" → {cta_url}
- .lead-label + .lead (pull-quote analytique de l'épisode)
- .key-facts 3 bullets (pas 4 — spécifique à l'épisode)
- article-body : {h2_instruction} — plus court qu'une fiche podcast globale. Insère un 1er lien texte discret (.inline-cta, souligné, PAS un bouton) juste après la 1ère section H2 → {cta_url}
- .pull-quote ({"AVEC attribution : " + guest_full_name if real_quote else "sans attribution"})
- 2e lien texte discret (.inline-cta) juste avant la FAQ → {cta_url}, formulation différente du premier
- FAQ "Cet épisode répond à ces questions" (H2 sobre, {"TOUTES les Q/R réelles fournies, une entrée par question — pas de plafond" if real_material else "3 Q/R"}, JSON-LD FAQPage) — JAMAIS "on répond"
- footer identique avec lien Listenly générique + lien "Découvrir {podcast['podcast_name']} sur Listenly" (ajoutés automatiquement après génération, ne pas les écrire toi-même)

## JSON-LD (head)
@graph : PodcastEpisode (name=H1, partOfSeries={{"@type":"PodcastSeries","name":"{podcast['podcast_name']}","url":"{listenly_url}"}}, datePublished, description), FAQPage ({"TOUTES les questions réelles listées, une par une" if real_material else "les 3 questions"}), Person (HOST_NAME/HOST_TITLE/worksFor HOST_COMPANY — l'hôte du podcast).
{person_guest_instruction}
Backlinks cachés identiques à la fiche podcast (canonical={ep_url}, og:url={ep_url}, rel=publisher, #semantic-index display:none en fin de <body>).
{"Le bloc #semantic-index doit lister les VRAIES entites nommees fournies plus haut (section MATERIEL REEL) sous forme 'entity: [nom]' une par ligne, plus entity " + guest_full_name if (real_material and guest_full_name) else "Le bloc #semantic-index liste les entites deduites du titre/description (entity PODCAST_NAME, entity HOST_NAME, concept CATEGORIE)."}
AJOUT CONDITIONNEL — HowTo : ajoute UNIQUEMENT si le sujet de cet épisode décrit une vraie démarche étape par étape reproductible (ex: "comment structurer un achat immobilier", "les étapes pour créer une SCI"). N'en ajoute PAS si l'épisode est une interview/discussion générale sans étapes concrètes — un HowTo force sur un contenu qui n'en est pas un est une erreur de balisage à éviter, pas un bonus.

## RÈGLES
- H1 = titre épisode, jamais une question
- FAQ = "Cet épisode répond à ces questions", jamais "on répond"
- Couleur d'accent réservée au seul cta-listen
- CTA principal et les 2 liens discrets pointent TOUS vers {cta_url}, jamais vers l'audio brut, jamais de CTA contact
- Contenu spécifique à CET épisode, pas générique au podcast
- LANGAGE ASSERTIF ET AUTORITAIRE (levier de citabilité IA le mieux établi avec les citations/statistiques) : affirme les faits directement ("X entraîne Y", "Le seuil est de Z€"), évite les tournures évasives ("il semblerait que", "on pourrait dire que", "cela dépend"). Reste factuel et fidèle à la source, mais formule avec assurance plutôt qu'en hésitant.

IMPORTANT : Réponds UNIQUEMENT avec le code HTML complet, de <!DOCTYPE html> à </html>. Aucun texte avant/après, aucun markdown, aucun backtick."""

def call_claude(prompt):
    payload = {"model": MODEL, "max_tokens": 10000, "messages": [{"role": "user", "content": prompt}]}
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

def render_episodes_index(podcast, episodes_meta):
    items = "\n".join(f"""
<div class="item">
  <a class="title" href="{e['url']}">{e['title']}</a>
  <div class="meta">{e.get('pubdate','')}</div>
</div>""" for e in sorted(episodes_meta, key=lambda x: x.get("pubdate",""), reverse=True))

    title = f"Épisodes de {podcast['podcast_name']}"
    n = len(episodes_meta)
    description = f"Retrouvez les {n} fiche{'s' if n > 1 else ''} épisode{'s' if n > 1 else ''} de {podcast['podcast_name']}, référencées par Listenly, avec les questions et sujets abordés."
    canonical = f"https://listenly.fr/podcast-btb/episodes/{SLUG}/index.html"
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
  <div class="eyebrow">Listenly · Épisodes</div>
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
    marker = f"/podcast-btb/episodes/{SLUG}/index.html"
    if marker in html:
        return
    link = (
        f'\n<p style="max-width:720px;margin:0 auto;padding:0 20px 20px;'
        f'font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#999;">'
        f'<a href="{marker}" style="color:#999;text-decoration:underline;">Voir tous les épisodes de ce podcast →</a></p>\n'
    )
    if "</body>" in html:
        html = html.replace("</body>", link + "</body>", 1)
        with open(PARENT_FICHE, "w", encoding="utf-8") as f:
            f.write(html)
        log("Lien 'Voir tous les épisodes' ajouté à la fiche parente")

def main():
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and os.path.exists(f"{PAGES_DIR}/.cron-paused"):
        log("Cron podcast-btb en pause (fichier .cron-paused present) — run ignore.")
        return

    podcast, all_records = load_podcast_record()
    podcast = enrich_from_fiche_html(podcast)
    rss_url = os.environ.get("RSS_URL", "").strip() or podcast.get("rss_url", "")
    if not rss_url:
        log("ERREUR : aucun RSS_URL — ni en variable, ni dans podcasts.json pour ce podcast.")
        sys.exit(1)
    if not podcast.get("listenly_url"):
        log("ERREUR : listenly_url manquant pour ce podcast — impossible de fixer le CTA principal.")
        sys.exit(1)

    log(f"Lecture RSS : {rss_url}")
    try:
        episodes = parse_episodes(fetch_rss(rss_url))
    except Exception as e:
        log(f"ERREUR lecture RSS : {e}")
        sys.exit(1)
    log(f"{len(episodes)} épisode(s) trouvé(s) dans le flux")

    registry = load_registry()
    known_guids = {r["guid"] for r in registry}
    new_episodes = [e for e in episodes if e["guid"] not in known_guids][:MAX_EPISODES]

    if not new_episodes:
        log("Aucun nouvel épisode à traiter — resynchronisation sitemap/historique quand meme.")
        try:
            gen_mod = _load_gen_module()
            gen_mod.build_sitemap()
            gen_mod.build_historique()
            gen_mod.build_llms_txt()
            gen_mod.build_dashboard()
        except Exception as e:
            log(f"AVERTISSEMENT : sitemap/historique non regenere ({e})")
        return

    os.makedirs(EPISODES_DIR, exist_ok=True)
    today = datetime.date.today().isoformat()

    for ep in new_episodes:
        ep_slug = slugify(ep["title"]) or slugify(ep["guid"])
        out_file = f"{EPISODES_DIR}/{ep_slug}.html"
        if os.path.exists(out_file):
            log(f"Fichier deja present : {out_file} — skip, ajout au registre seulement")
            registry.append({"guid": ep["guid"], "slug": ep_slug, "title": ep["title"], "pubdate": ep["pubdate"], "added_date": today})
            continue

        ep_url = f"https://listenly.fr/podcast-btb/episodes/{SLUG}/{ep_slug}.html"
        log(f"Génération épisode : {ep['title']}")

        real_material = None
        if USE_TRANSCRIPT:
            log("USE_TRANSCRIPT actif — tentative d'extraction audio reelle (test)...")
            real_material = get_real_transcript_material(ep, podcast)
            log("Materiel reel obtenu, injection dans le prompt." if real_material else "Pas de materiel reel — generation habituelle (fallback).")

        try:
            html_out = clean_html(call_claude(build_episode_prompt(podcast, ep, ep_slug, ep_url, today, real_material)))
        except Exception as e:
            log(f"ERREUR génération '{ep['title']}' : {e}")
            continue

        if not html_out.lower().startswith("<!doctype"):
            log(f"ERREUR sortie invalide pour '{ep['title']}'")
            continue

        with open(out_file, "w", encoding="utf-8") as f:
            f.write(html_out)
        log(f"✓ Fiche épisode écrite : {out_file}")
        registry.append({"guid": ep["guid"], "slug": ep_slug, "title": ep["title"], "pubdate": ep["pubdate"], "url": ep_url, "added_date": today})

    save_registry(registry)

    index_html = render_episodes_index(podcast, [
        {"title": r["title"], "url": r.get("url", f"https://listenly.fr/podcast-btb/episodes/{SLUG}/{r['slug']}.html"), "pubdate": r.get("pubdate","")}
        for r in registry
    ])
    with open(f"{EPISODES_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    log("Index des épisodes régénéré")

    ensure_parent_link()

    for r in all_records:
        if r["slug"] == SLUG:
            r.update(podcast)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    try:
        gen_mod = _load_gen_module()
        gen_mod.build_sitemap()
        gen_mod.build_historique()
        gen_mod.build_llms_txt()
        gen_mod.build_dashboard()
    except Exception as e:
        log(f"AVERTISSEMENT : sitemap/historique non regenere ({e})")

if __name__ == "__main__":
    main()

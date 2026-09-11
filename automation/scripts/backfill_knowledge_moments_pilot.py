"""
Backfill Knowledge Moments -- GENERALISATION (11/09/2026)
Pour chaque podcast donne, retrouve les timestamps des questions deja en ligne, sans jamais
toucher aux fiches HTML publiees. Ecrit uniquement de nouveaux fichiers JSON dans
pages/podcast-btb/data/knowledge_moments/. Un podcast qui echoue n'arrete pas les autres.

Usage : PODCAST_SLUGS=slug1,slug2,slug3 python3 backfill_knowledge_moments_pilot.py
"""
import os, sys, re, json, glob, urllib.request, urllib.error, tempfile, shutil
import xml.etree.ElementTree as ET
import importlib.util

PAGES_DIR = "pages/podcast-btb"
_slugs_env = os.environ.get("PODCAST_SLUGS", "").strip()
if _slugs_env:
    PODCAST_SLUGS = [s.strip() for s in _slugs_env.split(",") if s.strip()]
else:
    PODCAST_SLUGS = [os.environ["PODCAST_SLUG"].strip()]

def log(msg):
    print(f"[backfill] {msg}", flush=True)

spec = importlib.util.spec_from_file_location("ep_module", "automation/scripts/generate_episode_fiches_btb.py")
emod = importlib.util.module_from_spec(spec)
sys.modules["ep_module"] = emod
os.environ.setdefault("PODCAST_SLUG", PODCAST_SLUGS[0])
spec.loader.exec_module(emod)

with open(f"{PAGES_DIR}/data/podcasts.json", encoding="utf-8") as f:
    ALL_PODCASTS = {p["slug"]: p for p in json.load(f)}

LOCATE_PROMPT = """Voici la transcription d'un episode de podcast, avec reperes de temps [MM:SS].
Voici aussi une liste de questions qui ont deja ete publiees sur un site a partir de CE MEME
episode (elles peuvent y correspondre ou non -- certaines questions de la liste appartiennent
peut-etre a un AUTRE episode du meme podcast, ignore celles qui ne correspondent visiblement pas
au contenu de cette transcription precise).

TRANSCRIPTION :
\"\"\"{transcript}\"\"\"

QUESTIONS A LOCALISER (ne garde que celles qui correspondent vraiment a cette transcription) :
{questions_list}

Reponds UNIQUEMENT avec un JSON, sans markdown :
{{
  "matches": [
    {{"question": "texte exact de la question depuis la liste", "start_seconds": 154, "end_seconds": 210}}
  ]
}}
Si aucune question de la liste ne correspond a cette transcription, renvoie {{"matches": []}}.
N'invente jamais un timestamp -- deduis-le uniquement des reperes [MM:SS] reellement presents."""

grand_total = 0
podcasts_ok = 0
podcasts_failed = []

for slug in PODCAST_SLUGS:
    log(f"##### PODCAST : {slug} #####")
    try:
        podcast = ALL_PODCASTS.get(slug)
        if not podcast:
            log(f"ERREUR : '{slug}' introuvable dans podcasts.json -- ignore.")
            podcasts_failed.append(slug)
            continue

        req = urllib.request.Request(podcast["rss_url"], headers={
            "User-Agent": "Mozilla/5.0 (compatible; ListenlyGEO/1.0; +https://listenly.fr)"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            rss_xml = resp.read()
        root = ET.fromstring(rss_xml)

        guid_map = {}
        for item in root.iter("item"):
            guid_el = item.find("guid")
            enclosure_el = item.find("enclosure")
            title_el = item.find("title")
            if guid_el is not None and enclosure_el is not None:
                guid_map[guid_el.text.strip()] = {
                    "audio_url": enclosure_el.get("url"),
                    "title": (title_el.text or "").strip() if title_el is not None else "",
                }

        registry_path = f"{PAGES_DIR}/questions/{slug}/_qa_registry.json"
        if not os.path.exists(registry_path):
            log(f"Pas de registre pour '{slug}' -- ignore.")
            podcasts_failed.append(slug)
            continue
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
        known_guids = registry.get("known_episode_guids", [])

        resolved = [g for g in known_guids if g in guid_map]
        unresolved = [g for g in known_guids if g not in guid_map]
        log(f"Episodes connus : {len(known_guids)} | resolus : {len(resolved)} | non resolus : {len(unresolved)}")

        fiche_files = glob.glob(f"{PAGES_DIR}/questions/{slug}/*.html")
        fiche_files = [f for f in fiche_files if not f.endswith("index.html")]
        published_questions = []
        for ff in fiche_files:
            with open(ff, encoding="utf-8") as f:
                html = f.read()
            m = re.search(r'"headline"\s*:\s*"([^"]+)"', html)
            if m:
                published_questions.append(m.group(1))
        log(f"Fiches question deja publiees : {len(published_questions)}")

        podcast_total = 0
        for guid in resolved:
            ep_info = guid_map[guid]
            log(f"--- Episode : {ep_info['title'][:70]} ---")
            tmpdir = tempfile.mkdtemp(prefix="backfill_")
            try:
                audio_path = os.path.join(tmpdir, "episode.mp3")
                size = emod.download_audio(ep_info["audio_url"], audio_path)
                audio_path = emod.compress_audio_if_needed(audio_path, size)
                transcript, segments = emod.transcribe(audio_path, podcast.get("language", "en"))
                if not transcript:
                    log("Transcription vide, episode ignore.")
                    continue
                transcript_ts = emod.build_timestamped_transcript(transcript, segments)

                prompt = LOCATE_PROMPT.format(
                    transcript=transcript_ts,
                    questions_list="\n".join(f"- {q}" for q in published_questions),
                )
                raw = emod.call_claude(prompt)
                raw = re.sub(r"^```json\s*|\s*```$", "", raw.strip())
                data = json.loads(raw)
                matches = data.get("matches", [])
                log(f"{len(matches)} question(s) localisee(s).")

                matched_texts = {m.get("question", "").strip() for m in matches}
                published_questions = [q for q in published_questions if q.strip() not in matched_texts]

                if matches:
                    moments = []
                    for m in matches:
                        moments.append({
                            "podcast_name": podcast["podcast_name"],
                            "episode_title": ep_info["title"],
                            "audio_url": ep_info["audio_url"],
                            "question": m.get("question", ""),
                            "transcript_excerpt": "",
                            "expert_name": podcast.get("host_name"),
                            "start_seconds": m.get("start_seconds", 0) or 0,
                            "end_seconds": m.get("end_seconds", 0) or 0,
                        })
                    os.makedirs(f"{PAGES_DIR}/data/knowledge_moments", exist_ok=True)
                    ep_slug = emod.slugify(ep_info["title"])[:80]
                    out_path = f"{PAGES_DIR}/data/knowledge_moments/{slug}--backfill--{ep_slug}.json"
                    with open(out_path, "w", encoding="utf-8") as f:
                        json.dump(moments, f, ensure_ascii=False, indent=2)
                    podcast_total += len(matches)
            except Exception as e:
                log(f"ECHEC sur cet episode ({e}) -- episode ignore.")
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)

        log(f"Podcast '{slug}' termine : {podcast_total} knowledge moments.")
        grand_total += podcast_total
        podcasts_ok += 1
    except Exception as e:
        log(f"ECHEC complet sur le podcast '{slug}' ({e}) -- podcast ignore, on continue avec le suivant.")
        podcasts_failed.append(slug)

log(f"=== LOT TERMINE : {podcasts_ok}/{len(PODCAST_SLUGS)} podcasts OK, {grand_total} knowledge moments au total ===")
if podcasts_failed:
    log(f"Podcasts en echec : {podcasts_failed}")

#!/usr/bin/env python3
"""
MarketForge Engine — file d'attente d'EXTRACTION pure (27/09/2026).

But : pour chaque podcast prospect (fiche N1 deja creee), extraire les vraies Q/R de
quelques episodes et les pousser dans le hub knowledge (JSON + base Listenly via
knowledge-moments-import.php), SANS generer aucune fiche question HTML.
La preuve (proof_url) est ensuite lue par le script mail.

Reutilise tel quel le pipeline existant de generate_episode_fiches_btb.py :
download_audio -> compress_audio_if_needed -> transcribe -> extract_real_qa ->
save_knowledge_moments (JSON + push DB). Aucune logique d'extraction dupliquee.

Pilotage : automation/marketforge_engine/config.json (debit quotidien, pause...).
Etat     : automation/marketforge_engine/queue.json (statut par podcast + journal/jour).

Entree dans la file :
  - automatique : tout podcast de podcasts.json avec rss_url et date >= entree_auto_depuis_date
  - manuelle    : slugs listes dans "ajouter_manuellement"
  - "exclure"   : jamais traites

Variables : ANTHROPIC_API_KEY, GROQ_API_KEY (ou OPENAI_API_KEY), KNOWLEDGE_IMPORT_SECRET
Optionnelles : EPISODES_PAR_JOUR (surcharge ponctuelle), DRY_RUN=1 (planifie sans rien extraire)
"""
import os, sys, json, datetime, hashlib, tempfile, shutil, urllib.parse, importlib.util
import xml.etree.ElementTree as ET

ENGINE_DIR = "automation/marketforge_engine"
CONFIG_FILE = f"{ENGINE_DIR}/config.json"
QUEUE_FILE = f"{ENGINE_DIR}/queue.json"
PAGES_DIR = "pages/podcast-btb"
PODCASTS_FILE = f"{PAGES_DIR}/data/podcasts.json"
QUESTIONS_DIR = f"{PAGES_DIR}/questions"
DEFAULT_EPISODE_MINUTES = 60  # si itunes:duration absent du flux
INBOX_ROOT = "automation/inbox/moteur-trafic-transcripts"  # stock lu par generate_qa_fiches_btb.py
INBOX_TRANSCRIPT_MAX = 20000
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rss_contact import extract_contact_email, fetch_contact_email, check_email  # noqa: E402
import hub_index  # noqa: E402

DRY_RUN = os.environ.get("DRY_RUN", "").strip() in ("1", "true", "yes")
TODAY = datetime.date.today().isoformat()


def log(msg):
    print(f"[marketforge-engine] {msg}", flush=True)


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


# --- Module d'extraction existant (charge une seule fois, SLUG change par podcast) ---
_emod = None

def emod():
    global _emod
    if _emod is None:
        os.environ.setdefault("PODCAST_SLUG", "marketforge-engine")
        os.environ.setdefault("ANTHROPIC_API_KEY", "unused")
        spec = importlib.util.spec_from_file_location(
            "ep_module", "automation/scripts/generate_episode_fiches_btb.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["ep_module"] = mod
        spec.loader.exec_module(mod)
        _emod = mod
    return _emod


def set_questions_max(mod, n):
    """Le prompt existant plafonne a 6 Q/R par episode ; on ajuste ce plafond pour ce
    moteur uniquement (le fichier source n'est pas modifie)."""
    if n and n != 6 and "(6 MAXIMUM)" in mod.EXTRACT_REAL_QA_PROMPT:
        mod.EXTRACT_REAL_QA_PROMPT = mod.EXTRACT_REAL_QA_PROMPT.replace("(6 MAXIMUM)", f"({n} MAXIMUM)")


# --- RSS : episodes + duree (pour le budget minutes) ---
ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"

def parse_duration_minutes(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        if ":" in raw:
            parts = [int(float(p)) for p in raw.split(":")]
            secs = 0
            for p in parts:
                secs = secs * 60 + p
        else:
            secs = int(float(raw))
        return max(1, round(secs / 60))
    except ValueError:
        return None


def read_rss(url):
    xml_bytes = emod().fetch_rss(url)
    episodes = emod().parse_episodes(xml_bytes)
    durations = {}
    try:
        root = ET.fromstring(xml_bytes)
        for item in root.iter("item"):
            title_el = item.find("title")
            title = emod().clean_text(title_el.text) if title_el is not None and title_el.text else ""
            dur = item.find(f"{ITUNES}duration")
            durations[title] = parse_duration_minutes(dur.text if dur is not None else "")
    except ET.ParseError:
        pass
    for ep in episodes:
        ep["minutes"] = durations.get(ep["title"]) or DEFAULT_EPISODE_MINUTES
    return episodes, extract_contact_email(xml_bytes)


def already_mined_guids(slug):
    """Episodes deja mines par le moteur trafic (fiches requete) : pas de double cout Whisper."""
    reg = load_json(f"{QUESTIONS_DIR}/{slug}/_qa_registry.json", {})
    return set(reg.get("known_episode_guids", []))


# --- File d'attente ---
def sync_queue(queue, config, podcasts):
    since = config.get("entree_auto_depuis_date") or TODAY
    manual = set(config.get("ajouter_manuellement") or [])
    # Podcasts onboardes par le run (y compris fiches N1 plus anciennes rattachees au moteur)
    manual |= {o.get("slug") for o in load_json(f"{ENGINE_DIR}/last_onboard.json", {}).get("onboarded", []) if o.get("slug")}
    excluded = set(config.get("exclure") or [])
    added = []
    for p in podcasts:
        slug = p.get("slug")
        if not slug or slug in queue["podcasts"] or slug in excluded:
            continue
        if not p.get("rss_url"):
            continue
        if slug in manual or (p.get("date") or "") >= since:
            queue["podcasts"][slug] = {
                "status": "en_attente",
                "added": TODAY,
                "episodes_done": [],
                "moments_count": 0,
                "podcast_name": p.get("podcast_name", ""),
                "fiche_url": p.get("fiche_url", ""),
                "email": "",
                "proof_url": "",
                "last_error": "",
            }
            added.append(slug)
    for slug in manual - set(p.get("slug") for p in podcasts):
        log(f"AVERTISSEMENT : '{slug}' (ajouter_manuellement) absent de podcasts.json — cree d'abord sa fiche N1.")
    for slug in excluded:
        if slug in queue["podcasts"] and queue["podcasts"][slug]["status"] != "extrait":
            queue["podcasts"][slug]["status"] = "exclu"
    if added:
        log(f"{len(added)} podcast(s) ajoute(s) a la file : {', '.join(added)}")
    return added


def build_proof_url(config, podcast):
    tpl = config.get("proof_url_template") or ""
    name = podcast.get("podcast_name", "")
    return tpl.format(
        slug=podcast.get("slug", ""),
        podcast_name=name,
        podcast_name_url=urllib.parse.quote_plus(name),
        fiche_url=podcast.get("fiche_url") or f"https://listenly.fr/podcast-btb/{podcast.get('slug', '')}-podcast.html",
    )


def save_inbox_stock(podcast, ep, transcript, guest, qa, quote, stats, entities):
    """Stock complet pour la future machine a fiches : meme format que l'inbox deja consommee par
    generate_qa_fiches_btb.py (try_load_from_inbox). Activer le moteur trafic sur ce podcast
    suffira a generer les fiches, sans re-transcrire (dedoublonnage par episode_guid)."""
    inbox = f"{INBOX_ROOT}/{podcast['slug']}"
    os.makedirs(inbox, exist_ok=True)
    guid = ep.get("guid") or ep.get("title", "")
    payload = {
        "episode_guid": guid,
        "source_kind": "marketforge_engine",
        "source_url": ep.get("audio_url", ""),
        "episode_title": ep.get("title", ""),
        "pubdate": ep.get("pubdate", ""),
        "real_qa": qa,
        "guest": guest or {},
        "real_quote": quote or "",
        "key_stats": stats or [],
        "entities": entities or [],
        "transcript_full": (transcript or "")[:INBOX_TRANSCRIPT_MAX],
        "extracted_date": TODAY,
    }
    name = "mfe-" + hashlib.sha1(guid.encode("utf-8")).hexdigest()[:16] + ".json"
    save_json(os.path.join(inbox, name), payload)


def refresh_hub(podcast):
    """Met a jour le bloc « Les reponses de ce podcast » de la fiche N1 (preuve du mail)."""
    reg = load_json(f"{QUESTIONS_DIR}/{podcast['slug']}/_qa_registry.json", {})
    n1_path = f"{PAGES_DIR}/{podcast['slug']}-podcast.html"
    try:
        # Lecteur de moments : les nouvelles questions doivent ouvrir ecouter.html au bon moment.
        # Cache vide (un episode vient d'etre ecrit) + index du podcast reecrit avec le hub.
        import moments_index
        moments_index.invalidate(podcast["slug"])
        ok = hub_index.apply_hub_index(n1_path, podcast, reg.get("published", []))
        moments_index.build_index(podcast, moments_index.load_json(moments_index.EP_URLS_FILE, {}))
        return ok
    except Exception as e:
        log(f"AVERTISSEMENT hub N1 non mis a jour ({e})")
        return False


def extract_episode(podcast, ep):
    """Pipeline existant, sans generation de fiche. Retourne le nombre de Q/R ecrites."""
    m = emod()
    m.SLUG = podcast["slug"]  # save_knowledge_moments nomme le fichier avec ce slug
    tmpdir = tempfile.mkdtemp(prefix="mf_engine_")
    try:
        audio_path = os.path.join(tmpdir, "episode.mp3")
        size = m.download_audio(ep["audio_url"], audio_path)
        audio_path = m.compress_audio_if_needed(audio_path, size)
        if getattr(m, "WHISPER_SPEEDUP_FACTOR", 1.0) != 1.0:
            audio_path = m.speed_up_audio(audio_path)
        transcript, segments = m.transcribe(audio_path, podcast.get("language", "en"))
        if not transcript:
            log("Transcription vide — episode ignore.")
            return 0
        guest, qa, quote, stats, entities = m.extract_real_qa(transcript, ep, podcast, segments)
        if not qa:
            return 0
        m.save_knowledge_moments(podcast, ep, guest, qa)  # JSON + push base Listenly (hub)
        save_inbox_stock(podcast, ep, transcript, guest, qa, quote, stats, entities)
        return len(qa)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    config = load_json(CONFIG_FILE, {})
    if config.get("pause"):
        log("pause=true dans config.json — aucun traitement.")
        return

    queue = load_json(QUEUE_FILE, {"podcasts": {}, "journal": {}})
    queue.setdefault("podcasts", {})
    queue.setdefault("journal", {})
    podcasts = {p["slug"]: p for p in load_json(PODCASTS_FILE, []) if p.get("slug")}
    sync_queue(queue, config, list(podcasts.values()))
    if not DRY_RUN:
        save_json(QUEUE_FILE, queue)  # le hub N1 lit la file pour savoir quels podcasts enrichir

    eps_per_day = int(os.environ.get("EPISODES_PAR_JOUR") or config.get("episodes_par_jour", 10))
    eps_per_podcast = int(config.get("episodes_par_podcast", 3))
    minutes_max = int(config.get("minutes_audio_max_jour", 600))
    journal = queue["journal"].setdefault(TODAY, {"episodes": 0, "minutes": 0, "moments": 0})
    # garde les 30 derniers jours seulement
    for d in sorted(queue["journal"])[:-30]:
        del queue["journal"][d]

    if not DRY_RUN:
        set_questions_max(emod(), int(config.get("questions_max_par_episode", 6)))

    log(f"Budget du jour : {journal['episodes']}/{eps_per_day} episodes, {journal['minutes']}/{minutes_max} min deja consommes.")

    # --- Mode CONTACT (27/09/2026) : fiche N1 + email -> pret pour le mail, sans extraction ---
    # L'extraction (Whisper + Claude) n'est faite que si extraction_auto=true, ou pour les slugs
    # listes dans "extraire" (ex. prospects qui ont repondu). Tous les autres passent directement
    # en statut "contact" avec leur fiche N1 comme preuve.
    extraction_auto = bool(config.get("extraction_auto", False))
    extraire = set(config.get("extraire") or [])
    contacts, sans_email = 0, 0
    for slug, state in queue["podcasts"].items():  # infos pour personnaliser le mail
        p = podcasts.get(slug) or {}
        state["host_name"] = state.get("host_name") or p.get("host_name", "")
        state["listenly_url"] = state.get("listenly_url") or p.get("listenly_url", "")
    # Anti-rebond : re-verifie aussi les contacts deja prets (email d'hebergeur, boite technique,
    # domaine sans serveur mail) -> on retente le flux RSS pour une meilleure adresse, sinon sans_email.
    rejetes = 0
    for slug, state in queue["podcasts"].items():
        if state["status"] != "contact" or not state.get("email") or state.get("email_ok"):
            continue
        why = check_email(state["email"])
        if not why:
            state["email_ok"] = True
            continue
        podcast = podcasts.get(slug) or {}
        better = fetch_contact_email(podcast["rss_url"]) if podcast.get("rss_url") else ""
        if better and better != state["email"] and not check_email(better):
            log(f"Email remplace pour {slug} : {state['email']} -> {better} ({why})")
            state["email"], state["email_ok"] = better, True
            continue
        log(f"Email rejete pour {slug} : {state['email']} ({why})")
        state["email_rejete"] = f"{state['email']} ({why})"
        state["email"], state["proof_url"], state["status"] = "", "", "sans_email"
        rejetes += 1
    for slug, state in queue["podcasts"].items():
        if state["status"] != "en_attente" or extraction_auto or slug in extraire:
            continue
        podcast = podcasts.get(slug)
        if not podcast:
            state["status"] = "erreur"; state["last_error"] = "absent de podcasts.json"; continue
        state["podcast_name"] = state.get("podcast_name") or podcast.get("podcast_name", "")
        state["fiche_url"] = state.get("fiche_url") or podcast.get("fiche_url", "")
        email = state.get("email") or (fetch_contact_email(podcast["rss_url"]) if podcast.get("rss_url") else "")
        why = check_email(email) if email else ""
        if why:
            log(f"Email rejete pour {slug} : {email} ({why})")
            state["email_rejete"] = f"{email} ({why})"
            email, rejetes = "", rejetes + 1
        state["email"] = email
        state["email_ok"] = bool(email)
        if email:
            state["proof_url"] = state.get("proof_url") or build_proof_url(config, podcast)
            state["proof_date"] = state.get("proof_date") or TODAY
            state["status"] = "contact"
            contacts += 1
        else:
            state["status"] = "sans_email"
            sans_email += 1
    journal["contacts"] = journal.get("contacts", 0) + contacts
    journal["emails_rejetes"] = journal.get("emails_rejetes", 0) + rejetes
    log(f"Mode contact : {contacts} contact(s) pret(s) (fiche N1 + email), {sans_email} sans email, "
        f"{rejetes} email(s) rejete(s) (anti-rebond).")

    # Extraction differee (29/09/2026) : 0 question cote prospect ; demarre 7 jours apres le 1er mail
    # sans reponse, tout de suite pour les podcasts jamais contactables. Voir hub_index.extraction_allowed.
    differee = int(config.get("extraction_apres_jours", 7) or 0) > 0
    gsc = load_json(f"{PAGES_DIR}/data/gsc_pages.json", {}).get("pages", {})
    imp = {u.rsplit("/", 1)[-1].replace("-podcast.html", ""): v.get("impressions", 0) for u, v in gsc.items()}
    order = sorted(
        (s for s, st in queue["podcasts"].items()
         if (extraction_auto and st["status"] in ("en_attente", "en_cours"))
         or (s in extraire and st["status"] in ("en_attente", "en_cours", "contact", "sans_email"))
         or (differee and st["status"] in ("contact", "sans_email", "en_cours")
             and hub_index.extraction_allowed(s, st["status"]))),
        key=lambda s: (queue["podcasts"][s]["status"] != "en_cours", -imp.get(s, 0), queue["podcasts"][s]["added"], s),
    )
    log(f"{len(order)} podcast(s) dans la file active.")

    for slug in order:
        if journal["episodes"] >= eps_per_day or journal["minutes"] >= minutes_max:
            log("Budget du jour atteint — la suite reprend au prochain run.")
            break
        state = queue["podcasts"][slug]
        podcast = podcasts.get(slug)
        if not podcast:
            state["status"] = "erreur"
            state["last_error"] = "absent de podcasts.json"
            continue

        remaining = eps_per_podcast - len(state["episodes_done"])
        log(f"### {slug} ({len(state['episodes_done'])}/{eps_per_podcast} episodes extraits)")
        try:
            episodes, email = read_rss(podcast["rss_url"])
            if email and not state.get("email"):
                state["email"] = email
            state.setdefault("podcast_name", podcast.get("podcast_name", ""))
            state.setdefault("fiche_url", podcast.get("fiche_url", ""))
        except Exception as e:
            state["last_error"] = f"RSS illisible : {e}"[:200]
            log(f"ERREUR RSS ({e}) — podcast saute ce run.")
            continue

        skip = set(state["episodes_done"]) | already_mined_guids(slug)
        todo = [e for e in episodes if e.get("audio_url") and e["guid"] not in skip]
        if not todo:
            state["status"] = "extrait"
            log("Plus aucun episode disponible — podcast marque extrait.")

        for ep in todo[:remaining]:
            if journal["episodes"] >= eps_per_day:
                break
            if journal["minutes"] + ep["minutes"] > minutes_max and journal["episodes"] > 0:
                log(f"Episode de {ep['minutes']} min depasserait le budget minutes — reporte.")
                break
            log(f"Extraction : {ep['title'][:80]} ({ep['minutes']} min)")
            if DRY_RUN:
                n = 0
            else:
                try:
                    n = extract_episode(podcast, ep)
                    state["last_error"] = ""
                except Exception as e:
                    n = 0
                    state["last_error"] = str(e)[:200]
                    log(f"ECHEC extraction ({e}) — episode marque traite pour ne pas boucler dessus.")
            state["episodes_done"].append(ep["guid"])
            state["moments_count"] += n
            state["status"] = "en_cours"
            journal["episodes"] += 1
            journal["minutes"] += ep["minutes"]
            journal["moments"] += n
            log(f"  -> {n} Q/R ajoutee(s) au hub.")

        left = [e for e in todo if e["guid"] not in state["episodes_done"]]
        if len(state["episodes_done"]) >= eps_per_podcast or not left:
            state["status"] = "extrait"
        if state["moments_count"] > 0 and not DRY_RUN:
            if refresh_hub(podcast):
                log("Hub N1 mis a jour avec les reponses extraites.")
            if not state["proof_url"]:
                state["proof_url"] = build_proof_url(config, podcast)
                state["proof_date"] = TODAY
        if not state.get("email"):
            state["status_email"] = "sans_email"
        else:
            state.pop("status_email", None)

    if DRY_RUN:
        log("DRY_RUN : aucun fichier modifie.")
        return
    save_json(QUEUE_FILE, queue)
    counts = {}
    for st in queue["podcasts"].values():
        counts[st["status"]] = counts.get(st["status"], 0) + 1
    log(f"Termine. Aujourd'hui : {journal['episodes']} episodes, {journal['minutes']} min, {journal['moments']} Q/R. File : {counts}")


if __name__ == "__main__":
    main()

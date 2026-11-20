#!/usr/bin/env python3
"""
Generateur d'Index client (16/11/2026, lot 2 de l'onboarding).

Pour chaque ligne "A construire" de l'onglet Onboarding (paiement verifie par Stripe) :
  1. statut -> "En construction"
  2. lit le flux RSS du client, prend ses derniers episodes
  3. transcrit les N premieres minutes (transcription publiee du flux si elle existe = gratuit, sinon Whisper)
  4. extrait les vraies questions / reponses avec leurs horaires (pipeline existant)
  5. cree le site du client dans l'app Index (si besoin) et importe les pages (endpoint /hub/import, publie)
  6. statut -> "Pret" + lien dans le Sheet + mail au client et a Etienne (Apps Script)
En cas d'echec : statut "Erreur" + alerte. Aucun effet de bord sur Listenly (rien n'est enregistre dans la base des moments).

Variables : MFE_SHEET_URL (avec ?secret=), HUB_IMPORT_TOKEN, ANTHROPIC_API_KEY, GROQ_API_KEY (ou OPENAI_API_KEY)
Optionnelles : INDEX_EPISODES_MAX (6), INDEX_CLIENTS_MAX (2), INDEX_AUDIO_MIN (20), INDEX_TEST_EMAILS (adresses autorisees sans paiement verifie), DRY_RUN=1
"""
import os, sys, re, json, time, tempfile, shutil, subprocess, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet_bridge as sb  # noqa: E402
import marketforge_extract_queue as xq  # noqa: E402

HUB_URL = "https://app.marketforge.fr/hub/import"
BASE_DOCS = "https://app.marketforge.fr/docs"
MAX_EPISODES = int(os.environ.get("INDEX_EPISODES_MAX") or 6)
MAX_CLIENTS = int(os.environ.get("INDEX_CLIENTS_MAX") or 2)
AUDIO_MIN = int(os.environ.get("INDEX_AUDIO_MIN") or 20)
TEST_EMAILS = {e.strip().lower() for e in (os.environ.get("INDEX_TEST_EMAILS")
               or "etienne.cugnet@gmail.com,etienne.cugnet@marketforge.fr").split(",") if e.strip()}
DRY_RUN = os.environ.get("DRY_RUN", "").strip() in ("1", "true", "yes")
# File de pages (19/11/2026) : extraction complete au paiement, 5 pages en ligne tout de suite, puis 1 par jour (index_daily.py).
# 22/11/2026 : un cycle = un mois d'abonnement = 30 pages, extraites de 12 episodes au plus (cout maitrise).
QUEUE_EPISODES = int(os.environ.get("INDEX_QUEUE_EPISODES") or 12)
QUEUE_MAX = int(os.environ.get("INDEX_QUEUE_MAX") or 30)
FIRST_BATCH = int(os.environ.get("INDEX_FIRST_BATCH") or 5)
QUEUE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "onboarding_queue")

CTA_TEXT = {
    "Clients / leads": "Work with us",
    "Booked calls": "Book a call with us",
    "Newsletter subscribers": "Join the newsletter",
    "Product sales": "Get the offer",
}


def log(msg):
    print(f"[index-builder] {msg}", flush=True)


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower().encode("ascii", "ignore").decode()).strip("-")
    return s[:60] or "index"


def set_status(row, statut, note="", url=""):
    if DRY_RUN:
        log(f"[dry] ligne {row} -> {statut} {note} {url}")
        return
    sb.call(payload={"action": "onboarding_update", "row": row, "statut": statut, "note": note, "url": url})


def qkey(q):
    return re.sub(r"\W+", " ", (q or "").lower()).strip()


def pending():
    j = sb.call(payload={"action": "onboarding_pending"})
    return j.get("rows", []) if isinstance(j, dict) and j.get("ok") else []


def extract_answers(podcast, episodes, trim_min, max_eps=None):
    """Retourne la liste des reponses (format de l'import) pour les derniers episodes."""
    m = xq.emod()
    m.SLUG = podcast["slug"]
    xq.AUDIO_TRIM_MIN = trim_min
    answers, done = [], 0
    for ep in episodes:
        if done >= (max_eps or MAX_EPISODES):
            break
        if not ep.get("audio_url"):
            continue
        tmp = tempfile.mkdtemp(prefix="mf_index_")
        try:
            published = xq.fetch_published_transcript(ep)
            if published:
                transcript, segments = published
                kept = [s for s in segments if float(s.get("start", 0) or 0) <= trim_min * 60]
                if len(kept) >= 20:
                    segments = kept
                    transcript = " ".join(str(s.get("text", "")).strip() for s in kept).strip()
                log(f"Transcription publiee (gratuit) : {ep['title'][:60]}")
            else:
                path = os.path.join(tmp, "episode.mp3")
                size = m.download_audio(ep["audio_url"], path)
                out = os.path.join(tmp, "trim.mp3")
                subprocess.run(["ffmpeg", "-y", "-i", path, "-t", str(trim_min * 60), "-vn", "-ac", "1", "-ar", "16000",
                                "-b:a", "32k", out], check=True, capture_output=True)
                transcript, segments = m.transcribe(out, podcast.get("language", "en"))
                log(f"Transcription Whisper ({trim_min} min) : {ep['title'][:60]}")
            if not transcript:
                continue
            guest, qa, quote, stats, _entities = m.extract_real_qa(transcript, ep, podcast, segments)
            done += 1
            guest_name = f"{guest.get('prenom', '')} {guest.get('nom', '')}".strip()
            for i, it in enumerate(qa or []):
                q, r = (it.get("q") or "").strip(), (it.get("r") or "").strip()
                if not q or len(r) < 200:
                    continue
                answers.append({
                    "question": q, "answer": r, "episode": ep["title"], "guest": guest_name,
                    "audio_url": ep["audio_url"], "start_sec": int(it.get("start_seconds", 0) or 0),
                    "listenly_url": "", "topic": "",
                    "quote": quote if i == 0 else "", "quote_by": guest_name if i == 0 and quote else "",
                    "key_points": [str(s) for s in (stats or []) if isinstance(s, str)][:3] if i == 0 else [],
                })
        except Exception as e:  # un episode en echec ne bloque pas les autres
            log(f"Episode ignore ({type(e).__name__}: {str(e)[:120]}) : {ep.get('title', '')[:60]}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    log(f"{done} episode(s) traite(s), {len(answers)} reponse(s) utilisable(s).")
    return answers


def post_import(payload):
    """Un envoi vers l'app, avec 3 essais (l'hebergeur renvoie parfois un 502/503 passager). L'import est idempotent."""
    token = os.environ.get("HUB_IMPORT_TOKEN", "")
    if not token:
        raise RuntimeError("HUB_IMPORT_TOKEN manquant")
    last = None
    for attempt in range(3):
        req = urllib.request.Request(HUB_URL, data=json.dumps(payload, ensure_ascii=False).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-Hub-Token": token})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = RuntimeError(f"import HTTP {e.code} : {e.read().decode(errors='replace')[:200]}")
            if e.code not in (500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError) as e:
            last = RuntimeError(f"import injoignable : {e}")
        time.sleep(25 * (attempt + 1))
    raise last


def build(row):
    num = row["row"]
    name = (row.get("Nom affiche") or row.get("Podcast") or "Podcast").strip()
    rss = (row.get("Flux RSS") or "").strip()
    log(f"=== Ligne {num} : {name} ({rss}) ===")
    set_status(num, "En construction")
    episodes, _contact = xq.read_rss(rss)
    podcast = {"slug": slugify(name), "podcast_name": name, "rss_url": rss, "language": "en"}
    # Les episodes ayant une transcription publiee (gratuite) passent d'abord, puis les plus recents.
    with_audio = [e for e in episodes if e.get("audio_url")]
    episodes = sorted(with_audio, key=lambda e: 0 if e.get("transcript_url") else 1)[: QUEUE_EPISODES * 2]
    answers = extract_answers(podcast, episodes, AUDIO_MIN, QUEUE_EPISODES)
    if not answers:
        raise RuntimeError("aucune reponse exploitable extraite des episodes")
    site = slugify(name) + "-index"
    # Dedoublonnage des questions, plafond de la file, puis : 5 pages en ligne, le reste en file (publie chaque jour).
    seen, uniq = set(), []
    for a in answers:
        k = qkey(a["question"])
        if k and k not in seen:
            seen.add(k)
            uniq.append(a)
    answers = uniq[:QUEUE_MAX]
    total = len(answers)
    first, rest = answers[:FIRST_BATCH], answers[FIRST_BATCH:]
    if not DRY_RUN:
        # 20/11/2026 : la file est toujours creee (meme vide) : elle porte le cycle mensuel (renouvellement, pause) et la memoire des episodes utilises.
        os.makedirs(QUEUE_DIR, exist_ok=True)
        with open(os.path.join(QUEUE_DIR, site + ".json"), "w", encoding="utf-8") as f:
            json.dump({"site": site, "podcast": name, "cta_url": (row.get("Lien du bouton") or "").strip(),
                       "cta_text": CTA_TEXT.get(row.get("Objectif", ""), "Learn more"),
                       "created": time.strftime("%Y-%m-%d"), "cycle": 1, "cycle_start": time.strftime("%Y-%m-%d"),
                       "live": len(first), "used_episodes": sorted({a["episode"] for a in answers}),
                       "keys": sorted(seen), "pointer": 0, "last_publish": "", "pages": rest},
                      f, ensure_ascii=False, indent=1)
        log(f"File creee : {len(rest)} page(s) en attente, 1 par jour.")
    answers = first
    payload = {
        "site": site, "create_site": name, "podcast": name, "publish": True, "docs_theme": "mintlify",
        "cta_url": (row.get("Lien du bouton") or "").strip(),
        "cta_text": CTA_TEXT.get(row.get("Objectif", ""), "Learn more"),
        "answers": answers, "dry_run": DRY_RUN,
    }
    # Envoi par lots de 8 pages (charge raisonnable pour l'hebergeur) : le site est cree au 1er lot, la mise en ligne se fait au dernier.
    lots = [answers[i:i + 8] for i in range(0, len(answers), 8)]
    for n, lot in enumerate(lots, 1):
        part = dict(payload, answers=lot, publish=(n == len(lots)))
        res = post_import(part)
        log(f"Import lot {n}/{len(lots)} : {str(res.get('output', ''))[-160:]}")
        if not res.get("ok"):
            raise RuntimeError("import refuse : " + str(res.get("output", ""))[:200])
    return f"{BASE_DOCS}/{site}", total, len(first)


def main():
    if not sb.URL:
        log("MFE_SHEET_URL manquant : rien a faire.")
        return
    rows = pending()
    todo = []
    for r in rows:
        ok_pay = str(r.get("Paiement", "")).startswith("paye")
        if ok_pay or (r.get("Email", "").strip().lower() in TEST_EMAILS):
            todo.append(r)
        else:
            log(f"Ligne {r.get('row')} ignoree : paiement non verifie ({r.get('Email', '')}).")
    log(f"{len(rows)} ligne(s) en attente, {len(todo)} a construire (max {MAX_CLIENTS} par passage).")
    for r in todo[:MAX_CLIENTS]:
        try:
            url, n, live = build(r)
            set_status(r["row"], "Pret", f"{live} pages en ligne, {n} en file (1 par jour)", url)
            log(f"Pret : {url}")
        except Exception as e:
            log(f"ERREUR ligne {r.get('row')} : {type(e).__name__}: {e}")
            set_status(r["row"], "Erreur", f"{type(e).__name__}: {str(e)[:300]}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
MOMENTS CONNUS (08/11/2026) : pipeline separe de MarketForge, dedie aux podcasts connus (niveau A).

But : extraire de vraies Q/R des episodes des podcasts connus pour alimenter le SCORING MOMENT SYSTEM
(listenly.org). N'ecrit jamais dans la file, le reservoir ni les statistiques de prospection de MarketForge.

Reutilise le code d'extraction existant (marketforge_extract_queue.py : transcription publiee ou Whisper,
extract_real_qa, save_knowledge_moments) sans le modifier. Seuls la file, les reglages et le reservoir sont a part :
  Reglages : automation/moments_connus/config.json   (debit : 20 episodes/jour, 3 max par podcast et par jour)
  Etat     : automation/moments_connus/queue.json    (episodes traites par podcast + journal du jour)
  Reservoir: automation/moments_connus/reservoir_connus.json

Variables : ANTHROPIC_API_KEY, GROQ_API_KEY (ou OPENAI_API_KEY), KNOWLEDGE_IMPORT_SECRET
Optionnelle : DRY_RUN=1 (planifie sans rien extraire ni ecrire)
"""
import os, sys, json, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import marketforge_extract_queue as mq  # noqa: E402  (bibliotheque : main() n'est pas lance a l'import)
import reservoir_questions  # noqa: E402

DIR = "automation/moments_connus"
CONFIG_FILE = f"{DIR}/config.json"
QUEUE_FILE = f"{DIR}/queue.json"
PRIORITE_FILE = "pages/podcast-btb/data/priorite_podcasts.json"
DRY_RUN = os.environ.get("DRY_RUN", "").strip() in ("1", "true", "yes")
TODAY = datetime.date.today().isoformat()

# Reservoir a part : MarketForge garde le sien intact.
reservoir_questions.RESERVOIR_FILE = f"{DIR}/reservoir_connus.json"


def log(msg):
    print(f"[moments-connus] {msg}", flush=True)


# --- Filtre « episodes de fond » (08/11/2026) : privilegier interviews et explications, eviter l'actualite ---
NEWS = ("breaking", "what happened", "midterm", "election", "live from", "this week", "recap", "headlines",
        "tonight", "today's", "monday", "tuesday", "wednesday", "thursday", "friday", "sentencing", "trial",
        "stock market", "shutdown", "polls", "caucus", "verdict")
EVERGREEN = ("how to", "how ", "why ", "what is", "what are", "guide", "explained", "lessons", "framework",
             "strategy", "mindset", "habits", "mistakes", "ways to", "secrets", "playbook", "science of", "rules")


def score_fond(ep):
    """Plus c'est haut, plus l'episode est intemporel. Interview avec un invite : bonus. Actualite : malus."""
    t = (ep.get("title") or "").lower()
    pts = sum(2 for k in EVERGREEN if k in t)
    pts += 1 if " with " in t or " w/ " in t else 0
    pts -= sum(3 for k in NEWS if k in t)
    minutes = ep.get("minutes") or 60
    if minutes < 15 or minutes > 110:
        pts -= 1
    return pts


def choisir_episode(todo, fenetre=12):
    """Parmi les 12 episodes non traites les plus recents, prend le plus « de fond » (a egalite : le plus recent)."""
    cand = todo[:fenetre]
    return max(cand, key=lambda e: (score_fond(e), -cand.index(e)))


def main():
    config = mq.load_json(CONFIG_FILE, {})
    if config.get("pause"):
        log("pause=true — aucun traitement.")
        return
    niveaux = set(config.get("niveaux") or ["A"])
    exclure = set(config.get("exclure") or [])
    corriges = config.get("flux_corriges") or {}
    levels = mq.load_json(PRIORITE_FILE, {}).get("niveaux", {})
    podcasts = {p["slug"]: p for p in mq.load_json(mq.PODCASTS_FILE, []) if p.get("slug")}
    cibles = [s for s, n in levels.items() if n in niveaux and s not in exclure and s in podcasts]

    queue = mq.load_json(QUEUE_FILE, {"podcasts": {}, "journal": {}})
    queue.setdefault("podcasts", {}); queue.setdefault("journal", {})
    for s in cibles:
        queue["podcasts"].setdefault(s, {"episodes_done": [], "moments_count": 0, "last_error": "",
                                         "podcast_name": podcasts[s].get("podcast_name", "")})
    journal = queue["journal"].setdefault(TODAY, {"episodes": 0, "minutes": 0, "moments": 0})
    for d in sorted(queue["journal"])[:-30]:
        del queue["journal"][d]

    eps_jour = int(os.environ.get("EPISODES_PAR_JOUR") or config.get("episodes_par_jour", 20))
    eps_podcast = int(config.get("episodes_par_podcast_par_jour", 3))
    minutes_max = int(config.get("minutes_audio_max_jour", 2400))
    run_max = int(config.get("episodes_par_run", eps_jour) or eps_jour)
    if not DRY_RUN:
        mq.set_questions_max(mq.emod(), int(config.get("questions_max_par_episode", 5)))

    log(f"{len(cibles)} podcast(s) connus. Budget : {journal['episodes']}/{eps_jour} episodes, "
        f"{journal['minutes']}/{minutes_max} min deja consommes aujourd'hui.")

    # Tour de role : les podcasts les moins exploites d'abord, 3 episodes max par podcast et par jour.
    order = sorted(cibles, key=lambda s: (len(queue["podcasts"][s]["episodes_done"]), s))
    done_today = {s: 0 for s in cibles}
    run_start = journal["episodes"]
    progress = True
    while progress and journal["episodes"] < eps_jour and journal["minutes"] < minutes_max \
            and journal["episodes"] - run_start < run_max:
        progress = False
        for slug in order:
            if journal["episodes"] >= eps_jour or journal["minutes"] >= minutes_max \
                    or journal["episodes"] - run_start >= run_max:
                break
            if done_today[slug] >= eps_podcast:
                continue
            state, podcast = queue["podcasts"][slug], podcasts[slug]
            url = corriges.get(slug) or podcast.get("rss_url", "")
            if not url:
                state["last_error"] = "pas de flux RSS"
                continue
            try:
                episodes, _email = mq.read_rss(url)
            except Exception as e:
                state["last_error"] = f"RSS illisible : {e}"[:200]
                log(f"ERREUR RSS {slug} ({e})")
                continue
            skip = set(state["episodes_done"]) | mq.already_mined_guids(slug)
            todo = [e for e in episodes if e.get("audio_url") and e["guid"] not in skip]
            if not todo:
                continue
            ep = choisir_episode(todo) if config.get('filtre_fond', True) else todo[0]
            if journal["minutes"] + ep["minutes"] > minutes_max and journal["episodes"] > run_start:
                continue
            log(f"{slug} : {ep['title'][:80]} ({ep['minutes']} min)")
            n = 0
            if not DRY_RUN:
                try:
                    n = mq.extract_episode(podcast, ep)
                    state["last_error"] = ""
                except Exception as e:
                    state["last_error"] = str(e)[:200]
                    log(f"ECHEC extraction ({e}) — episode marque traite pour ne pas boucler.")
            state["episodes_done"].append(ep["guid"])
            state["moments_count"] += n
            state["last_extract_date"] = TODAY
            done_today[slug] += 1
            journal["episodes"] += 1; journal["minutes"] += ep["minutes"]; journal["moments"] += n
            progress = True
            log(f"  -> {n} Q/R ajoutee(s).")

    if DRY_RUN:
        log(f"DRY_RUN : {journal['episodes'] - run_start} episode(s) auraient ete traites. Rien ecrit.")
        return
    mq.save_json(QUEUE_FILE, queue)
    log(f"Termine. Aujourd'hui : {journal['episodes']} episodes, {journal['minutes']} min, {journal['moments']} Q/R.")


if __name__ == "__main__":
    main()

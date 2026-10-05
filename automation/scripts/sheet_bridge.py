#!/usr/bin/env python3
"""
Pont GitHub <-> Google Sheet de prospection (MarketForge Engine).

  python sheet_bridge.py pull   : lit les reglages MFE_* de l'onglet Reglages -> config.json
  python sheet_bridge.py push   : envoie le compte-rendu du run (onboarding + file + journal) au Sheet
  python sheet_bridge.py stats  : lit le suivi prospection (envois, relances, reponses, rebonds) ->
                                  automation/marketforge_engine/prospection_stats.json (chiffres agreges
                                  uniquement, jamais d'email : le depot est public) -> tableau de bord

Secret GitHub : MFE_SHEET_URL = URL de l'application web Apps Script, AVEC ?secret=... a la fin.
Sans ce secret, le script ne fait rien (le systeme continue avec config.json).
"""
import os, sys, json, datetime, urllib.request, urllib.parse

URL = os.environ.get("MFE_SHEET_URL", "").strip()
CONFIG_FILE = "automation/marketforge_engine/config.json"
QUEUE_FILE = "automation/marketforge_engine/queue.json"
ONBOARD_FILE = "automation/marketforge_engine/last_onboard.json"

# Cle du Sheet (onglet Reglages) -> cle de config.json
KEYS = {
    "MFE_PAUSE": "pause",
    "MFE_DECOUVERTE_MAX_JOUR": "decouverte_max_par_jour",
    "MFE_ONBOARDING_AUTO": "onboarding_auto",
    "MFE_ONBOARDING_MAX_JOUR": "onboarding_max_par_jour",
    "MFE_EXTRACTION_AUTO": "extraction_auto",
    "MFE_EPISODES_PAR_JOUR": "episodes_par_jour",
    "MFE_EPISODES_PAR_PODCAST": "episodes_par_podcast",
    "MFE_MINUTES_AUDIO_MAX_JOUR": "minutes_audio_max_jour",
    "MFE_EXTRACTION_APRES_JOURS": "extraction_apres_jours",
}


def log(msg):
    print(f"[sheet-bridge] {msg}", flush=True)


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def call(params=None, payload=None):
    url = URL
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:  # suit la redirection googleusercontent
        return json.loads(r.read().decode())


def convert(key, value):
    if key in ("pause", "onboarding_auto", "extraction_auto"):
        return str(value).strip().upper() in ("TRUE", "VRAI", "1", "OUI", "YES")
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def pull():
    res = call({"action": "config"})
    if not res.get("ok"):
        raise RuntimeError(res)
    config = load(CONFIG_FILE, {})
    changed = []
    for sheet_key, cfg_key in KEYS.items():
        if sheet_key in res.get("reglages", {}):
            v = convert(cfg_key, res["reglages"][sheet_key])
            if v is not None and config.get(cfg_key) != v:
                changed.append(f"{cfg_key}: {config.get(cfg_key)} -> {v}")
                config[cfg_key] = v
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")
    log("Reglages du Sheet appliques : " + (", ".join(changed) if changed else "aucun changement"))


STATS_FILE = "automation/marketforge_engine/prospection_stats.json"


def stats():
    res = call({"action": "status"})
    if not res.get("ok"):
        raise RuntimeError(res)
    rows = res.get("prospects", [])
    day = lambda v: str(v or "")[:10] if str(v or "")[:4].isdigit() else ""
    status = {}
    sent_by_day, replies_by_day, followups_by_day, bounces_by_day = {}, {}, {}, {}
    for r in rows:
        st = str(r.get("Statut") or "?")
        status[st] = status.get(st, 0) + 1
        d = day(r.get("Envoye le"))
        if d:
            sent_by_day[d] = sent_by_day.get(d, 0) + 1
            if st == "Rebond":
                bounces_by_day[d] = bounces_by_day.get(d, 0) + 1
        d = day(r.get("Reponse"))
        if d:
            replies_by_day[d] = replies_by_day.get(d, 0) + 1
        d = day(r.get("Relance le"))
        if d:
            followups_by_day[d] = followups_by_day.get(d, 0) + 1
    reg = res.get("reglages", {})
    # Position dans la file d'envoi (ordre du Sheet = ordre reellement suivi par mfeSend_) :
    # sert au tableau de bord pour estimer l'heure d'envoi des prospects "Pret".
    queue_rank, n = {}, 0
    for r in rows:
        if str(r.get("Statut")) == "Pret":
            n += 1
            queue_rank[r.get("Slug")] = n
    # Detail par prospect pour le tableau de bord (JAMAIS l'email ni le thread : le depot est public).
    # Trie par date la plus recente (relance > envoi > ajout) en tete.
    prospect_rows = sorted(rows, key=lambda r: str(r.get("Relance le") or r.get("Envoye le") or r.get("Ajoute le") or ""), reverse=True)
    detail = [
        {
            "slug": r.get("Slug", ""),
            "podcast": r.get("Podcast", ""),
            "statut": r.get("Statut", ""),
            "ajoute_le": r.get("Ajoute le", ""),
            "envoye_le": r.get("Envoye le", ""),
            "relance_le": r.get("Relance le", ""),
            "reponse": r.get("Reponse", ""),
            "fiche_url": r.get("Preuve (fiche N1)") or r.get("Page Listenly") or "",
            "queue_rank": queue_rank.get(r.get("Slug")),
            "variante": r.get("Variante CTA", ""),
        }
        for r in prospect_rows[:300]
    ]
    out = {
        "updated": datetime.datetime.utcnow().isoformat(timespec="minutes"),
        "total": len(rows),
        "status": status,
        "sent_total": sum(sent_by_day.values()),
        "replies_total": sum(replies_by_day.values()),
        "followups_total": sum(followups_by_day.values()),
        "sent_by_day": dict(sorted(sent_by_day.items())[-60:]),
        "replies_by_day": dict(sorted(replies_by_day.items())[-60:]),
        "followups_by_day": dict(sorted(followups_by_day.items())[-60:]),
        "bounces_by_day": dict(sorted(bounces_by_day.items())[-60:]),
        "envoi_auto": str(reg.get("MFE_ENVOI_AUTO", "")).upper() == "TRUE",
        "max_envois_jour": reg.get("MFE_MAX_ENVOIS_JOUR", ""),
        "heures_envoi": reg.get("MFE_HEURES_ENVOI", ""),
        "cap_jour_effectif": res.get("cap_jour_effectif"),
        "envoyes_aujourdhui": res.get("envoyes_aujourdhui"),
        "prospects": detail,
    }
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"::notice title=Prospection::{out['sent_total']} envoye(s), {out['replies_total']} reponse(s), {out['total']} prospect(s) dans le Sheet")
    log(f"Suivi prospection : {out['sent_total']} envoye(s), {out['replies_total']} reponse(s), statuts {status}")


def push():
    queue = load(QUEUE_FILE, {"podcasts": {}, "journal": {}})
    onboard = load(ONBOARD_FILE, {"onboarded": [], "failed_issues": []})
    today = datetime.date.today().isoformat()
    journal = queue.get("journal", {}).get(today, {"episodes": 0, "minutes": 0, "moments": 0})
    try:   # preuve du mail : une vraie question + son moment exact (lien https://listenly.fr/?p=<slug>&m=<id>)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import moments_index
    except Exception as e:   # jamais bloquant : sans preuve, le mail part avec le lien general
        moments_index = None
        log(f"(moments_index indisponible : {e})")

    def proof(slug, p):
        if not moments_index or not p.get("moments_count"):
            return "", ""
        try:
            moments_index.invalidate(slug)
            q, mid = moments_index.best_proof(slug) or ("", "")
            return q, mid
        except Exception as e:
            log(f"(preuve {slug} : {e})")
            return "", ""

    podcasts = []
    for s, p in queue.get("podcasts", {}).items():
        q, mid = proof(s, p)
        podcasts.append(
            {"slug": s, "podcast_name": p.get("podcast_name", s), "email": p.get("email", ""),
             "status": p.get("status", ""), "moments_count": p.get("moments_count", 0),
             "proof_url": p.get("proof_url", ""), "fiche_url": p.get("fiche_url", ""),
             "host_name": p.get("host_name", ""), "listenly_url": p.get("listenly_url", ""),
             "thematique": p.get("thematique", ""),
             "latest_episode_question": q, "latest_episode_moment_id": mid,
             "last_error": p.get("last_error", "")})
    payload = {
        "action": "report",
        "date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "run_url": f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
                   f"{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}",
        "decouverts": int(os.environ.get("DISCOVERED_COUNT") or 0),
        "onboarded": onboard.get("onboarded", []),
        "onboard_echecs": onboard.get("failed_issues", []),
        "extraction_jour": journal,
        "podcasts": podcasts,
    }
    res = call(payload=payload)
    log(f"Compte-rendu envoye au Sheet : {res}")


def tendances():
    """Envoie le classement des secteurs (targeting.json) vers l'onglet Synthese du Sheet."""
    t = load("automation/marketforge_engine/targeting.json", {})
    if not t.get("ranking"):
        log("targeting.json vide -- rien a envoyer.")
        return
    rows = [[r["rang"], r["secteur"], r.get("poids_pct"), r.get("delta_pts", 0), r.get("tendance", ""),
             r.get("onboarde", 0), r.get("joignable", 0), r.get("envoye", 0), r.get("rebond", 0),
             r.get("reponse", 0), r.get("taux_reponse")] for r in t["ranking"]]
    ab = load("automation/marketforge_engine/ab_test.json", {})
    ab_rows = [[k, d.get("label", ""), d.get("envoye", 0), d.get("rebond", 0), d.get("reponse", 0),
                d.get("taux_pct") if d.get("taux_pct") is not None else "", d.get("chance_meilleure_pct", 0),
                d.get("part_envois_pct", 0)] for k, d in (ab.get("variants") or {}).items()]
    res = call(payload={"action": "tendances", "updated": t.get("updated", ""),
                        "envois_total": t.get("envois_total", 0), "reponses_total": t.get("reponses_total", 0),
                        "rows": rows,
                        "ab": {"rows": ab_rows, "verdict": ab.get("verdict", ""), "updated": ab.get("updated", "")} if ab_rows else None})
    log(f"Classement des tendances envoye a la Synthese : {res}")


def optimisations():
    """Envoie le journal des optimisations (optimisations.json) vers l'onglet 'Optimisations' du Sheet."""
    j = load("automation/marketforge_engine/optimisations.json", {})
    items = j.get("items", [])
    if not items:
        log("optimisations.json vide -- rien a envoyer.")
        return
    try:
        if int(call({"action": "status"}).get("script_version", 0)) < 12:
            log("Script Apps Script a recoller (colonne Version du journal) : journal des optimisations non envoye pour ne rien ecraser.")
            return
    except Exception as e:
        log(f"Version du script Apps Script illisible ({e}) : journal non envoye.")
        return
    label = {"valide": "\u2705 Valid\u00e9", "en_cours": "\u26a0\ufe0f En cours", "a_faire": "\u274c Pas encore fait"}
    rows = []
    for sec in j.get("sections", []):
        rows.append({"section": sec})
        for it in items:
            if it.get("section") == sec:
                rows.append({"version": it.get("version", "\u2014"), "texte": it["texte"], "date": it.get("date", "\u2014"),
                             "statut": label.get(it.get("statut"), label["a_faire"])})
    res = call(payload={"action": "optimisations", "updated": datetime.date.today().strftime("%d/%m/%Y"), "rows": rows})
    log(f"Journal des optimisations envoye au Sheet : {res}")


if __name__ == "__main__":
    if not URL:
        log("MFE_SHEET_URL absent — pont Sheet desactive, rien a faire.")
        sys.exit(0)
    try:
        {"pull": pull, "push": push, "stats": stats, "tendances": tendances, "optimisations": optimisations}[sys.argv[1]]()
    except Exception as e:  # ne bloque jamais le run
        log(f"AVERTISSEMENT : pont Sheet en echec ({e})")
        print(f"::warning title=Pont Sheet ({sys.argv[1]})::{str(e)[:300]}")

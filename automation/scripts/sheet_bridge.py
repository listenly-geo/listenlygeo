#!/usr/bin/env python3
"""
Pont GitHub <-> Google Sheet de prospection (MarketForge Engine).

  python sheet_bridge.py pull   : lit les reglages MFE_* de l'onglet Reglages -> config.json
  python sheet_bridge.py push   : envoie le compte-rendu du run (onboarding + file + journal) au Sheet

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


def push():
    queue = load(QUEUE_FILE, {"podcasts": {}, "journal": {}})
    onboard = load(ONBOARD_FILE, {"onboarded": [], "failed_issues": []})
    today = datetime.date.today().isoformat()
    journal = queue.get("journal", {}).get(today, {"episodes": 0, "minutes": 0, "moments": 0})
    podcasts = [
        {"slug": s, "podcast_name": p.get("podcast_name", s), "email": p.get("email", ""),
         "status": p.get("status", ""), "moments_count": p.get("moments_count", 0),
         "proof_url": p.get("proof_url", ""), "fiche_url": p.get("fiche_url", ""),
         "last_error": p.get("last_error", "")}
        for s, p in queue.get("podcasts", {}).items()
    ]
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


if __name__ == "__main__":
    if not URL:
        log("MFE_SHEET_URL absent — pont Sheet desactive, rien a faire.")
        sys.exit(0)
    try:
        {"pull": pull, "push": push}[sys.argv[1]]()
    except Exception as e:  # ne bloque jamais le run
        log(f"AVERTISSEMENT : pont Sheet en echec ({e})")

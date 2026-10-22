#!/usr/bin/env python3
"""MarketForge Health : un seul contrôle toutes les 2 h.

Lit l'état de chaque étape, écrit automation/marketforge_engine/health.json,
et prend des décisions automatiques SANS jamais :
  - lever la pause ou réactiver l'envoi (décision humaine) ;
  - envoyer un mail à une adresse non vérifiée ou sans dirigeant ;
  - modifier les textes des mails ou les règles de qualité.

Décisions autonomes permises :
  - relancer la découverte si le stock de prêts est sous l'objectif (au plus toutes les 6 h) ;
  - relancer le run du moteur si le stock est sous l'objectif et qu'il n'est pas en pause.
"""
import datetime, json, os, subprocess, sys, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENGINE = os.path.join(ROOT, "automation", "marketforge_engine")
OUT = os.path.join(ENGINE, "health.json")
REPO = os.environ.get("GITHUB_REPOSITORY", "listenly-geo/listenlygeo")
OBJECTIF = 30
COOLDOWN_H = 6


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def gh_api(path):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}{path}",
        headers={"Authorization": f"Bearer {os.environ.get('GH_TOKEN','')}",
                 "Accept": "application/vnd.github+json", "User-Agent": "mf-health"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def last_run(workflow):
    try:
        runs = gh_api(f"/actions/workflows/{workflow}/runs?per_page=1").get("workflow_runs", [])
        if not runs:
            return {"conclusion": "aucun", "at": ""}
        r = runs[0]
        return {"conclusion": r.get("conclusion") or r.get("status"), "at": r.get("created_at", "")}
    except Exception as e:
        return {"conclusion": f"erreur API ({e})"[:120], "at": ""}


def dispatch(workflow):
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow}/dispatches",
            data=json.dumps({"ref": "main"}).encode(), method="POST",
            headers={"Authorization": f"Bearer {os.environ.get('GH_TOKEN','')}",
                     "Accept": "application/vnd.github+json", "User-Agent": "mf-health",
                     "Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30)
        return True
    except Exception as e:
        print(f"[health] relance impossible ({workflow}) : {e}")
        return False


def lire_pause():
    """Pause lue dans le Sheet (MFE_PAUSE). Si la lecture échoue, on considère le système EN PAUSE (sécurité)."""
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        import sheet_bridge
        reg = (sheet_bridge.call({"action": "status"}) or {}).get("reglages", {}) or {}
        return str(reg.get("MFE_PAUSE", "TRUE")).upper() != "FALSE"
    except Exception as e:
        print(f"[health] pause illisible, on reste en sécurité (pause) : {e}")
        return True


def main():
    now = datetime.datetime.utcnow()
    stats = load(os.path.join(ENGINE, "prospection_stats.json"), {})
    status = stats.get("status", {}) or {}
    pret = int(status.get("Pret", 0) or 0)
    pause = lire_pause()
    last_onboard = load(os.path.join(ENGINE, "last_onboard.json"), {})

    checks = {
        "deploiement_pont": last_run("apps-script-deploy.yml"),
        "moteur": last_run("marketforge-engine-run.yml"),
        "decouverte": last_run("discover-podcasts.yml"),
        "tableau_de_bord": last_run("refresh-dashboard.yml"),
    }
    deploy_ok = str(checks["deploiement_pont"]["conclusion"]) == "success"

    stock = {"prets": pret, "objectif": OBJECTIF, "sous_objectif": pret < OBJECTIF,
             "risque_ou_sans_dirigeant": status.get("Email risque", 0) + status.get("En pause (pas de dirigeant)", 0),
             "onboardes_dernier_run": len(last_onboard.get("onboarded", []))}

    decisions, alertes = [], []
    if not deploy_ok:
        alertes.append("Pont d'envoi en échec : reconnexion clasp nécessaire (action humaine).")
    if pause:
        decisions.append("Système en pause : aucune relance automatique, décision humaine requise pour reprendre.")
    elif stock["sous_objectif"]:
        prev = load(OUT, {}).get("decisions", [])
        recent = [d for d in prev if "découverte" in d.get("action", "") and
                  (now - datetime.datetime.fromisoformat(d["quand"])).total_seconds() < COOLDOWN_H * 3600]
        if recent:
            decisions.append("Découverte déjà relancée il y a moins de 6 h : pas de nouvelle relance.")
        elif dispatch("discover-podcasts.yml"):
            decisions.append({"action": "relance découverte", "quand": now.isoformat(timespec="minutes")})
    if stock["sous_objectif"]:
        alertes.append(f"Stock de prospects prêts : {pret} sur {OBJECTIF}.")
    if stock["risque_ou_sans_dirigeant"]:
        alertes.append(f"{stock['risque_ou_sans_dirigeant']} prospects à risque ou sans dirigeant (à traiter).")

    result = {"maj": now.isoformat(timespec="minutes"), "etapes": checks, "stock": stock,
              "decisions": [d if isinstance(d, dict) else {"action": d, "quand": now.isoformat(timespec="minutes")} for d in decisions],
              "alertes": alertes}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main() or 0)

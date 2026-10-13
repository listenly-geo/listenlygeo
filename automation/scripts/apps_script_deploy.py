#!/usr/bin/env python3
"""
Deploiement de MarketForgeEngine.gs dans l'Apps Script lie au Sheet (01/10/2026).

Utilise la connexion clasp d'Etienne (secret CLASPRC_JSON) via l'API Apps Script (les comptes de service sont refuses : HTTP 403).
Prerequis : ID du script dans automation/apps-script/script_id.txt.

Mode DRY (defaut) : lit le projet, sauvegarde l'existant dans automation/apps-script/backup/, compare, n'ecrit rien.
Mode DEPLOY (env APPS_SCRIPT_MODE=deploy) : remplace le fichier de code, conserve appsscript.json et les autres fichiers.
"""
import os, sys, json, hashlib, datetime
import requests
from google.oauth2.credentials import Credentials as UserCreds
from google.auth.transport.requests import Request

BASE = "automation/apps-script"
SRC = f"{BASE}/MarketForgeEngine.gs"
SCOPES = ["https://www.googleapis.com/auth/script.projects", "https://www.googleapis.com/auth/script.deployments"]


def get_creds():
    """Connexion clasp d'Etienne (secret CLASPRC_JSON) : acces utilisateur, le seul que l'API Apps Script accepte."""
    raw = os.environ.get("CLASPRC_JSON", "").strip()
    if not raw:
        print("::error title=Apps Script::secret CLASPRC_JSON absent")
        sys.exit(1)
    rc = json.loads(raw)
    tok = (rc.get("tokens") or {}).get("default") or {}
    if tok.get("refresh_token"):
        cid, sec, rt = tok["client_id"], tok["client_secret"], tok["refresh_token"]
    else:  # ancien format de clasp
        t0 = rc.get("token") or {}
        o = rc.get("oauth2ClientSettings") or {}
        cid, sec, rt = o.get("clientId"), o.get("clientSecret"), t0.get("refresh_token")
    if not (cid and sec and rt):
        print("::error title=Apps Script::format CLASPRC_JSON inattendu (client/refresh_token manquants)")
        sys.exit(1)
    creds = UserCreds(None, refresh_token=rt, token_uri="https://oauth2.googleapis.com/token", client_id=cid, client_secret=sec)
    creds.refresh(Request())
    return creds


def publier(sid, H, note=""):
    """Cree une nouvelle version du projet et la branche sur le deploiement de l'application web (l'URL du pont ne change pas)."""
    base = f"https://script.googleapis.com/v1/projects/{sid}"
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    rv = requests.post(f"{base}/versions", headers={**H, "Content-Type": "application/json"},
                       data=json.dumps({"description": f"Auto {stamp} {note}".strip()}), timeout=60)
    if rv.status_code != 200:
        print(f"::error title=Apps Script::creation de version impossible HTTP {rv.status_code}: {rv.text[:300]}")
        sys.exit(1)
    num = rv.json().get("versionNumber")
    rd = requests.get(f"{base}/deployments", headers=H, timeout=60)
    if rd.status_code != 200:
        print(f"::error title=Apps Script::lecture des deploiements impossible HTTP {rd.status_code}: {rd.text[:300]}")
        sys.exit(1)
    cibles = [d for d in rd.json().get("deployments", [])
              if any(e.get("entryPointType") == "WEB_APP" for e in d.get("entryPoints", []))
              and d.get("deploymentConfig", {}).get("versionNumber")]
    if len(cibles) != 1:
        print(f"::error title=Apps Script::{len(cibles)} deploiement(s) web trouves (1 attendu), version {num} creee mais non branchee")
        sys.exit(1)
    d = cibles[0]
    cfg = {"versionNumber": num, "manifestFileName": "appsscript", "description": f"Auto {stamp}"}
    ru = requests.put(f"{base}/deployments/{d['deploymentId']}", headers={**H, "Content-Type": "application/json"},
                      data=json.dumps({"deploymentConfig": cfg}), timeout=60)
    if ru.status_code != 200:
        print(f"::error title=Apps Script::mise a jour du deploiement impossible HTTP {ru.status_code}: {ru.text[:300]}")
        sys.exit(1)
    print(f"::notice title=Apps Script::deploiement web passe a la version {num} (publie)")


def main():
    sid = open(f"{BASE}/script_id.txt").read().strip()
    creds = get_creds()
    H = {"Authorization": f"Bearer {creds.token}"}
    url = f"https://script.googleapis.com/v1/projects/{sid}/content"
    r = requests.get(url, headers=H, timeout=60)
    if r.status_code != 200:
        print(f"::error title=Apps Script::lecture impossible HTTP {r.status_code}: {r.text[:300]}")
        sys.exit(1)
    content = r.json()
    files = content.get("files", [])
    print("[apps-script] fichiers:", [(f["name"], f["type"], len(f.get("source", ""))) for f in files])

    os.makedirs(f"{BASE}/backup", exist_ok=True)
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M")
    with open(f"{BASE}/backup/projet-{stamp}.json", "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=1)

    new_src = open(SRC, encoding="utf-8").read()
    code = [f for f in files if f["type"] == "SERVER_JS"]
    same = len(code) == 1 and code[0].get("source", "") == new_src
    print(f"[apps-script] {len(code)} fichier(s) de code ; identique au depot: {same}")
    print(f"::notice title=Apps Script::lecture OK, {len(files)} fichiers, identique={same}")

    mode = os.environ.get("APPS_SCRIPT_MODE")
    if mode not in ("deploy", "publish"):
        print("[apps-script] mode DRY : rien d'ecrit")
        return
    if mode == "publish" and same:   # code deja en place : on republie seulement une nouvelle version (test ou retablissement)
        publier(sid, H, "(republication)")
        return
    if same:
        print("[apps-script] deja a jour")
        return
    if len(code) != 1:
        print("::error title=Apps Script::plusieurs fichiers de code, deploiement annule")
        sys.exit(1)
    code[0]["source"] = new_src
    w = requests.put(url, headers={**H, "Content-Type": "application/json"}, data=json.dumps({"files": files}), timeout=60)
    if w.status_code != 200:
        print(f"::error title=Apps Script::ecriture impossible HTTP {w.status_code}: {w.text[:300]}")
        sys.exit(1)
    print(f"::notice title=Apps Script::script mis a jour ({hashlib.sha1(new_src.encode()).hexdigest()[:8]})")
    if mode in ("deploy", "publish"):
        publier(sid, H)   # nouvelle version + branchement sur l'application web : plus aucune action manuelle


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # message clair dans le journal des erreurs
        print(f"::error title=Apps Script::{type(e).__name__}: {str(e)[:300]}")
        sys.exit(1)

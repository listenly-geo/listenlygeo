#!/usr/bin/env python3
"""
Deploiement de MarketForgeEngine.gs dans l'Apps Script lie au Sheet (01/10/2026).

Utilise le compte de service (secret GSC_SERVICE_ACCOUNT_JSON) via l'API Apps Script.
Prerequis cote Etienne : Sheet partage au compte de service (Editeur) + API Apps Script activee dans le projet Cloud
+ ID du script dans automation/apps-script/script_id.txt.

Mode DRY (defaut) : lit le projet, sauvegarde l'existant dans automation/apps-script/backup/, compare, n'ecrit rien.
Mode DEPLOY (env APPS_SCRIPT_MODE=deploy) : remplace le fichier de code, conserve appsscript.json et les autres fichiers.
"""
import os, sys, json, hashlib, datetime
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

BASE = "automation/apps-script"
SRC = f"{BASE}/MarketForgeEngine.gs"
SCOPES = ["https://www.googleapis.com/auth/script.projects"]


def main():
    sid = open(f"{BASE}/script_id.txt").read().strip()
    info = json.loads(os.environ["SA_JSON"])
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    creds.refresh(Request())
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

    if os.environ.get("APPS_SCRIPT_MODE") != "deploy":
        print("[apps-script] mode DRY : rien d'ecrit")
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


if __name__ == "__main__":
    main()

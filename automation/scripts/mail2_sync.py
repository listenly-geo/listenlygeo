#!/usr/bin/env python3
"""Mail 2 (Done + CTA) : enregistre la destination du prospect, puis envoie le mail 2
seulement quand : lien recu, 20 minutes ecoulees, et VALIDE ecrit en colonne S par Etienne.
Etape 1 : le lien du prospect est ecrit dans automation/marketforge_engine/redirections.json (commit).
Etape 2 : pour les prospects deja enregistres depuis un passage precedent, le mail 2 part s'il est VALIDE."""
import json, os, subprocess, sys
sys.path.insert(0, "automation/scripts")
import sheet_bridge

REDIR = "automation/marketforge_engine/redirections.json"

def lire():
    return json.load(open(REDIR, encoding="utf-8")) if os.path.exists(REDIR) else {}

def main():
    avant = lire()
    res = sheet_bridge.call(payload={"action": "cmd", "cmd": "mail2_check"})
    prospects = res.get("prospects", [])
    print(f"mail2 : {len(prospects)} prospect(s) « Lien recu »")
    # Etape 2 : envoi automatique DESACTIVE pour l'instant (validation du tunnel complet en cours).
    # Le mail 2 n'est envoye qu'apres confirmation explicite d'Etienne dans le chat.
    # Pour reactiver l'envoi automatique : MAIL2_AUTO=true dans l'environnement.
    for p in (prospects if os.environ.get("MAIL2_AUTO", "").lower() == "true" else []):
        if p["slug"] in avant and avant[p["slug"]] == p["lien"] and p["validation"].strip().upper() == "VALIDE" and p["minutes_depuis_reponse"] >= 20:
            r = sheet_bridge.call(payload={"action": "cmd", "cmd": "mail2_send", "slug": p["slug"]})
            print(f"::notice title=Mail 2::{p['slug']} -> {json.dumps(r, ensure_ascii=False)[:200]}")
    # Etape 1 : enregistrer les nouvelles destinations
    for p in prospects:
        lien = p.get("lien", "")
        if lien.startswith("https://") and avant.get(p["slug"]) != lien:
            subprocess.run([sys.executable, "automation/scripts/redirection.py", "set", p["slug"], lien], check=True, stdout=subprocess.DEVNULL)
            print(f"::notice title=Destination::{p['slug']} -> enregistree")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"::error title=Mail 2::{type(e).__name__}: {str(e)[:300]}")
        sys.exit(1)

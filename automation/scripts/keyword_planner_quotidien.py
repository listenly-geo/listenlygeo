#!/usr/bin/env python3
"""
Volumes Google Ads (Keyword Planner) pour toutes les questions de moment, chaque jour (17/10/2026).

Lit les questions de pages/podcast-btb/data/moments/*.json, interroge Google Ads par lots de 20,
et ecrit pages/podcast-btb/data/keyword_planner.json (lu par moteur_autonome_moments.py).
Ne publie rien. Sans secrets Google Ads, ecrit l'etat « non connecte ».
"""
import os, sys, json, glob, datetime, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import keyword_planner as kp

MOMENTS = "pages/podcast-btb/data/moments"
BATCH = 20


def questions():
    qs = set()
    for f in glob.glob(f"{MOMENTS}/*.json"):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for e in (d.get("entries") or {}).values():
            if isinstance(e, dict) and (e.get("q") or "").strip():
                qs.add(e["q"].strip())
    return sorted(qs)


def main():
    now = datetime.datetime.utcnow().isoformat(timespec="minutes") + "Z"
    missing = kp.secrets_ok()
    if missing:
        kp.write_state({"statut": "non connecte", "manque": missing, "date": now})
        print("Keyword Planner : non connecte. Secrets manquants : " + ", ".join(missing))
        return
    qs = questions()
    token = kp.access_token()
    merged, erreurs, faits = {}, 0, 0
    for i in range(0, len(qs), BATCH):
        lot = qs[i:i + BATCH]
        try:
            for idea in kp.generate_ideas(lot, token):
                k = (idea.get("requete") or "").lower()
                if k and idea["volume_mensuel_moyen"] > merged.get(k, {}).get("volume_mensuel_moyen", -1):
                    merged[k] = idea
            faits += 1
        except urllib.error.HTTPError as e:
            erreurs += 1
            if e.code in (429, 403):   # quota ou acces refuse : on arrete pour aujourd'hui
                print(f"Arret au lot {i // BATCH} : erreur {e.code}")
                break
    statut = "connecte" if faits else "erreur"
    kp.write_state({"statut": statut, "date": now, "graines": qs[:faits * BATCH],
                    "lots_reussis": faits, "lots_en_erreur": erreurs,
                    "idees": sorted(merged.values(), key=lambda x: -x["volume_mensuel_moyen"])})
    print(f"Keyword Planner : {len(merged)} idees pour {len(qs)} questions ({faits} lots, {erreurs} erreurs).")


if __name__ == "__main__":
    main()

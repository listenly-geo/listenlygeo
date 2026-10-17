#!/usr/bin/env python3
"""
Volumes Google Ads (Keyword Planner) pour toutes les questions de moment, chaque jour (17/10/2026).

Lit le theme court des fiches qui passent la porte (keyword_themes.json), interroge Google Ads par lots de 20,
et ecrit pages/podcast-btb/data/keyword_planner.json (lu par moteur_autonome_moments.py).
Ne publie rien. Sans secrets Google Ads, ecrit l'etat « non connecte ».
"""
import os, sys, json, datetime, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import keyword_planner as kp

SCORES = "pages/podcast-btb/data/moments_scores.json"
BATCH = 20


THEMES = "pages/podcast-btb/data/keyword_themes.json"
DEMANDE = "pages/podcast-btb/data/demande_par_fiche.json"


def reservoir_themes():
    """Theme court de chaque fiche du reservoir (porte passee), tel que ecrit dans keyword_themes.json."""
    try:
        sc = json.load(open(SCORES, encoding="utf-8"))
        th = json.load(open(THEMES, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    gate = {k for k, v in (sc.get("scores") or sc).items() if isinstance(v, dict) and v.get("gate")}
    return {k: t.strip() for k, t in th.items() if k in gate and isinstance(t, str) and t.strip()}


def questions():
    """Methode du 17/10/2026 : on interroge Google avec le theme court de chaque fiche du reservoir."""
    return sorted(set(reservoir_themes().values()))


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
    if faits:   # volume par fiche = volume du theme (correspondance exacte)
        par_theme = {(i.get("requete") or "").lower(): i["volume_mensuel_moyen"] for i in merged.values()}
        fiches = {k: {"theme": t, "volume": par_theme.get(t.lower(), 0)} for k, t in reservoir_themes().items()}
        json.dump({"date": now, "fiches": fiches}, open(DEMANDE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    kp.write_state({"statut": statut, "date": now, "graines": qs[:faits * BATCH],
                    "lots_reussis": faits, "lots_en_erreur": erreurs,
                    "idees": sorted(merged.values(), key=lambda x: -x["volume_mensuel_moyen"])})
    print(f"Keyword Planner : {len(merged)} idees pour {len(qs)} questions ({faits} lots, {erreurs} erreurs).")


if __name__ == "__main__":
    main()

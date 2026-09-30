#!/usr/bin/env python3
"""
Optimiseur du test A/B du CTA (30/09/2026).

Chaque premier mail recoit une variante de CTA (A, B, C) ; Apps Script note la variante dans la colonne
"Variante CTA" du Sheet. Ce script mesure, par variante, le taux de VRAIES reponses (hors rebonds et
hors reponses automatiques) et en deduit :
  - la probabilite que chaque variante soit la meilleure (statistique bayesienne, Beta)
  - la repartition des prochains envois : egale tant que chaque variante n'a pas MIN_ENVOIS envois,
    ensuite proportionnelle aux chances, avec un plancher pour continuer d'explorer
  - un verdict : "gagnant" seulement avec assez d'envois ET >= 95 % de chances, sinon "trop tot"

Sortie : automation/marketforge_engine/ab_test.json (lu par Apps Script pour repartir les envois,
et envoye dans la Synthese du Sheet). Aucune cle API, aucun appel reseau.
"""
import os, sys, json, random, datetime

STATS = "automation/marketforge_engine/prospection_stats.json"
CONFIG = "automation/marketforge_engine/config.json"
OUT = "automation/marketforge_engine/ab_test.json"

LABELS = {
    "A": "Video audit de 2 minutes (CTA retenu)",
    # Pour retester d'autres CTA : ajouter ici "B": "...", puis remplir MFE_CTA_B dans l'onglet Reglages du Sheet.
}
MIN_ENVOIS = 30        # envois par variante avant d'adapter la repartition
MIN_VERDICT = 100      # envois par variante avant de declarer un gagnant
PROBA_GAGNANT = 0.95
FLOOR = 0.15           # part minimale d'une variante (exploration)
PRIOR_A, PRIOR_B = 1.0, 30.0   # a priori Beta : ~3 % de reponses
DRAWS = 20000


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def main():
    stats = load(STATS, {})
    ignored = set(load(CONFIG, {}).get("reponses_automatiques_ignorees", []))
    v = {k: {"envoye": 0, "rebond": 0, "reponse": 0} for k in LABELS}
    for p in stats.get("prospects", []):
        k = str(p.get("variante") or "").strip()
        if k not in v or not p.get("envoye_le"):
            continue
        v[k]["envoye"] += 1
        if p.get("statut") == "Rebond":
            v[k]["rebond"] += 1
        if p.get("statut") == "Repondu" and p.get("slug") not in ignored:
            v[k]["reponse"] += 1

    keys = list(v)
    for k in keys:
        d = v[k]
        d["delivres"] = max(d["envoye"] - d["rebond"], 0)
        d["taux_pct"] = round(100.0 * d["reponse"] / d["delivres"], 1) if d["delivres"] else None

    rnd = random.Random(42)
    wins = {k: 0 for k in keys}
    for _ in range(DRAWS):
        draw = {k: rnd.betavariate(PRIOR_A + v[k]["reponse"],
                                   PRIOR_B + max(v[k]["delivres"] - v[k]["reponse"], 0)) for k in keys}
        wins[max(draw, key=draw.get)] += 1
    p_best = {k: wins[k] / DRAWS for k in keys}

    if min(v[k]["envoye"] for k in keys) < MIN_ENVOIS:
        weights = {k: round(1.0 / len(keys), 4) for k in keys}
        phase = "exploration (repartition egale)"
    else:
        spread = 1.0 - FLOOR * len(keys)
        weights = {k: round(FLOOR + spread * p_best[k], 4) for k in keys}
        phase = "adaptation (plus d'envois pour les meilleures variantes)"

    best = max(keys, key=lambda k: p_best[k])
    if len(keys) == 1:
        verdict = f"un seul CTA actif ({LABELS[keys[0]]}) : aucune comparaison en cours"
    elif min(v[k]["envoye"] for k in keys) >= MIN_VERDICT and p_best[best] >= PROBA_GAGNANT:
        verdict = f"gagnant : variante {best} ({LABELS[best]})"
    else:
        total = sum(v[k]["envoye"] for k in keys)
        verdict = (f"trop tot pour conclure ({total} envois avec variante ; il en faut au moins "
                   f"{MIN_VERDICT} par variante et 95 % de chances)")

    out = {"updated": datetime.datetime.utcnow().isoformat(timespec="minutes"),
           "phase": phase, "verdict": verdict, "weights": weights,
           "variants": {k: {"label": LABELS[k], **v[k], "chance_meilleure_pct": round(100 * p_best[k], 1),
                            "part_envois_pct": round(100 * weights[k], 1)} for k in keys}}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for k in keys:
        d = out["variants"][k]
        print(f"[ab] {k}: {d['envoye']} env., {d['rebond']} rebonds, {d['reponse']} rep. "
              f"({d['taux_pct']}%), chance meilleure {d['chance_meilleure_pct']}%, part {d['part_envois_pct']}%")
    print(f"[ab] {phase} | {verdict}")
    print(f"::notice title=Test A/B CTA::{verdict}")


if __name__ == "__main__":
    sys.exit(main())

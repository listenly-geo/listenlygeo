#!/usr/bin/env python3
"""
Optimiseur de ciblage du MarketForge Engine (30/09/2026).

Boucle d'apprentissage : lit les RESULTATS reels de la prospection (par secteur) et en deduit
des poids de ciblage que la decouverte utilise pour repartir son budget de qualification.
  - secteurs qui donnent des emails joignables ET des reponses  -> poids en hausse
  - secteurs qui rebondissent / ne repondent pas               -> poids en baisse
  - plancher d'exploration : aucun secteur n'est jamais coupe a 0 (on continue d'echantillonner)

Sorties :
  automation/marketforge_engine/targeting.json          poids + classement (lu par discover_podcasts.py)
  automation/marketforge_engine/targeting_history.json  photo des poids par jour (pour la tendance)

Aucune dependance reseau ni cle API : lit uniquement les fichiers du depot.
Score d'un secteur (08/10/2026) = taux de DIRIGEANTS JOIGNABLES trouves (filtre d'entree, lisse) x taux de reponse lisse x (1 - taux de rebond lisse).
Le taux de dirigeants joignables est le signal rapide (des dizaines de tests par jour) ; le taux de reponse prend le relais quand les envois s'accumulent.
Les reponses AUTOMATIQUES (absence, accuse de reception) ne comptent pas : voir
config.json > reponses_automatiques_ignorees.
"""

import os, re, sys, json, datetime, unicodedata

STATS = "automation/marketforge_engine/prospection_stats.json"
QUEUE = "automation/marketforge_engine/queue.json"
CONFIG = "automation/marketforge_engine/config.json"
PODCASTS = "pages/podcast-btb/data/podcasts.json"
SEEN = "automation/data/discovery_seen_history.json"
GROUPS = "automation/data/discovery_keyword_groups.json"
OUT = "automation/marketforge_engine/targeting.json"
HISTORY = "automation/marketforge_engine/targeting_history.json"
GATE = "automation/marketforge_engine/gate_state.json"   # filtre dirigeant : podcasts testes / dirigeants joignables trouves, par secteur

# Podcasts deja onboardes avant le ciblage par secteur : on reutilise leur categorie N1.
LEGACY_SECTOR = {
    "Finance & Patrimoine": "Finance & Fintech",
    "Immobilier": "Immobilier",
    "RH & Management": "RH & Recrutement",
    "Marketing & Communication": "Marketing & Ventes",
    "Tech & Cybersécurité": "Cybersécurité",
    "Cybersécurité": "Cybersécurité",
    "Santé & Pharma": "Santé",
    "Droit & Juridique": "Juridique",
    "Business & Entrepreneuriat": "Business général (entreprise)",
}
OTHER = "Autre"

PRIOR_REPLY_RATE = 0.02   # a priori : 2 % de reponses en prospection a froid
PRIOR_STRENGTH = 30       # poids de l'a priori, en nombre d'envois
FLOOR = 0.015             # part minimale de budget par secteur actif (exploration) ; 20 secteurs -> 30 % d exploration, 70 % guides par les resultats
CAP = 0.30                # part maximale d'un seul secteur (diversification)
MIN_SENT_FOR_TREND = 10


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def main():
    stats = load(STATS, {})
    queue = (load(QUEUE, {}) or {}).get("podcasts", {})
    config = load(CONFIG, {})
    podcasts = {p.get("slug"): p for p in load(PODCASTS, []) if isinstance(p, dict)}
    seen = load(SEEN, {})
    groups = load(GROUPS, {})
    ignored = set(config.get("reponses_automatiques_ignorees", []))
    gate_sect = (load(GATE, {}) or {}).get("secteurs", {})
    g_tries = sum(v.get("tries", 0) for v in gate_sect.values())
    g_ok = sum(v.get("ok", 0) for v in gate_sect.values())
    g_rate = (g_ok + 0.25 * 10) / (g_tries + 10)   # a priori : 25 % de podcasts avec dirigeant joignable

    name_to_sector = {}
    for rec in seen.values():
        if isinstance(rec, dict) and rec.get("secteur"):
            name_to_sector[norm(rec.get("podcast_name"))] = rec["secteur"]

    def sector_of(slug):
        q = queue.get(slug, {})
        name = q.get("podcast_name") or (podcasts.get(slug) or {}).get("podcast_name", "")
        if norm(name) in name_to_sector:
            return name_to_sector[norm(name)]
        cat = (podcasts.get(slug) or {}).get("categorie", "")
        return LEGACY_SECTOR.get(cat, OTHER)

    active = list(groups)  # secteurs pour lesquels la decouverte a des mots-cles
    sectors = {}

    def bucket(sec):
        return sectors.setdefault(sec, {"onboarde": 0, "joignable": 0, "envoye": 0,
                                        "rebond": 0, "reponse": 0})

    for slug, q in queue.items():
        b = bucket(sector_of(slug))
        b["onboarde"] += 1
        if q.get("email") and q.get("status_email") != "sans_email":
            b["joignable"] += 1

    for p in stats.get("prospects", []):
        slug = p.get("slug")
        b = bucket(sector_of(slug))
        if p.get("envoye_le"):
            b["envoye"] += 1
        if p.get("statut") == "Rebond":
            b["rebond"] += 1
        if p.get("statut") == "Repondu" and slug not in ignored:
            b["reponse"] += 1

    for sec in active:
        bucket(sec)

    tot_sent = sum(b["envoye"] for b in sectors.values())
    tot_rep = sum(b["reponse"] for b in sectors.values())
    global_rate = (tot_rep + PRIOR_REPLY_RATE * PRIOR_STRENGTH) / (tot_sent + PRIOR_STRENGTH)

    for sec, b in sectors.items():
        gt = gate_sect.get(sec, {})
        b["dirigeant_testes"] = gt.get("tries", 0)
        b["dirigeant_trouves"] = gt.get("ok", 0)
        # taux de dirigeants joignables, lisse vers la moyenne globale (poids 10 tests)
        reach = (b["dirigeant_trouves"] + g_rate * 10) / (b["dirigeant_testes"] + 10)
        reply = (b["reponse"] + global_rate * PRIOR_STRENGTH) / (b["envoye"] + PRIOR_STRENGTH)
        bounce = (b["rebond"] + 0.5) / (b["envoye"] + 5)
        b["taux_reponse"] = round(100.0 * b["reponse"] / b["envoye"], 1) if b["envoye"] else None
        b["score"] = reach * reply * (1 - bounce)

    # Poids = plancher d'exploration + part proportionnelle au score, plafonnee.
    weights = {}
    if active:
        total_score = sum(sectors[s]["score"] for s in active) or 1.0
        spread = 1.0 - FLOOR * len(active)
        weights = {s: FLOOR + spread * sectors[s]["score"] / total_score for s in active}
        for _ in range(3):  # plafond + redistribution du surplus
            over = {s: w - CAP for s, w in weights.items() if w > CAP}
            if not over:
                break
            room = [s for s in weights if s not in over]
            for s in over:
                weights[s] = CAP
            for s in room:
                weights[s] += sum(over.values()) / len(room)
        norm_total = sum(weights.values())
        weights = {s: round(w / norm_total, 4) for s, w in weights.items()}

    today = datetime.date.today().isoformat()
    history = load(HISTORY, [])
    previous = next((h for h in reversed(history) if h.get("date") != today), None)

    ranking = []
    for sec, b in sectors.items():
        w = weights.get(sec)
        delta = (w - previous["weights"].get(sec, w)) if (w is not None and previous) else 0.0
        if b["envoye"] < MIN_SENT_FOR_TREND and b.get("dirigeant_testes", 0) < MIN_SENT_FOR_TREND:
            trend = "provisoire"
        else:
            trend = "hausse" if delta >= 0.01 else "baisse" if delta <= -0.01 else "stable"
        ranking.append({"secteur": sec, "poids_pct": round(100 * w, 1) if w is not None else None,
                        "delta_pts": round(100 * delta, 1), "tendance": trend, **b})
    ranking.sort(key=lambda r: (r["poids_pct"] is None, -(r["poids_pct"] or 0), -r["score"]))
    for i, r in enumerate(ranking, 1):
        r["rang"] = i
        r["score"] = round(r["score"], 5)

    out = {"updated": datetime.datetime.utcnow().isoformat(timespec="minutes"),
           "envois_total": tot_sent, "reponses_total": tot_rep,
           "taux_reponse_global_pct": round(100 * tot_rep / tot_sent, 1) if tot_sent else None,
           "dirigeants_testes": g_tries, "dirigeants_trouves": g_ok,
           "weights": weights, "ranking": ranking}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    history = [h for h in history if h.get("date") != today] + [{"date": today, "weights": weights}]
    with open(HISTORY, "w", encoding="utf-8") as f:
        json.dump(history[-60:], f, ensure_ascii=False)

    print(f"[ciblage] {tot_sent} envois, {tot_rep} reponse(s) reelle(s), {len(active)} secteurs actifs")
    for r in ranking[:8]:
        print(f"[ciblage] #{r['rang']} {r['secteur']}: poids {r['poids_pct']}% | "
              f"{r['envoye']} env., {r['reponse']} rep., {r['rebond']} rebonds, "
              f"{r['dirigeant_trouves']}/{r['dirigeant_testes']} dirigeants joignables | {r['tendance']}")
    top = ", ".join(f"{r['secteur']} {r['poids_pct']}%" for r in ranking[:3] if r["poids_pct"] is not None)
    print(f"::notice title=Ciblage::{tot_rep} reponse(s) / {tot_sent} envois | budget : {top}")


if __name__ == "__main__":
    rc = main()
    try:   # reflexion de la machine : blocages + pourquoi pas encore de client (ne casse jamais le run)
        import funnel_diagnostic
        funnel_diagnostic.run()
    except Exception as e:
        print(f"[reflexion] ignoree : {e}")
    sys.exit(rc)

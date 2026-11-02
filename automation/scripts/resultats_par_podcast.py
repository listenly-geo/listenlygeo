#!/usr/bin/env python3
"""Phase 1 du système de résultats : agrège les chiffres Search Console des pages de moment par podcast.
Lit data/gsc/pages.json (chiffres du jour, page x clics/impressions/position) et écrit
data/gsc/resultats_par_podcast.json : clics, impressions, position moyenne, nombre de pages, et une liste
« gagnant / en observation / sans résultat ». AUCUNE décision n'est prise ici : c'est la phase 2 qui s'en servira.
Seuil de confiance : un podcast n'est « gagnant » qu'avec au moins 100 impressions sur la période."""
import json, re, datetime, collections

SEUIL_IMPRESSIONS = 100
MOMENT = re.compile(r"/podcast-btb/m/([^/]+)/")

pages = json.load(open("data/gsc/pages.json", encoding="utf-8"))
agg = collections.defaultdict(lambda: {"clics": 0, "impressions": 0, "pages": 0, "position_ponderee": 0.0, "pages_avec_clic": 0})
for p in pages:
    m = MOMENT.search(p.get("page", ""))
    if not m:
        continue
    slug = m.group(1)
    a = agg[slug]
    a["clics"] += p.get("clics", 0)
    a["impressions"] += p.get("impressions", 0)
    a["pages"] += 1
    a["position_ponderee"] += p.get("position", 0) * p.get("impressions", 0)
    a["pages_avec_clic"] += 1 if p.get("clics", 0) > 0 else 0

sortie = []
for slug, a in agg.items():
    pos = round(a["position_ponderee"] / a["impressions"], 1) if a["impressions"] else None
    if a["clics"] > 0 and a["impressions"] >= SEUIL_IMPRESSIONS:
        statut = "gagnant"
    elif a["clics"] > 0 or a["impressions"] >= SEUIL_IMPRESSIONS:
        statut = "en observation"
    else:
        statut = "sans résultat"
    sortie.append({"podcast": slug, "clics": a["clics"], "impressions": a["impressions"],
                   "pages": a["pages"], "pages_avec_clic": a["pages_avec_clic"],
                   "position_moyenne": pos, "statut": statut})
sortie.sort(key=lambda x: (-x["clics"], -x["impressions"]))

resume = {"date": datetime.date.today().isoformat(),
          "source": "data/gsc/pages.json", "seuil_impressions": SEUIL_IMPRESSIONS,
          "podcasts": len(sortie),
          "gagnants": sum(1 for x in sortie if x["statut"] == "gagnant"),
          "en_observation": sum(1 for x in sortie if x["statut"] == "en observation"),
          "sans_resultat": sum(1 for x in sortie if x["statut"] == "sans résultat"),
          "detail": sortie}
json.dump(resume, open("data/gsc/resultats_par_podcast.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[resultats] {resume['podcasts']} podcasts | gagnants {resume['gagnants']} | observation {resume['en_observation']} | sans résultat {resume['sans_resultat']}")

#!/usr/bin/env python3
"""
Liste ordonnee des fiches N1 a soumettre en priorite a Google (01/10/2026).
Ordre : 1) podcasts de la file deja contactes / en attente / extraits (la preuve du mail doit etre dans Google),
        2) autres N1 anciennes jamais explorees par Google, 3) le reste, les plus anciennes d'abord.
Exclut les N1 deja indexees et les podcasts sans email (aucun mail possible : rang 3).
Ecrit pages/podcast-btb/data/index_priorite.json et .csv (a utiliser dans Search Console : Inspection de l'URL
-> Demander l'indexation, 10 a 20 par jour). Lecture seule, ne modifie aucune page.
"""
import os, sys, json, csv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hub_consolidation as hc  # noqa: E402

D = "pages/podcast-btb/data"
CUTOFF = "2026-09-15"
LABEL = {"extrait": "Prospect : questions extraites", "en_attente": "Prospect : en attente de mail",
         "contact": "Prospect : deja contacte"}
ORDER = {"extrait": 0, "en_attente": 1, "contact": 2}


def main():
    pods = hc.load(f"{D}/podcasts.json", [])
    st = hc.load(f"{D}/gsc_hub_status.json", {})
    q = hc.load("automation/marketforge_engine/queue.json", {"podcasts": {}}).get("podcasts", {})
    diag = hc.load(f"{D}/gsc_hub_diagnostic.json", {}).get("fiches", {})
    rows = []
    for p in pods:
        s = p.get("slug")
        if not s or st.get(s, {}).get("indexed_on"):
            continue
        qs = q.get(s, {}).get("status", "")
        date = (p.get("date") or "")[:10]
        cov = st.get(s, {}).get("coverage", "")
        if qs in ORDER:
            rang, raison, sub = 1, LABEL[qs], ORDER[qs]
        elif date and date < CUTOFF:
            rang, raison, sub = 2, "N1 ancienne jamais explorée par Google", 0
        else:
            rang, raison, sub = 3, "Autre N1", 0
        if cov.startswith("Crawled"):
            raison += " (explorée mais refusée : améliorer le contenu avant de redemander)"
        rows.append((rang, sub, date, s, p, qs, raison))
    rows.sort(key=lambda r: (r[0], r[1], r[2], r[3]))
    out = [{"ordre": i + 1, "rang": r[0], "url": f"{hc.BASE}{r[3]}-podcast.html", "podcast": r[4].get("podcast_name"),
            "categorie": r[4].get("categorie"), "cree_le": r[2], "file": r[5] or "hors file", "raison": r[6]}
           for i, r in enumerate(rows)]
    with open(f"{D}/index_priorite.json", "w", encoding="utf-8") as f:
        json.dump({"_aide": "N1 non indexees, par ordre de priorite pour 'Demander l'indexation' (Search Console), 10 a 20/jour.",
                   "total": len(out), "fiches": out}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(f"{D}/index_priorite.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()), delimiter=";")
        w.writeheader(); w.writerows(out)
    n = {k: sum(1 for o in out if o["rang"] == k) for k in (1, 2, 3)}
    print(f"[n1-priority] {len(out)} N1 non indexees : rang1 (prospects) {n[1]}, rang2 (anciennes) {n[2]}, rang3 {n[3]}")


if __name__ == "__main__":
    main()

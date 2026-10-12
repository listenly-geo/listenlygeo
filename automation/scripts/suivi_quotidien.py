#!/usr/bin/env python3
"""Suivi quotidien de l'objectif (12/10/2026) : combien de VRAIS mails sont partis aujourd'hui sur 30, stock de prets, verifications, erreurs.
Ecrit automation/marketforge_engine/suivi_quotidien.json (60 jours max). Aucune adresse."""
import sys, json, datetime
sys.path.insert(0, "automation/scripts")
import sheet_bridge

ME = "automation/marketforge_engine"
OBJECTIF = 30


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def main():
    today = datetime.date.today()
    d = sheet_bridge.call({"action": "status"})
    prospects = d.get("prospects", [])
    pret = sum(1 for p in prospects if p.get("Statut") == "Pret")
    envoyes = int(d.get("envoyes_aujourdhui", 0))
    g = load(f"{ME}/gate_state.json", {})
    verifs = int(g.get("used", 0)) if g.get("date") == today.isoformat() else 0
    j = load(f"{ME}/journal.json", {}).get("entrees", [])
    jour = today.strftime("%d/%m/%Y")
    erreurs = [f"{e.get('etape')}" for e in j if str(e.get("date", "")).startswith(jour)]
    ligne = {"date": today.isoformat(), "envoyes": envoyes, "objectif": OBJECTIF,
             "atteint": envoyes >= OBJECTIF, "stock_prets": pret, "verifs_filtre": verifs,
             "etapes_en_erreur": sorted(set(erreurs))[:10]}
    s = load(f"{ME}/suivi_quotidien.json", {"_aide": "Objectif : 30 vrais mails par jour a des dirigeants. Une ligne par jour.", "jours": []})
    s["jours"] = [x for x in s["jours"] if x.get("date") != ligne["date"]] + [ligne]
    s["jours"] = s["jours"][-60:]
    json.dump(s, open(f"{ME}/suivi_quotidien.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"suivi : {envoyes}/{OBJECTIF} mails, stock {pret} prets, {verifs} verifications, {len(set(erreurs))} etape(s) en erreur")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Apercu des prochains 1ers mails (17/11/2026) : LECTURE SEULE, n'envoie rien et n'ecrit rien dans le Sheet.

Reproduit l'ordre d'envoi de mfeSend_ (Apps Script) :
  - candidats : statut "Pret" + question reelle (colonne Q) + fiche N1 (/podcast-btb/ en colonne D) ;
  - dirigeants verifies d'abord (module Qui contacter : nom + adresse trouves), puis contacts du flux RSS ;
  - a rang egal, ordre des lignes du Sheet.
Les verifications faites juste avant l'envoi (anti-rebond, MyEmailVerifier, doublon de dirigeant) peuvent en ecarter
quelques-uns : la liste est donc une estimation fidele, pas une garantie.
Aucune adresse email n'est affichee (journaux publics).
"""
import os, sys, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet_bridge as sb  # noqa: E402

N = int(os.environ.get("APERCU_N") or 40)


def main():
    res = sb.call({"action": "status"})
    rows = res.get("prospects", [])
    state = {}
    try:
        state = json.load(open("automation/marketforge_engine/contact_state.json", encoding="utf-8"))
    except (OSError, ValueError):
        pass
    cands = []
    for i, r in enumerate(rows):
        if str(r.get("Statut")) != "Pret" or not str(r.get("Dernier épisode Q") or "").strip():
            continue
        if "/podcast-btb/" not in str(r.get("Preuve (fiche N1)") or ""):
            continue
        st = state.get(r.get("Slug"), {})
        dirigeant = bool(st.get("trouve") and st.get("email_trouve"))
        cands.append((0 if dirigeant else 1, i, r, dirigeant))
    cands.sort(key=lambda x: (x[0], x[1]))
    cap = res.get("cap_jour_effectif")
    deja = res.get("envoyes_aujourdhui")
    lines = [f"Candidats prets : {len(cands)} | plafond du jour : {cap} | deja envoyes ce jour d'envoi : {deja}", "",
             "| # | Podcast | Destinataire | Question | Fiche moment |", "|---|---|---|---|---|"]
    for n, (_, _, r, dirigeant) in enumerate(cands[:N], 1):
        slug, mid = str(r.get("Slug") or "").strip(), str(r.get("Dernier épisode Moment ID") or "").strip()
        url = f"https://listenly.org/podcast-btb/m/{slug}/{mid}" if mid else str(r.get("Preuve (fiche N1)") or "")
        q = str(r.get("Dernier épisode Q") or "").replace("|", "/").strip()
        lines.append(f"| {n} | {str(r.get('Podcast') or '').replace('|', '/')} | {'Dirigeant' if dirigeant else 'Flux RSS'} | {q} | {url} |")
    out = "\n".join(lines)
    print(out)
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as f:
            f.write("## Apercu des prochains 1ers mails\n\n" + out + "\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
SELECTION RESERVOIR (08/11/2026) : volet « 30 % » du plan podcasts connus + reservoir.
Classe les questions du reservoir MarketForge qui n'ont pas encore de fiche (lecture seule : ne modifie rien).

Critere de pertinence (v0, SANS volume Google Ads, pas encore branche) :
  forme de la question (30), sujet metier (35), longueur adaptee au titre SEO (15), pas d'actualite / fait divers (20).
Quand le Keyword Planner sera branche, le volume mensuel s'ajoute comme filtre : seuil 100 recherches/mois.

Sortie : automation/moments_connus/test_selection_reservoir.json (top 30) + resume en console.
"""
import os, sys, json, re, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import moteur_autonome_moments as mam  # noqa: E402  (bibliotheque : main() n'est pas lance a l'import)

RESERVOIR = "automation/marketforge_engine/reservoir_questions.json"
OUT = "automation/moments_connus/test_selection_reservoir.json"
NEWS = ("breaking", "midterm", "election", "sentencing", "trial", "murder", "verdict", "shutdown", "polls",
        "this week", "tonight", "today", "yesterday", "arrested", "killed", "died")


def score(q):
    t = (q or "").strip()
    low = t.lower()
    forme = 0
    if low.startswith(mam.QUESTION_START):
        forme += 20
    if t.endswith("?"):
        forme += 10
    biz = sum(1 for k in mam.BUSINESS if re.search(rf"\b{re.escape(k)}\b", low))
    sujet = min(35, biz * 12)
    n = len(t)
    longueur = 15 if 35 <= n <= 90 else 8 if n <= 120 else 0
    actu = 0 if any(k in low for k in NEWS) else 20
    if mam.named_run(t):
        forme -= 10  # suite de noms propres : peu cherchable
    return forme + sujet + longueur + actu


def main():
    items = json.load(open(RESERVOIR, encoding="utf-8"))["items"]
    a_traiter = [i for i in items if not i.get("fiche_url")]
    scored = []
    for i in a_traiter:
        scored.append({"score": score(i.get("question", "")), "question": i.get("question", ""),
                       "podcast_slug": i.get("podcast_slug", ""), "date_ajout": i.get("date_ajout", ""),
                       "episode": i.get("episode_title", "")})
    scored.sort(key=lambda x: (-x["score"], x["podcast_slug"]))
    top, par_podcast = [], collections.Counter()
    for s in scored:   # plafond de 3 par podcast, comme la selection quotidienne
        if par_podcast[s["podcast_slug"]] >= 3:
            continue
        top.append(s); par_podcast[s["podcast_slug"]] += 1
        if len(top) == 30:
            break
    out = {"note": "TEST — classement sans volume Google Ads (non branche). Lecture seule.",
           "questions_a_traiter": len(a_traiter), "retenues": top}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(a_traiter)} questions a traiter ; top {len(top)} ecrit dans {OUT}")
    for s in top[:10]:
        print(f"  {s['score']:3d} | {s['podcast_slug'][:28]:28s} | {s['question'][:90]}")


if __name__ == "__main__":
    main()

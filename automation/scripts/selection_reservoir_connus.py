#!/usr/bin/env python3
"""
SELECTION RESERVOIR (08/11/2026) : volet « 30 % » du plan podcasts connus + reservoir.
Classe les questions du reservoir MarketForge qui n'ont pas encore de fiche (lecture seule : ne modifie rien).

Critere de pertinence (score de forme) + VOLUME Google Ads (volumes_reservoir.json, branche le 08/11/2026) :
  forme de la question (30), sujet metier (35), longueur adaptee au titre SEO (15), pas d'actualite / fait divers (20).
Le volume mensuel du theme est un filtre : seuil 100 recherches/mois (SEUIL_VOLUME). Sans volume disponible, classement par score seul.

Sortie : automation/moments_connus/test_selection_reservoir.json (top 30) + resume en console.
"""
import os, sys, json, re, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import moteur_autonome_moments as mam  # noqa: E402  (bibliotheque : main() n'est pas lance a l'import)

RESERVOIR = "automation/marketforge_engine/reservoir_questions.json"
OUT = "automation/moments_connus/test_selection_reservoir.json"
SEUIL_VOLUME = 100
VOLUMES = "automation/moments_connus/volumes_reservoir.json"
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


def qkey(item):
    import hashlib
    norm = re.sub(r'\W+', ' ', (item.get('question') or '').lower()).strip()
    base = item.get('podcast_slug', '') + '|' + norm
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


def main():
    vols = {}
    if os.path.exists(VOLUMES):
        v = json.load(open(VOLUMES, encoding="utf-8"))
        if v.get("statut") == "connecte":
            vols = v.get("items", {})
    items = json.load(open(RESERVOIR, encoding="utf-8"))["items"]
    a_traiter = [i for i in items if not i.get("fiche_url")]
    scored = []
    for i in a_traiter:
        vi = vols.get(qkey(i))
        if vols and (not vi or vi["volume"] < SEUIL_VOLUME):
            continue
        scored.append({"score": score(i.get("question", "")), "volume": vi["volume"] if vi else None,
                       "theme": vi["theme"] if vi else None, "question": i.get("question", ""),
                       "podcast_slug": i.get("podcast_slug", ""), "date_ajout": i.get("date_ajout", ""),
                       "episode": i.get("episode_title", "")})
    scored.sort(key=lambda x: (-(x["volume"] or 0), -x["score"], x["podcast_slug"]))
    top, par_podcast = [], collections.Counter()
    for s in scored:   # plafond de 3 par podcast, comme la selection quotidienne
        if par_podcast[s["podcast_slug"]] >= 3:
            continue
        top.append(s); par_podcast[s["podcast_slug"]] += 1
        if len(top) == 30:
            break
    out = {"note": "Classement par volume Google Ads (seuil 100/mois) puis score. Lecture seule." if vols else "TEST — volumes absents, classement par score seul. Lecture seule.",
           "questions_a_traiter": len(a_traiter), "questions_au_dessus_du_seuil": len(scored) if vols else None, "retenues": top}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(a_traiter)} questions a traiter ; top {len(top)} ecrit dans {OUT}")
    for s in top[:10]:
        print(f"  vol {s['volume']} | {s['score']:3d} | {s['podcast_slug'][:28]:28s} | {s['question'][:90]}")


if __name__ == "__main__":
    main()

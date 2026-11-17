#!/usr/bin/env python3
"""
Optimiseur du test A/B de la phrase d'accroche du 1er mail (17/11/2026, remplace l'ancien test A-E).

Principe (decision d'Etienne du 17/11/2026) :
  - le 1er mail contient UNE phrase testee (en gras, emplacement {CTA}) ; tout le reste du mail est identique ;
  - 4 versions actives, 25 % des envois chacune ; chaque envoi note l'identifiant de la version (Q0, Q1...) dans
    la colonne "Variante CTA" du Sheet ;
  - un cycle dure 7 jours. A la fin du cycle :
      * une version a strictement plus de vraies reponses que toutes les autres -> elle devient la reference
        (gagnante) et les autres sont remplacees par les 3 suivantes de la reserve ;
      * aucune reponse -> la reference est gardee, les 3 challengers sont remplaces par la reserve ;
      * egalite en tete (avec des reponses) -> le cycle est prolonge jusqu'a 14 jours, puis le meilleur taux gagne.
  - la reserve ne contient que des phrases deja montrees a Etienne. Reserve vide -> on garde les versions en cours
    et le verdict demande de nouvelles phrases (jamais de texte invente automatiquement).

Sources : prospection_stats.json (cle ab_envois : toutes les lignes testees, sans email), replies.json (classes),
config.json (reponses automatiques ignorees). Sortie : automation/marketforge_engine/ab_test.json, lu par Apps Script
(textes + poids) et par la Synthese du Sheet. Aucun appel reseau, aucune cle API.
"""
import sys, json, datetime

STATS = "automation/marketforge_engine/prospection_stats.json"
CONFIG = "automation/marketforge_engine/config.json"
REPLIES = "automation/marketforge_engine/replies.json"
OUT = "automation/marketforge_engine/ab_test.json"

CYCLE_JOURS = 7
CYCLE_MAX_JOURS = 14   # prolongation maximale en cas d'egalite
NB_ACTIVES = 4

# Cycle 1 (valide par Etienne le 17/11/2026). Q0 = phrase historique, reference.
DEPART = {
    "Q0": ("Trafic (reference)", "Have you ever considered turning each episode into traffic that comes directly from Google & AI, with nothing to change in your strategy?"),
    "Q1": ("Reference / expert", "Have you ever thought about becoming the expert Google and ChatGPT recommend in your field, without writing a word?"),
    "Q2": ("Clients", "Have you ever thought about your episodes bringing you clients from Google and ChatGPT, without recording a single extra episode?"),
    "Q3": ("Clients cites par l'IA", "Have you ever thought about ChatGPT recommending your business when your future clients ask a question, without publishing anything new?"),
}
# Reserve : phrases deja proposees a Etienne dans le chat du 17/11/2026 (meme structure que Q0). Ordre = ordre d'entree en test.
RESERVE = [
    ("Q4", "Rendez-vous", "Have you ever considered turning each episode into booked calls that come directly from Google & AI, with nothing to change in your podcast?"),
    ("Q5", "Prospects qualifies", "Have you ever considered turning each episode into qualified leads that come directly from Google & AI, with nothing to change in your workflow?"),
    ("Q6", "Reponses d'expert", "Have you ever considered turning each episode into expert answers that Google & AI recommend to your future clients, with nothing to change in your strategy?"),
    ("Q7", "Nouveaux clients", "Have you ever considered turning each episode into new clients that come directly from Google & AI, with nothing to change in your strategy?"),
]
DEBUT = "2026-11-17"


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def initial_state():
    return {
        "cycle": 1, "cycle_debut": DEBUT, "controle": "Q0",
        "versions": {k: {"label": l, "texte": t} for k, (l, t) in DEPART.items()},
        "actives": list(DEPART),
        "reserve": [{"id": i, "label": l, "texte": t} for i, l, t in RESERVE],
        "historique": [],
    }


def count(state, envois, replies, ignored):
    debut = state["cycle_debut"]
    v = {k: {"envoye": 0, "rebond": 0, "reponse": 0, "positive": 0} for k in state["actives"]}
    for p in envois:
        k = str(p.get("variante") or "").strip()
        if k not in v or str(p.get("envoye_le") or "")[:10] < debut:
            continue
        d = v[k]
        d["envoye"] += 1
        st = p.get("statut")
        if st == "Rebond":
            d["rebond"] += 1
        if st == "Repondu" and p.get("slug") not in ignored:
            cl = replies.get(str(p.get("podcast") or "").strip().lower(), "")
            if cl != "auto":
                d["reponse"] += 1
                if cl == "positive":
                    d["positive"] += 1
    for d in v.values():
        d["delivres"] = max(d["envoye"] - d["rebond"], 0)
        d["taux_pct"] = round(100.0 * d["reponse"] / d["delivres"], 1) if d["delivres"] else None
    return v


def new_cycle(state, keep, today, decision, stats):
    """Garde `keep` (reference) et complete avec la reserve jusqu'a NB_ACTIVES. Retourne False si la reserve est vide."""
    state["historique"].append({"cycle": state["cycle"], "debut": state["cycle_debut"], "fin": today,
                                "decision": decision, "resultats": stats})
    need = NB_ACTIVES - 1
    if not state["reserve"]:
        return False
    nouvelles = state["reserve"][:need]
    state["reserve"] = state["reserve"][need:]
    for n in nouvelles:
        state["versions"][n["id"]] = {"label": n["label"], "texte": n["texte"]}
    state["controle"] = keep
    state["actives"] = [keep] + [n["id"] for n in nouvelles]
    state["cycle"] += 1
    state["cycle_debut"] = today
    return True


def main():
    prev = load(OUT, {})
    state = prev.get("etat") or initial_state()
    stats = load(STATS, {})
    envois = stats.get("ab_envois") or stats.get("prospects", [])
    ignored = set(load(CONFIG, {}).get("reponses_automatiques_ignorees", []))
    replies = {str(r.get("podcast") or "").strip().lower(): r.get("classe") or "" for r in load(REPLIES, [])}

    today = datetime.date.today().isoformat()
    jours = (datetime.date.today() - datetime.date.fromisoformat(state["cycle_debut"])).days
    v = count(state, envois, replies, ignored)
    note = ""

    if jours >= CYCLE_JOURS:
        ranked = sorted(state["actives"], key=lambda k: (v[k]["reponse"], v[k]["taux_pct"] or 0), reverse=True)
        top, second = ranked[0], ranked[1] if len(ranked) > 1 else None
        total = sum(d["reponse"] for d in v.values())
        snap = {k: dict(v[k], texte=state["versions"][k]["texte"]) for k in state["actives"]}
        decision = None
        if total == 0:
            decision, keep = f"aucune reponse en {jours} jours : {state['controle']} reste la reference, 3 nouvelles phrases", state["controle"]
        elif second is None or v[top]["reponse"] > v[second]["reponse"]:
            decision, keep = f"gagnante : {top} ({v[top]['reponse']} reponses)", top
        elif jours >= CYCLE_MAX_JOURS:
            decision, keep = f"egalite apres {jours} jours : {top} gagne au meilleur taux", top
        if decision:
            if new_cycle(state, keep, today, decision, snap):
                note = f"Cycle {state['cycle'] - 1} termine ({decision}). Cycle {state['cycle']} demarre."
                v = count(state, envois, replies, ignored)
                jours = 0
            else:
                note = f"Cycle {state['cycle']} termine ({decision}) mais la reserve est vide : nouvelles phrases a valider par Etienne."
                state["historique"][-1]["reserve_vide"] = True
                state["cycle_debut"] = today   # on relance un cycle avec les memes versions en attendant
                state["controle"] = keep
                v = count(state, envois, replies, ignored)
                jours = 0
        else:
            note = f"Egalite en tete apres {jours} jours : cycle prolonge (jusqu'a {CYCLE_MAX_JOURS} jours)."

    actives = state["actives"]
    weights = {k: round(1.0 / len(actives), 4) for k in actives}
    reste = max(CYCLE_JOURS - jours, 0)
    if len(state["reserve"]) < NB_ACTIVES - 1:
        note = (note + " " if note else "") + f"Reserve presque vide ({len(state['reserve'])} phrase(s)) : proposer de nouvelles phrases a Etienne."
    verdict = (note + " " if note else "") + (
        f"Cycle {state['cycle']} (depuis le {state['cycle_debut']}) : {sum(v[k]['envoye'] for k in actives)} envois, "
        f"{sum(v[k]['reponse'] for k in actives)} vraies reponses. Decision dans {reste} jour(s).")

    out = {
        "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M"),
        "actif": True,
        "cycle": state["cycle"], "cycle_debut": state["cycle_debut"], "controle": state["controle"],
        "phase": f"cycle {state['cycle']}, jour {jours + 1}/{CYCLE_JOURS}",
        "verdict": verdict,
        "weights": weights,
        "texts": {k: state["versions"][k]["texte"] for k in actives},   # lu par Apps Script : phrase inseree a la place de {CTA}
        "variants": {k: {"label": state["versions"][k]["label"] + (" (reference)" if k == state["controle"] and "reference" not in state["versions"][k]["label"] else ""),
                         "texte": state["versions"][k]["texte"], **v[k],
                         "chance_meilleure_pct": "", "part_envois_pct": round(100 * weights[k], 1)} for k in actives},
        "reserve_restante": len(state["reserve"]),
        "etat": state,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for k in actives:
        d = out["variants"][k]
        print(f"[ab] {k}: {d['envoye']} env., {d['rebond']} rebonds, {d['reponse']} rep. ({d['taux_pct']}%) — {d['label']}")
    print(f"[ab] {verdict}")
    print(f"::notice title=Test A/B accroche::{verdict}")


if __name__ == "__main__":
    sys.exit(main())

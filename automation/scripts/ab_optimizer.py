#!/usr/bin/env python3
"""
Optimiseur du 1er mail : BASE 75 % + CHALLENGER 25 % (decision d'Etienne du 18/11/2026, remplace le test des 4 questions).

Principe :
  - la BASE (controle) est le mail actuel, avec la phrase Q0 : 75 % des envois ;
  - UN challenger a la fois, 25 % des envois : un mail COMPLET construit sur un angle different (meme promesse,
    meme objet, meme PS, meme signature). Chaque envoi note l'identifiant (Q0, C2...) dans la colonne "Variante CTA" ;
  - decision quand le challenger a >= MIN_DELIVRES mails delivres (ou a la fin de la duree maximale) :
      * le challenger a un taux de vraies reponses strictement superieur a celui de la base ET au moins 1 reponse
        -> il devient la nouvelle base (l'ancienne base est retiree) ;
      * sinon il est retire et le challenger suivant de la reserve prend la place ;
  - arret anticipe : >= MIN_ARRET delivres, 0 reponse, alors que la base a un taux >= 1 % -> challenger retire ;
  - la reserve ne contient que des textes deja montres a Etienne. Reserve vide -> on garde la base seule (100 %)
    et le verdict demande de nouveaux challengers (jamais de texte invente automatiquement).

Sources : prospection_stats.json (cle ab_envois, sans email), replies.json, config.json. Sortie : ab_test.json, lu par
Apps Script (textes, corps complets, poids) et par la Synthese du Sheet. Aucun appel reseau, aucune cle API.
"""
import sys, json, datetime

STATS = "automation/marketforge_engine/prospection_stats.json"
CONFIG = "automation/marketforge_engine/config.json"
REPLIES = "automation/marketforge_engine/replies.json"
OUT = "automation/marketforge_engine/ab_test.json"

PART_CHALLENGER = 0.25
MIN_DELIVRES = 150      # decision normale
MIN_ARRET = 80          # arret anticipe si 0 reponse et base >= 1 %
DUREE_MAX_JOURS = 28    # decision forcee
DEBUT = "2026-11-18"

BASE_Q0 = ("Base (reference)", "Have you ever considered turning each episode into traffic that comes directly from Google & AI, with nothing to change in your strategy?")

PS = "<em>PS: Without a reply, the system automatically keeps your episodes' traffic on Listenly.</em>"

# Challengers (textes montres a Etienne le 18/11/2026). Variables Apps Script : {HELLO} {PODCAST} {QUERY} {MOMENT_URL}.
CHALLENGERS = [
    ("C2", "Preuve d'abord",
     "{HELLO}\n\nIn one of your episodes of <strong>{PODCAST}</strong>, this question comes up: <em>\"{QUERY}\"</em>\n\n"
     "I turned the answer into a page that Google, ChatGPT and Gemini can cite, <a href=\"{MOMENT_URL}\">here</a>.\n\n"
     "Every episode could work the same way, with nothing extra to record.\n\n"
     "<strong>Worth a look at what that would mean for your business?</strong>\n\nBest regards,\n\nEtienne\n\n" + PS),
    ("C3", "Resultat client",
     "{HELLO}\n\nYour episodes of <strong>{PODCAST}</strong> already contain the answers your future clients are searching for. "
     "Today, only your listeners find them.\n\n"
     "We turn each one into a page that Google and ChatGPT can cite, so the right people find you before your competitors. "
     "Example: <a href=\"{MOMENT_URL}\">here</a>.\n\n"
     "<strong>Open to seeing what yours would look like?</strong>\n\nBest regards,\n\nEtienne\n\n" + PS),
    ("C1", "Court (curiosite)",
     "{HELLO}\n\nQuick question about <strong>{PODCAST}</strong>: when a business leader asks ChatGPT about {THEMATIQUE}, "
     "is your expertise the answer it cites?\n\n"
     "Your episodes could be, like <a href=\"{MOMENT_URL}\">here</a>.\n\nBest regards,\n\nEtienne\n\n" + PS),
]


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def initial_state(old=None):
    hist = list((old or {}).get("historique", []))
    if old and old.get("mode") != "base_challenger":
        hist.append({"cycle": old.get("cycle"), "debut": old.get("cycle_debut"), "fin": DEBUT,
                     "decision": "arrete : passage au modele base 75 % / challenger 25 % (decision du 18/11/2026)"})
    ch = CHALLENGERS[0]
    return {
        "mode": "base_challenger", "cycle": 1, "cycle_debut": DEBUT, "controle": "Q0",
        "versions": {"Q0": {"label": BASE_Q0[0], "texte": BASE_Q0[1]},
                     ch[0]: {"label": ch[1], "texte": "(mail complet : " + ch[1] + ")", "corps": ch[2]}},
        "actives": ["Q0", ch[0]], "challenger": ch[0],
        "reserve": [{"id": i, "label": l, "corps": c} for i, l, c in CHALLENGERS[1:]],
        "historique": hist,
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


def next_challenger(state, today, decision, snap):
    """Cloture le challenger courant (et promeut ou non), puis prend le suivant. Retourne False si reserve vide."""
    state["historique"].append({"cycle": state["cycle"], "debut": state["cycle_debut"], "fin": today,
                                "decision": decision, "resultats": snap})
    state["cycle"] += 1
    state["cycle_debut"] = today
    if not state["reserve"]:
        state["actives"] = [state["controle"]]
        state["challenger"] = None
        return False
    n = state["reserve"].pop(0)
    state["versions"][n["id"]] = {"label": n["label"], "texte": "(mail complet : " + n["label"] + ")", "corps": n["corps"]}
    state["challenger"] = n["id"]
    state["actives"] = [state["controle"], n["id"]]
    return True


def main():
    prev = load(OUT, {})
    state = prev.get("etat")
    if not state or state.get("mode") != "base_challenger":
        state = initial_state(state)
    stats = load(STATS, {})
    envois = stats.get("ab_envois") or stats.get("prospects", [])
    ignored = set(load(CONFIG, {}).get("reponses_automatiques_ignorees", []))
    replies = {str(r.get("podcast") or "").strip().lower(): r.get("classe") or "" for r in load(REPLIES, [])}

    today = datetime.date.today().isoformat()
    jours = (datetime.date.today() - datetime.date.fromisoformat(state["cycle_debut"])).days
    v = count(state, envois, replies, ignored)
    note = ""
    base, ch = state["controle"], state.get("challenger")

    if ch:
        b, c = v[base], v[ch]
        snap = {k: dict(v[k], label=state["versions"][k]["label"]) for k in state["actives"]}
        decision = promote = None
        if c["delivres"] >= MIN_DELIVRES or jours >= DUREE_MAX_JOURS:
            tb, tc = b["taux_pct"] or 0, c["taux_pct"] or 0
            if c["reponse"] >= 1 and tc > tb:
                decision, promote = f"{ch} ({state['versions'][ch]['label']}) bat la base : {c['reponse']} reponses sur {c['delivres']} delivres ({tc} %) contre {tb} %. {ch} devient la base.", True
            else:
                decision, promote = f"{ch} retire : {c['reponse']} reponses sur {c['delivres']} delivres ({tc} %) contre {tb} % pour la base.", False
        elif c["delivres"] >= MIN_ARRET and c["reponse"] == 0 and (b["taux_pct"] or 0) >= 1.0:
            decision, promote = f"{ch} arrete : 0 reponse sur {c['delivres']} delivres alors que la base est a {b['taux_pct']} %.", False
        if decision:
            if promote:
                state["controle"] = ch
            if next_challenger(state, today, decision, snap):
                note = f"{decision} Nouveau challenger : {state['challenger']}."
            else:
                note = f"{decision} Reserve vide : la base envoie 100 %. Nouveaux challengers a valider par Etienne."
            v = count(state, envois, replies, ignored)
            jours = 0
            base, ch = state["controle"], state.get("challenger")

    actives = state["actives"]
    if ch:
        weights = {base: round(1 - PART_CHALLENGER, 4), ch: PART_CHALLENGER}
    else:
        weights = {base: 1.0}
    if ch and len(state["reserve"]) == 0:
        note = (note + " " if note else "") + "Dernier challenger de la reserve : proposer de nouveaux textes a Etienne."
    tot_env = sum(v[k]["envoye"] for k in actives)
    tot_rep = sum(v[k]["reponse"] for k in actives)
    verdict = (note + " " if note else "") + (
        f"Cycle {state['cycle']} (depuis le {state['cycle_debut']}) : base {base} {int(weights[base]*100)} %"
        + (f", challenger {ch} {int(weights[ch]*100)} %" if ch else ", pas de challenger")
        + f" ; {tot_env} envois, {tot_rep} vraies reponses. "
        + (f"Decision a {MIN_DELIVRES} delivres pour {ch} (actuellement {v[ch]['delivres']})." if ch else ""))

    out = {
        "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M"),
        "actif": True, "mode": "base_challenger",
        "cycle": state["cycle"], "cycle_debut": state["cycle_debut"], "controle": base,
        "phase": f"cycle {state['cycle']}, jour {jours + 1}",
        "verdict": verdict, "weights": weights,
        "texts": {k: state["versions"][k]["texte"] for k in actives},     # lu par Apps Script
        "bodies": {k: state["versions"][k]["corps"] for k in actives if state["versions"][k].get("corps")},  # mail complet du challenger
        "variants": {k: {"label": state["versions"][k]["label"] + (" (base)" if k == base and "base" not in state["versions"][k]["label"].lower() else ""),
                         "texte": state["versions"][k]["texte"], **v[k],
                         "chance_meilleure_pct": "", "part_envois_pct": round(100 * weights[k], 1)} for k in actives},
        "reserve_restante": len(state["reserve"]),
        "etat": state,
    }
    # la base promue par un challenger n'a plus de phrase CTA (c'est un mail complet) : Apps Script utilise alors bodies[base]
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for k in actives:
        d = out["variants"][k]
        print(f"[ab] {k}: {d['envoye']} env., {d['rebond']} rebonds, {d['reponse']} rep. ({d['taux_pct']}%) — {d['label']} ({d['part_envois_pct']} %)")
    print(f"[ab] {verdict}")
    print(f"::notice title=Base/challenger::{verdict}")


if __name__ == "__main__":
    sys.exit(main())

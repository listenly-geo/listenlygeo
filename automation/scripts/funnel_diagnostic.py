#!/usr/bin/env python3
"""
Reflexion du MarketForge Engine (03/10/2026) : la machine cherche seule OU le funnel Hub bloque et POURQUOI
il n'y a pas encore de client.

Lit uniquement les fichiers du depot (aucun reseau, aucune cle). Appelee a chaque run par targeting_optimizer.py.
Sorties :
  automation/marketforge_engine/reflexion.json   donnees (funnel, blocages, hypotheses, actions)
  automation/marketforge_engine/reflexion.md     lecture humaine, en francais
  + annotations GitHub ::warning:: pour chaque blocage (visibles dans le run)

Etapes du funnel : contact cree -> mail envoye -> delivre -> reponse -> reponse POSITIVE -> demo/VSL -> paiement Hub.
Les reponses sont classees dans replies.json (champ "classe" : positive | neutre | refus | auto). Tant que rien
n'est classe positive, la machine le signale : sans cette mesure, impossible de trouver le funnel gagnant.
"""
import os, sys, json, datetime

ME = "automation/marketforge_engine"
STATS, QUEUE, CONFIG = f"{ME}/prospection_stats.json", f"{ME}/queue.json", f"{ME}/config.json"
REPLIES, AB, TARGET = f"{ME}/replies.json", f"{ME}/ab_test.json", f"{ME}/targeting.json"
OUT_JSON, OUT_MD = f"{ME}/reflexion.json", f"{ME}/reflexion.md"

BOUNCE_ALERT = 0.03        # taux de rebond 3 jours au-dela duquel la delivrabilite est en danger
MIN_SENT_SIGNAL = 100      # envois avant de conclure quoi que ce soit sur le taux de reponse
CLIENT_EST = (500, 3000)   # ordre de grandeur (hypothese) : mails necessaires pour un 1er client a 1500 $


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def run():
    now = datetime.datetime.utcnow()
    today = now.date().isoformat()
    yday = (now.date() - datetime.timedelta(days=1)).isoformat()
    stats, queue, cfg = load(STATS, {}), load(QUEUE, {}), load(CONFIG, {})
    replies, ab, target = load(REPLIES, []), load(AB, {}), load(TARGET, {})
    prospects = stats.get("prospects", [])
    pods = queue.get("podcasts", {})
    journal = queue.get("journal", {})

    st = {}
    for p in prospects:
        st[p.get("statut")] = st.get(p.get("statut"), 0) + 1
    sent_total = stats.get("sent_total", 0)
    sent_by_day = stats.get("sent_by_day", {})
    bounce_by_day = stats.get("bounces_by_day", {})
    last3 = [(now.date() - datetime.timedelta(days=i)).isoformat() for i in range(3)]
    sent3 = sum(sent_by_day.get(d, 0) for d in last3)
    bounce3 = sum(bounce_by_day.get(d, 0) for d in last3)
    real = [r for r in replies if r.get("classe") != "auto"]
    positives = [r for r in real if r.get("classe") == "positive"]
    classed = [r for r in real if r.get("classe") in ("positive", "neutre", "refus")]
    pod_status = {}
    for p in pods.values():
        pod_status[p.get("status")] = pod_status.get(p.get("status"), 0) + 1
    cap = stats.get("cap_jour_effectif") or 44

    funnel = {
        "podcasts_en_file": len(pods), "contacts_prets_a_mailer": pod_status.get("contact", 0),
        "bloques_en_attente": pod_status.get("en_attente", 0), "sans_email": pod_status.get("sans_email", 0),
        "prospects_dans_sheet": len(prospects), "statut_pret": st.get("Pret", 0),
        "mails_envoyes": sent_total, "relances": stats.get("followups_total", 0),
        "rebonds_total": st.get("Rebond", 0), "reponses_reelles": stats.get("replies_total", len(real)),
        "reponses_classees": len(classed), "reponses_positives": len(positives),
        "demos_envoyees": 0, "paiements_hub": 0,
    }

    blocages, hypotheses, actions = [], [], []

    # --- 1. Blocages mecaniques (le plus dangereux : tout semble tourner, rien ne sort) ---
    if cfg.get("pause"):
        blocages.append("PAUSE active dans config.json : tout est coupe.")
    c_today = journal.get(today, {}).get("contacts", 0)
    c_yday = journal.get(yday, {}).get("contacts", 0)
    if c_today == 0 and c_yday == 0 and funnel["bloques_en_attente"] > 20:
        blocages.append(f"Aucun contact cree depuis 2 jours alors que {funnel['bloques_en_attente']} podcasts attendent : "
                        "etape 'contact' bloquee (verifier extraction_auto, doit etre false).")
        actions.append("Verifier config.json : extraction_auto=false, onboarding_auto=true, pause=false.")
    if cfg.get("extraction_auto") and funnel["bloques_en_attente"] > 20:
        blocages.append("extraction_auto=true : les nouveaux podcasts restent en 'en_attente' au lieu de passer en contact.")
    if not stats.get("envoi_auto", True):
        blocages.append("envoi_auto=false : le Sheet prepare mais n'envoie plus (pause auto rebonds ? reglage MFE_ENVOI_AUTO).")
    hour = now.hour
    if funnel["statut_pret"] == 0 and 6 <= hour <= 17:
        blocages.append("Stock 'Pret' vide : plus aucun mail a envoyer (decouverte/onboarding/contact en panne ou emails rejetes).")
    done_days = [d for d in sorted(sent_by_day) if d < today][-2:]
    if done_days and all(sent_by_day[d] < 0.5 * cap for d in done_days) and funnel["statut_pret"] > 0:
        blocages.append(f"Envois sous 50 % du plafond ({cap}/j) alors que des prospects sont prets : Apps Script arrete ou plage horaire/quota en cause.")
    if sent3 >= 20 and bounce3 / sent3 > BOUNCE_ALERT:
        blocages.append(f"Rebonds {bounce3}/{sent3} sur 3 jours ({100*bounce3//sent3} %) : reputation du domaine en danger.")
        actions.append("Durcir le filtre email (verification boite) et ralentir tant que le taux de rebond depasse 3 %.")
    upd = stats.get("updated", "")
    try:
        if (now - datetime.datetime.fromisoformat(upd)).total_seconds() > 8 * 3600:
            blocages.append(f"Statistiques non rafraichies depuis plus de 8 h ({upd}) : bridge Sheet ou Apps Script a l'arret.")
    except Exception:
        pass

    # --- 2. Pourquoi pas encore de client ? (lecture du funnel, etape par etape) ---
    envoyes = funnel["mails_envoyes"]
    rep = funnel["reponses_reelles"]
    if envoyes < MIN_SENT_SIGNAL:
        hypotheses.append(f"Volume : {envoyes} mails seulement. Sous {MIN_SENT_SIGNAL}, le taux de reponse n'est pas interpretable.")
    low, high = CLIENT_EST
    hypotheses.append(f"Ordre de grandeur (hypothese, pas une mesure) : un 1er client a ~1500 $ demande souvent {low} a {high} mails "
                      f"froids. Il en reste {max(0, low - envoyes)} a {max(0, high - envoyes)}, soit environ "
                      f"{max(0, low - envoyes) // max(cap, 1)} a {max(0, high - envoyes) // max(cap, 1)} jours au rythme actuel ({cap}/j).")
    if envoyes >= MIN_SENT_SIGNAL and rep == 0:
        hypotheses.append("0 reponse reelle apres 100+ mails : probleme probable de delivrabilite (spam), d'objet ou d'offre. "
                          "Tester un objet sans emoji et sans '🔴', un mail plus court, une 1re phrase tournee sur le podcast.")
        actions.append("Envoyer un mail test vers une boite perso (Gmail/Outlook) et verifier inbox vs spam.")
    elif envoyes >= MIN_SENT_SIGNAL and rep / max(envoyes, 1) < 0.01:
        hypotheses.append(f"Reponse {100*rep/envoyes:.1f} % : sous le seuil habituel (1-3 %). L'accroche ou la cible est a revoir avant d'augmenter le volume.")
    if rep > 0 and not classed:
        blocages.append("Reponses non classees (positive / neutre / refus) : impossible de savoir si le funnel marche. "
                        "Ajouter le champ 'classe' dans replies.json.")
        actions.append("Classer chaque reponse reelle : positive (interesse par le Hub), neutre, refus.")
    if classed and not positives and len(classed) >= 5:
        hypotheses.append("Des reponses mais aucune positive : l'offre Hub n'est pas percue comme un besoin. Tester un autre angle de CTA.")
    if positives and not funnel["demos_envoyees"]:
        hypotheses.append("Reponses positives mais pas de demo/VSL : l'etape suivante du funnel n'est pas encore outillee.")
    ranking = target.get("ranking", [])
    thin = [r["secteur"] for r in ranking if r.get("envoye", 0) < 15]
    if thin:
        hypotheses.append(f"{len(thin)} secteurs avec moins de 15 envois : aucun signal par niche, ne pas en tirer de conclusion.")
    if ab.get("verdict", "").startswith("trop tot"):
        hypotheses.append("Test A/B CTA : trop tot pour un gagnant. Ne rien changer avant 100 envois par variante.")
    if funnel["relances"] and not positives:
        hypotheses.append("Relances envoyees sans reponse positive : mesurer separement 1er mail vs relances.")

    status = "BLOQUE" if blocages else ("SOUS-SURVEILLANCE" if envoyes < MIN_SENT_SIGNAL else "EN_COURS")
    out = {"updated": now.isoformat(timespec="minutes"), "statut": status, "funnel": funnel,
           "blocages": blocages, "hypotheses": hypotheses, "actions": actions}
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    md = [f"# Reflexion du MarketForge Engine ({out['updated']} UTC)", f"**Statut : {status}**", "", "## Funnel"]
    md += [f"- {k.replace('_', ' ')} : {v}" for k, v in funnel.items()]
    md += ["", "## Blocages"] + ([f"- {b}" for b in blocages] or ["- aucun"])
    md += ["", "## Pourquoi pas encore de client"] + [f"- {h}" for h in hypotheses]
    md += ["", "## Actions proposees"] + ([f"- {a}" for a in actions] or ["- aucune urgente"])
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    for b in blocages:
        print(f"::warning title=Reflexion::{b}")
    print(f"[reflexion] statut {status} | {envoyes} envois, {rep} reponse(s), {len(positives)} positive(s) | {len(blocages)} blocage(s)")
    return out


if __name__ == "__main__":
    run()

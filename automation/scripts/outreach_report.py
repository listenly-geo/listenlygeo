#!/usr/bin/env python3
"""
19h45 — Rapport marketing du soir (moteur autorite / prospection uniquement). Lisible en moins de 2 minutes.
Structure : Resultats du jour - Ce qui fonctionne - Ce qui ne fonctionne pas - Apprentissages (3 max) - Strategie de demain
            puis A garder / A arreter / A tester demain.

Usage : python3 automation/scripts/outreach_report.py /tmp/rapport.html   (derniere ligne imprimee = objet du mail)
Donnees : prospection_stats.json, ab_test.json, replies.json (classes oui/non/auto/autre) et
  synthese.json ecrit chaque soir par l'analyste (Claude) :
  {"marche":[..],"ne_marche_pas":[..],"apprentissages":[.. 3 max],"strategie":[..],"garder":[..],"arreter":[..],"tester":[..]}
(Le budget API reste dans l'onglet « Budget API » du Sheet, pas dans ce mail.)
"""
import sys, json, html, datetime

ME = "automation/marketforge_engine"


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def main(out):
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    today = now.date().isoformat()
    fr = now.strftime("%d/%m/%Y")
    ps = load(f"{ME}/prospection_stats.json", {})
    ab = load(f"{ME}/ab_test.json", {})
    reps = load(f"{ME}/replies.json", [])
    syn = load(f"{ME}/synthese.json", {})

    sent_day = ps.get("sent_by_day", {})
    bnc_day = ps.get("bounces_by_day", {})
    sent_t, bnc_t = sent_day.get(today, 0), bnc_day.get(today, 0)
    total, total_b = ps.get("sent_total", sum(sent_day.values())), sum(bnc_day.values())
    on_day = lambda c, d: len([r for r in reps if r.get("classe") == c and str(r.get("date", ""))[:10] == d])
    yes_t, no_t = on_day("oui", today), on_day("non", today)
    yes = len([r for r in reps if r.get("classe") == "oui"])
    no = len([r for r in reps if r.get("classe") == "non"])
    delivered = max(total - total_b, 0)
    rate = f"{100.0 * (yes + no) / delivered:.1f} %" if delivered else "—"
    rate_t = f"{100.0 * (yes_t + no_t) / max(sent_t - bnc_t, 1):.1f} %" if sent_t else "—"

    css = ("body{margin:0;background:#f5f5f7;font-family:-apple-system,Helvetica,Arial,sans-serif;color:#1d1d1f}"
           ".w{max-width:640px;margin:0 auto;padding:24px 16px}.c{background:#fff;border-radius:16px;padding:20px 22px;margin:0 0 14px}"
           "h1{font-size:24px;margin:0 0 4px}h2{font-size:17px;margin:0 0 8px}p,li{font-size:14px;line-height:1.6}ul{margin:4px 0 0;padding-left:20px}"
           ".k{display:inline-block;min-width:105px;margin:4px 12px 4px 0}.k b{display:block;font-size:26px}.k span{font-size:12px;color:#6e6e73}"
           ".g{background:#e9f7ee}.r{background:#fdecec}.y{background:#fff7e0}.m{color:#6e6e73;font-size:12px}")
    kpi = lambda v, l: f'<div class="k"><b>{v}</b><span>{l}</span></div>'
    lst = lambda xs, empty: "<ul>" + ("".join(f"<li>{html.escape(x)}</li>" for x in xs) if xs else f"<li class='m'>{empty}</li>") + "</ul>"

    h = [f"<html><head><meta charset='utf-8'><style>{css}</style></head><body><div class='w'>",
         f"<div class='c'><h1>Rapport marketing — {fr}</h1><p class='m'>Prospection : ce qui marche, ce qui bloque, ce qu'on change demain.</p></div>",
         "<div class='c'><h2>Résultats du jour</h2>"
         + kpi(sent_t, "emails envoyés") + kpi(yes_t, "réponses positives") + kpi(no_t, "réponses négatives")
         + kpi(rate_t, "taux de réponse") + kpi(bnc_t, "rebonds")
         + f"<p class='m'>Depuis le début : {total} envoyés · {yes} positives · {no} négatives · {rate} de réponse · {total_b} rebonds.</p></div>"]
    if ab.get("variants"):
        rows = "".join(f"<li><b>{k}</b> · {html.escape(v.get('label', ''))} : {v.get('envoye', 0)} envois, {v.get('reponse', 0)} réponses</li>"
                       for k, v in ab["variants"].items())
        h.append(f"<div class='c'><h2>Test du CTA en cours</h2><ul>{rows}</ul><p class='m'>{html.escape(ab.get('verdict', ''))}</p></div>")
    h.append("<div class='c g'><h2>✅ Ce qui fonctionne</h2>" + lst(syn.get("marche", []), "Pas encore assez de données pour le dire.") + "</div>")
    h.append("<div class='c r'><h2>❌ Ce qui ne fonctionne pas</h2>" + lst(syn.get("ne_marche_pas", []), "Rien d'établi pour l'instant.") + "</div>")
    h.append("<div class='c'><h2>💡 Apprentissages marketing</h2>" + lst(syn.get("apprentissages", [])[:3], "Pas encore de conclusion fiable.") + "</div>")
    h.append("<div class='c'><h2>🎯 Stratégie de demain</h2>" + lst(syn.get("strategie", []), "Inchangée.") + "</div>")
    h.append("<div class='c y'><p><b>À garder :</b></p>" + lst(syn.get("garder", []), "—")
             + "<p><b>À arrêter :</b></p>" + lst(syn.get("arreter", []), "—")
             + "<p><b>À tester demain :</b></p>" + lst(syn.get("tester", []), "—") + "</div>")
    h.append("</div></body></html>")
    with open(out, "w", encoding="utf-8") as f:
        f.write("".join(h))
    print(f"Rapport marketing {fr} — {sent_t} envoyés · {yes_t} positives · {bnc_t} rebonds")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/rapport.html")

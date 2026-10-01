#!/usr/bin/env python3
"""
Rapport du soir MarketForge — version "marketing" (02/10/2026).
Mission unique : obtenir des OUI. Structure : 1 Fait - 2 Analyse - 3 Optimise - 4 Synthese + plan, plus un budget API.

Usage : python3 automation/scripts/outreach_report.py /tmp/rapport.html   (derniere ligne imprimee = objet du mail)

Donnees : prospection_stats.json, ab_test.json, queue.json (journal d'extraction), optimisations.json, config.json
Fichiers ecrits par l'analyste du soir (Claude) dans automation/marketforge_engine/ :
  replies.json   [{"podcast","date","classe":"oui|non|auto|autre","note"}]  -> OUI / non / reponses automatiques
  synthese.json  {"synthese":["..."],"plan":["..."],"goulot":"..."}          -> section 4 (sinon regles automatiques)
Le budget API est une ESTIMATION (tarifs a ajuster dans RATES ci-dessous).
"""
import sys, json, html, datetime

ME = "automation/marketforge_engine"
RATES = {                       # dollars, estimations a corriger avec les vraies factures
    "whisper_min": 0.006,       # transcription audio (OpenAI Whisper) par minute
    "claude_episode": 0.15,     # extraction Q/R par episode transcrit (Claude)
    "verif_email": 0.005,       # verification d'un email (MyEmailVerifier) par adresse
}


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def fr(d):  # 2026-10-02 -> 02/10/2026
    return datetime.date.fromisoformat(d).strftime("%d/%m/%Y")


def pct(a, b):
    return f"{100.0 * a / b:.1f} %" if b else "—"


def budget(journal, ps):
    rows = []
    for day in sorted(journal):
        j = journal[day]
        w = j.get("minutes", 0) * RATES["whisper_min"]
        c = j.get("episodes", 0) * RATES["claude_episode"]
        v = j.get("contacts", 0) * RATES["verif_email"]
        rows.append((day, j.get("minutes", 0), j.get("episodes", 0), j.get("contacts", 0), w, c, v, w + c + v))
    return rows


def main(out):
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    today = now.date().isoformat()
    ps = load(f"{ME}/prospection_stats.json", {})
    ab = load(f"{ME}/ab_test.json", {})
    q = load(f"{ME}/queue.json", {})
    opt = load(f"{ME}/optimisations.json", {}).get("items", [])
    reps = load(f"{ME}/replies.json", [])
    syn = load(f"{ME}/synthese.json", {})
    st = ps.get("status", {})

    sent_day = ps.get("sent_by_day", {})
    bnc_day = ps.get("bounces_by_day", {})
    rel_day = ps.get("followups_by_day", {})
    sent_t, sent_d = sent_day.get(today, 0), None
    bnc_t = bnc_day.get(today, 0)
    total_sent = ps.get("sent_total", sum(sent_day.values()))
    total_bnc = sum(bnc_day.values())
    delivered = max(total_sent - total_bnc, 0)
    cls = lambda c: [r for r in reps if r.get("classe") == c]
    yes, no, auto = cls("oui"), cls("non"), cls("auto")
    real = len(yes) + len(no) + len(cls("autre"))
    yes_today = [r for r in yes if str(r.get("date", ""))[:10] == today]
    journal = q.get("journal", {})
    jt = journal.get(today, {})
    ready = st.get("Pret", 0)
    onboarded = jt.get("contacts", 0)
    done = [i for i in opt if i.get("date") == fr(today)]

    css = ("body{margin:0;background:#f5f5f7;font-family:-apple-system,Helvetica,Arial,sans-serif;color:#1d1d1f}"
           ".w{max-width:640px;margin:0 auto;padding:24px 16px}.c{background:#fff;border-radius:16px;padding:20px 22px;margin:0 0 14px}"
           "h1{font-size:24px;margin:0 0 4px}h2{font-size:17px;margin:0 0 10px}p,li{font-size:14px;line-height:1.55}"
           "ul{margin:6px 0 0;padding-left:20px}.k{display:inline-block;min-width:120px;margin:4px 14px 4px 0}"
           ".k b{display:block;font-size:26px}.k span{font-size:12px;color:#6e6e73}"
           "table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:6px 8px;border-bottom:1px solid #eee;text-align:left}"
           ".m{color:#6e6e73;font-size:12px}")

    def kpi(v, l):
        return f'<div class="k"><b>{v}</b><span>{l}</span></div>'

    h = [f"<html><head><meta charset='utf-8'><style>{css}</style></head><body><div class='w'>"]
    h.append(f"<div class='c'><h1>MarketForge — {fr(today)}</h1>"
             "<p class='m'>Mission unique : obtenir des OUI de podcasts d'entreprise, pour vendre ensuite le moteur autorité.</p>"
             + kpi(sent_t, "mails envoyés aujourd'hui") + kpi(total_sent, "envoyés au total")
             + kpi(pct(delivered, total_sent), "délivrés") + kpi(real, "vraies réponses")
             + kpi(len(yes), "OUI") + "</div>")

    # 1. Fait
    f = [f"<li><b>{sent_t}</b> mails envoyés (dont {rel_day.get(today, 0)} relances), <b>{bnc_t}</b> rebonds</li>",
         f"<li><b>{onboarded}</b> nouveaux contacts ajoutés ; <b>{ready}</b> prêts à partir</li>"]
    if jt.get("episodes"):
        f.append(f"<li>{jt['episodes']} épisodes transcrits ({jt.get('minutes', 0)} min)</li>")
    for r in yes_today:
        f.append(f"<li>🟢 OUI : <b>{html.escape(r.get('podcast', ''))}</b> {html.escape(r.get('note', ''))}</li>")
    h.append("<div class='c'><h2>1 · Ce qui a été fait</h2><ul>" + "".join(f) + "</ul></div>")

    # 2. Analyse
    a = []
    if ab.get("variants"):
        rows = "".join(
            f"<tr><td>{k}</td><td>{html.escape(v.get('label', ''))}</td><td>{v.get('envoye', 0)}</td><td>{v.get('rebond', 0)}</td>"
            f"<td>{v.get('reponse', 0)}</td><td>{v.get('chance_meilleure_pct', '—')} %</td></tr>"
            for k, v in ab["variants"].items())
        a.append("<p><b>Test A/B du CTA</b></p><table><tr><th></th><th>CTA</th><th>Envois</th><th>Rebonds</th><th>Rép.</th><th>Chance d'être meilleur</th></tr>"
                 + rows + "</table>")
        a.append(f"<p class='m'>{html.escape(ab.get('verdict', ''))}</p>")
    brate = 100.0 * total_bnc / total_sent if total_sent else 0
    a.append(f"<p><b>Délivrabilité :</b> {total_bnc} rebonds sur {total_sent} envois ({brate:.1f} %). Seuil sain : 2 %.</p>")
    a.append(f"<p><b>Réponses :</b> {len(yes)} OUI · {len(no)} non · {len(auto)} automatiques (absence, changement de poste)</p>")
    h.append("<div class='c'><h2>2 · Ce que disent les données</h2>" + "".join(a) + "</div>")

    # 3. Optimise
    o = "".join(f"<li>{html.escape(i['texte'])} <span class='m'>({i['statut']})</span></li>" for i in done) or "<li>Aucun changement aujourd'hui.</li>"
    h.append(f"<div class='c'><h2>3 · Ce qui a été optimisé</h2><ul>{o}</ul></div>")

    # 4. Synthese + plan
    if syn.get("synthese"):
        s, plan, goulot = syn["synthese"], syn.get("plan", []), syn.get("goulot", "")
    else:
        s = []
        if brate > 4:
            s.append("Les mails ne sont peut-être pas tous livrés : la délivrabilité passe avant tout le reste.")
        if delivered < 100:
            s.append(f"Seulement {delivered} mails délivrés : trop tôt pour conclure sur le ciblage ou le CTA.")
        if not yes:
            s.append("Aucun OUI pour l'instant.")
        goulot = "délivrabilité" if brate > 4 else ("volume trop faible pour conclure" if delivered < 100 else "message / CTA")
        plan = ["Continuer le test A/B jusqu'à 100 envois par variante", "Resserrer le ciblage sur les contacts nominatifs d'entreprises"]
    h.append("<div class='c'><h2>4 · Synthèse et plan</h2>"
             + (f"<p><b>Goulot du jour :</b> {html.escape(goulot)}</p>" if goulot else "")
             + "<ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in s) + "</ul>"
             + "<p><b>Plan pour demain</b></p><ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in plan) + "</ul></div>")

    # Budget API
    rows = budget(journal, ps)
    tot = sum(r[7] for r in rows)
    today_row = next((r for r in rows if r[0] == today), None)
    body = "".join(f"<tr><td>{fr(r[0])}</td><td>{r[1]} min</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[7]:.2f} $</td></tr>" for r in rows[-7:])
    h.append("<div class='c'><h2>Budget API (estimé)</h2>"
             f"<p>Aujourd'hui : <b>{(today_row[7] if today_row else 0):.2f} $</b> · cumul depuis le 27/09 : <b>{tot:.2f} $</b></p>"
             "<table><tr><th>Jour</th><th>Audio transcrit</th><th>Épisodes</th><th>Emails vérifiés</th><th>Coût estimé</th></tr>"
             + body + "</table>"
             f"<p class='m'>Estimation : {RATES['whisper_min']} $/min de transcription + {RATES['claude_episode']} $/épisode (Claude) + "
             f"{RATES['verif_email']} $/email vérifié. À comparer avec les factures réelles. Détail dans l'onglet « Budget API » du Sheet.</p></div>")
    h.append("</div></body></html>")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("".join(h))
    print(f"MarketForge {fr(today)} — {sent_t} envoyés · {real} réponses · {len(yes)} OUI")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/rapport.html")

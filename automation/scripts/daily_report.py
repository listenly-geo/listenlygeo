#!/usr/bin/env python3
"""
Rapport quotidien MarketForge Engine (HTML style epure) : succes, referencement, nouvelles fiches, prospection.
Lit les donnees du depot (podcasts.json, regroupement, Search Console, prospection_stats.json du Sheet).

  python automation/scripts/daily_report.py [sortie.html]
Ecrit le HTML et affiche l'objet du mail sur la 1re ligne de stdout (envoye ensuite par Gmail).
"""
import sys, json, html, datetime, urllib.parse

PAGES = "pages/podcast-btb"


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


e = lambda s: html.escape(str(s or ""), quote=True)


def main(out):
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=2)   # Europe/Berlin (ete)
    today = now.date().isoformat()
    d7 = (now.date() - datetime.timedelta(days=6)).isoformat()
    jour = now.strftime("%d/%m/%Y")

    podcasts = load(f"{PAGES}/data/podcasts.json", [])
    cons = load(f"{PAGES}/data/consolidated_questions.json", {"paths": []})
    idx = load(f"{PAGES}/data/gsc_index_status.json", {"urls": {}})
    gp = load(f"{PAGES}/data/gsc_pages.json", {"pages": {}}).get("pages", {})
    ps = load("automation/marketforge_engine/prospection_stats.json", {})

    total = len(podcasts)
    new = [p for p in podcasts if str(p.get("date", ""))[:10] == today]
    week = sum(1 for p in podcasts if str(p.get("date", ""))[:10] >= d7)
    urls = idx.get("urls", {})
    inspected, indexed = len(urls), sum(1 for v in urls.values() if v.get("verdict") == "PASS")
    regroup = len(cons.get("paths", []))
    names = {p.get("fiche_url"): p.get("podcast_name") for p in podcasts}
    hubs = sorted(((v.get("impressions", 0), u) for u, v in gp.items()
                   if u.endswith("-podcast.html") and "/questions/" not in u), reverse=True)
    hub_imp = sum(i for i, _ in hubs)

    st = ps.get("status", {})
    sent_today = (ps.get("sent_by_day") or {}).get(today, 0)
    cap = ps.get("cap_jour_effectif") or "—"
    sent_total = ps.get("sent_total", 0)
    bounces = st.get("Rebond", 0)
    prospects = ps.get("prospects") or []
    rep_all = [p.get("podcast") for p in prospects if p.get("statut") == "Repondu"]
    rep_today = [p.get("podcast") for p in prospects if p.get("statut") == "Repondu" and str(p.get("reponse", ""))[:10] == today]
    rep_total = ps.get("replies_total", len(rep_all))
    rel_today = (ps.get("followups_by_day") or {}).get(today, 0)

    # 10 fiches N1 a soumettre a Google aujourd'hui : calculees par seo_watch.py (nouvelles fiches, confirmees non indexees)
    hub_status = load(f"{PAGES}/data/gsc_hub_status.json", {})
    watch = load(f"{PAGES}/data/seo_watch.json", {})
    sub = watch.get("submit") or {}
    cand = sub.get("urls") or []
    pstat = {}
    order_st = {}
    inspected_hubs = sum(1 for v in hub_status.values() if v.get("date"))
    indexed_hubs = sum(1 for v in hub_status.values() if v.get("indexed_on"))
    GSC = "https://search.google.com/u/1/search-console/inspect?resource_id=sc-domain%3Alistenly.fr"
    GSC = "https://search.google.com/u/1/search-console/inspect?resource_id=sc-domain%3Alistenly.fr"
    submit_rows = "".join(
        f'<tr><td style="padding:8px 0;border-bottom:1px solid #f0f0f3;font-size:13px">'
        f'<a href="{e(GSC)}&amp;id={urllib.parse.quote(c["url"], safe="")}" style="display:inline-block;background:#0071e3;color:#fff;text-decoration:none;font-weight:600;font-size:12px;padding:5px 12px;border-radius:999px;float:right;margin-left:8px">Inspecter →</a>'
        f'<a href="{e(c["url"])}" style="color:#1d1d1f;text-decoration:none;word-break:break-all">{e(c["url"])}</a>'
        f'<div style="font-size:12px;color:#86868b">{e(c.get("name"))} · créée le {e(c.get("created"))}</div></td></tr>' for c in cand) \
        or '<tr><td style="padding:8px 0;font-size:14px;color:#86868b">Aucune nouvelle fiche non indexée à soumettre pour le moment 🎉</td></tr>'

    wins = []
    if rep_today:
        wins.append(f"💬 <b>{len(rep_today)} nouvelle(s) réponse(s)</b> aujourd'hui : {e(', '.join(rep_today))} — va vite répondre !")
    if new:
        wins.append(f"🚀 <b>{len(new)} nouvelles fiches</b> mises en ligne aujourd'hui, visibles par Google et les IA.")
    if sent_today:
        wins.append(f"📬 <b>{sent_today} podcasts</b> ont découvert leur fiche dans leur boîte mail aujourd'hui.")
    if hubs and hubs[0][0]:
        wins.append(f"🏆 Ton hub le plus vu : <b>{e(names.get(hubs[0][1]) or hubs[0][1])}</b> ({hubs[0][0]} impressions Google).")
    if regroup:
        wins.append(f"🧹 <b>{regroup} anciennes fiches</b> regroupées dans leur hub — le site gagne en force.")
    if rep_total:
        wins.append(f"🔥 <b>{rep_total} podcast(s) en conversation</b>. Chaque réponse = une vente possible à 1 500 € + 500 €/mois.")
    if not wins:
        wins.append("⚙️ La machine tourne : découverte, fiches et envois se font tout seuls.")

    F = "font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif;"
    card = lambda inner: f'<div style="background:#fff;border-radius:18px;padding:22px 24px;margin:0 0 16px;border:1px solid #e5e5ea">{inner}</div>'
    h2 = lambda t: f'<div style="font-size:19px;font-weight:700;color:#1d1d1f;margin:0 0 14px">{t}</div>'

    def kpis(items):
        tds = "".join(
            f'<td style="padding:4px 6px 4px 0;vertical-align:top"><div style="background:#f5f5f7;border-radius:14px;padding:12px 14px">'
            f'<div style="font-size:12px;color:#6e6e73">{a}</div><div style="font-size:26px;font-weight:700;color:#1d1d1f">{b}</div>'
            f'<div style="font-size:11px;color:#86868b">{c}</div></div></td>' for a, b, c in items)
        return f'<table width="100%" cellpadding="0" cellspacing="0"><tr>{tds}</tr></table>'

    def line(a, b):
        return (f'<tr><td style="padding:8px 0;border-bottom:1px solid #f0f0f3;color:#6e6e73;font-size:14px">{a}</td>'
                f'<td style="padding:8px 0;border-bottom:1px solid #f0f0f3;text-align:right;font-weight:600;font-size:14px;color:#1d1d1f">{b}</td></tr>')

    items = "".join(
        f'<tr><td style="padding:7px 0;border-bottom:1px solid #f0f0f3;font-size:14px"><a href="{e(p.get("fiche_url"))}" '
        f'style="color:#0071e3;text-decoration:none;font-weight:600">{e(p.get("podcast_name"))}</a>'
        f'<div style="font-size:12px;color:#86868b">{e(p.get("categorie"))}</div></td></tr>' for p in new[:40])
    if len(new) > 40:
        items += f'<tr><td style="padding:8px 0;font-size:13px;color:#86868b">… et {len(new) - 40} autres (voir le tableau de bord)</td></tr>'
    if not items:
        items = '<tr><td style="padding:8px 0;font-size:14px;color:#86868b">Pas de nouvelle fiche aujourd\'hui.</td></tr>'

    rate = f" ({bounces / sent_total * 100:.1f} %)".replace(".", ",") if sent_total else ""
    body = (
        f'<div style="background:#f5f5f7;padding:28px 12px;{F}"><div style="max-width:620px;margin:0 auto">'
        f'<div style="font-size:12px;font-weight:600;color:#86868b;margin:0 0 4px">MarketForge Engine · Listenly</div>'
        f'<div style="font-size:30px;font-weight:700;color:#1d1d1f;margin:0 0 4px">Ton rapport du jour ✨</div>'
        f'<div style="font-size:15px;color:#6e6e73;margin:0 0 20px">{jour}</div>'
        + card(h2("🎉 Les succès") + "".join(f'<div style="font-size:15px;line-height:1.5;color:#1d1d1f;margin:0 0 10px">{w}</div>' for w in wins))
        + card(h2("📈 Le référencement avance")
               + kpis([("Fiches hub", total, "au total"), ("Aujourd'hui", f"+{len(new)}", "nouvelles"), ("Rythme", round(week / 7), "fiches / jour")])
               + '<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px">'
               + line("Hubs visibles dans Google", len([1 for i, _ in hubs if i])) + line("Impressions des hubs (Search Console)", hub_imp)
               + line("Anciennes fiches regroupées dans les hubs", regroup)
               + line("Fiches question vérifiées / indexées (protégées)", f"{inspected} / {indexed}") + "</table>")
        + card(h2("🔗 10 fiches N1 à envoyer à Google")
               + '<div style="font-size:13px;color:#6e6e73;margin:0 0 8px;line-height:1.5">Clique sur <b>Inspecter →</b> (ou colle l\'adresse dans la barre de la Search Console), puis <b>Demander une indexation</b>. Environ 2 minutes pour les 10.'
                 f'<br><a href="{GSC}" style="color:#0071e3;font-weight:600;text-decoration:none">Ouvrir la barre « Inspecter l\'URL » de la Search Console →</a>'
                 f'<br>Fiches N1 confirmées indexées : <b>{indexed_hubs}</b> sur {inspected_hubs} vérifiées.</div>'
               + f'<table width="100%" cellpadding="0" cellspacing="0">{submit_rows}</table>')
        + card(h2(f"🆕 Nouvelles fiches ({len(new)})") + f'<table width="100%" cellpadding="0" cellspacing="0">{items}</table>')
        + card(h2("📬 La prospection")
               + kpis([("Envoyés aujourd'hui", sent_today, f"sur {cap} prévus"), ("Réponses", rep_total, "au total"), ("Prêts", st.get("Pret", 0), "à contacter")])
               + '<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px">'
               + line("Envoi automatique", "🟢 actif" if ps.get("envoi_auto") else "⏸️ en pause")
               + line("Emails envoyés au total", sent_total) + line("Relances envoyées aujourd'hui", rel_today)
               + line("Rebonds", f"{bounces}{rate}")
               + line("Adresses écartées (anti-rebond)", st.get("Email invalide", 0) + st.get("Email risque", 0))
               + (line("En conversation", e(", ".join(rep_all))) if rep_all else "") + "</table>")
        + '<div style="text-align:center;margin:22px 0 8px">'
          '<a href="https://listenly.fr/podcast-btb/moteur.html" style="display:inline-block;background:#0071e3;color:#fff;text-decoration:none;font-weight:600;font-size:14px;padding:11px 20px;border-radius:999px;margin:4px">Tableau de bord</a> '
          '<a href="https://docs.google.com/spreadsheets/d/1b53cWGiz6iOuakpotw_Ck4bQBeIMJa3hfq5gP2mFiT4/edit" style="display:inline-block;background:#1d1d1f;color:#fff;text-decoration:none;font-weight:600;font-size:14px;padding:11px 20px;border-radius:999px;margin:4px">Google Sheet</a></div>'
        '</div></div>')
    with open(out, "w", encoding="utf-8") as f:
        f.write(body)
    subject = (("💬 " if rep_today else "📊 ") + f"MarketForge — {jour} · +{len(new)} fiches · {sent_today} envois"
               + (f" · {rep_total} réponse(s)" if rep_total else ""))
    print(subject)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "daily_report.html")

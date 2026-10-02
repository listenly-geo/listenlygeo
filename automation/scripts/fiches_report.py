#!/usr/bin/env python3
"""
Rapport du soir « Fiches + indexation Google » (02/10/2026). Moteur trafic uniquement, pas de prospection.

  python3 automation/scripts/fiches_report.py --candidates 60     -> fiches non indexees, jamais proposees (a choisir : les plus connues)
  python3 automation/scripts/fiches_report.py --commit URL1 ... URL10  -> enregistre les 10 du jour (data/index_requests.json)
  python3 automation/scripts/fiches_report.py /tmp/fiches.html          -> HTML du mail ; derniere ligne imprimee = objet

Regles : ne JAMAIS reproposer une fiche deja donnee (index_requests.json) ; ne jamais proposer une fiche deja indexee.
"""
import sys, json, html, datetime, urllib.parse

P = "pages/podcast-btb/data"
REQ = f"{P}/index_requests.json"
GSC = "https://search.google.com/u/1/search-console/inspect?resource_id=sc-domain%3Alistenly.fr&id="


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def today():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=2)).date().isoformat()


def given():
    return {u for v in load(REQ, {}).values() for u in v}


def candidates(n):
    if today() in load(REQ, {}):
        print(f"LISTE DU JOUR DEJA ENREGISTREE ({today()}) : ne rien choisir ni enregistrer, passer au rapport.")
        return
    pods = load(f"{P}/podcasts.json", [])
    st = load(f"{P}/gsc_hub_status.json", {})
    gp = load(f"{P}/gsc_pages.json", {}).get("pages", {})
    seen = load("automation/data/discovery_seen_history.json", {})
    tracks = {}
    for v in seen.values():
        tracks[(v.get("podcast_name") or "").lower()[:30]] = v.get("track_count", 0)
    done = given()
    rows = []
    for r in pods:
        u = r["fiche_url"]
        slug = u.rsplit("/", 1)[-1].replace(".html", "")
        s = st.get(slug[:-8] if slug.endswith("-podcast") else slug) or st.get(slug) or {}
        if s.get("indexed_on") or s.get("verdict") == "PASS" or u in done:
            continue
        imp = (gp.get(u) or {}).get("impressions", 0)
        rows.append((imp, tracks.get(r["podcast_name"].lower()[:30], 0), r["podcast_name"], u, s.get("coverage", "non inspectee")))
    rows.sort(key=lambda x: (-x[0], -x[1]))
    for imp, tc, name, u, cov in rows[:n]:
        print(f"{imp}\t{tc}\t{name}\t{cov}\t{u}")


def commit(urls):
    d = load(REQ, {})
    if today() in d:
        print(f"Liste du {today()} deja enregistree : inchangee.")
        return
    d[today()] = urls
    with open(REQ, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print(f"{len(urls)} fiches enregistrees pour {today()}")


def report(out):
    t = today()
    fr = datetime.date.fromisoformat(t).strftime("%d/%m/%Y")
    pods = load(f"{P}/podcasts.json", [])
    names = {p["fiche_url"]: p["podcast_name"] for p in pods}
    w = load(f"{P}/seo_watch.json", {})
    hist = w.get("history", [])
    cur = hist[-1] if hist else {}
    prev = hist[-2] if len(hist) > 1 else {}
    st = load(f"{P}/gsc_hub_status.json", {})
    q = load("automation/marketforge_engine/queue.json", {}).get("journal", {}).get(t, {})
    new_today = sum(1 for p in pods if str(p.get("date", ""))[:10] == t)
    d7 = (datetime.date.fromisoformat(t) - datetime.timedelta(days=6)).isoformat()
    week = sum(1 for p in pods if str(p.get("date", ""))[:10] >= d7)
    newly = [k for k, v in st.items() if v.get("indexed_on") == t]

    def delta(k):
        a, b = cur.get(k, 0), prev.get(k)
        return f" ({'+' if a - b >= 0 else ''}{a - b} vs hier)" if b is not None else ""

    css = ("body{margin:0;background:#f5f5f7;font-family:-apple-system,Helvetica,Arial,sans-serif;color:#1d1d1f}"
           ".w{max-width:640px;margin:0 auto;padding:24px 16px}.c{background:#fff;border-radius:16px;padding:20px 22px;margin:0 0 14px}"
           "h1{font-size:24px;margin:0 0 4px}h2{font-size:17px;margin:0 0 10px}p,li{font-size:14px;line-height:1.6}ul{margin:6px 0 0;padding-left:20px}"
           ".k{display:inline-block;min-width:130px;margin:4px 14px 4px 0}.k b{display:block;font-size:26px}.k span{font-size:12px;color:#6e6e73}"
           ".b{display:inline-block;background:#0071e3;color:#fff;text-decoration:none;font-weight:600;font-size:12px;padding:5px 12px;border-radius:999px}"
           ".m{color:#6e6e73;font-size:12px}")
    kpi = lambda v, l: f'<div class="k"><b>{v}</b><span>{l}</span></div>'
    h = [f"<html><head><meta charset='utf-8'><style>{css}</style></head><body><div class='w'>",
         f"<div class='c'><h1>Fiches & Google — {fr}</h1><p class='m'>Moteur trafic : combien de fiches, combien Google en a indexé.</p>"
         + kpi(len(pods), "fiches en ligne") + kpi(new_today, "créées aujourd'hui") + kpi(week, "créées sur 7 jours")
         + kpi(cur.get("hubs_indexed", "—"), "fiches indexées par Google") + "</div>"]
    h.append("<div class='c'><h2>Indexation Google</h2><ul>"
             f"<li>Fiches indexées : <b>{cur.get('hubs_indexed', '—')}</b> sur {cur.get('hubs_checked', '—')} vérifiées{delta('hubs_indexed')}</li>"
             f"<li>Pages questions indexées : <b>{cur.get('questions_indexed', '—')}</b>{delta('questions_indexed')}</li>"
             f"<li>Fiches visibles dans Google : <b>{cur.get('hubs_with_impressions', '—')}</b> · impressions : <b>{cur.get('hub_impressions', '—')}</b>{delta('hub_impressions')} · clics : <b>{cur.get('hub_clicks', '—')}</b></li>"
             + (f"<li>Nouvellement indexées aujourd'hui : {html.escape(', '.join(newly[:8]))}</li>" if newly else "")
             + (f"<li>{q.get('episodes', 0)} épisodes transcrits aujourd'hui ({q.get('moments', 0)} questions extraites)</li>" if q else "")
             + "</ul></div>")
    urls = load(REQ, {}).get(t, [])
    rows = "".join(
        f"<tr><td style='padding:8px 0;border-bottom:1px solid #f0f0f3;font-size:13px'>{i}. {html.escape(names.get(u, u))}</td>"
        f"<td style='text-align:right;border-bottom:1px solid #f0f0f3'><a class='b' href='{GSC}{urllib.parse.quote(u, safe='')}'>Demander l'indexation →</a></td></tr>"
        for i, u in enumerate(urls, 1)) or "<tr><td class='m'>Liste du jour pas encore prête.</td></tr>"
    h.append("<div class='c'><h2>Les 10 fiches à faire indexer aujourd'hui</h2>"
             "<p class='m'>Les plus connues, pas encore indexées, jamais proposées. Clique, puis « Demander une indexation ».</p>"
             f"<table style='width:100%;border-collapse:collapse'>{rows}</table></div>")
    h.append("</div></body></html>")
    with open(out, "w", encoding="utf-8") as f:
        f.write("".join(h))
    print(f"Fiches & Google {fr} — {cur.get('hubs_indexed', '—')} indexées · +{new_today} fiches · 10 à indexer")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--candidates":
        candidates(int(a[1]) if len(a) > 1 else 60)
    elif a and a[0] == "--commit":
        commit(a[1:])
    else:
        report(a[0] if a else "/tmp/fiches.html")

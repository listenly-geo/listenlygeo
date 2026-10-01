#!/usr/bin/env python3
"""
Tableau de bord MarketForge Engine (fiches hub N1 + prospects + regroupement Google).
Genere pages/podcast-btb/moteur.html (noindex) a chaque run du moteur et de la consolidation.

  python automation/scripts/build_engine_dashboard.py
"""
import os, json, html, datetime, collections, math

PAGES = "pages/podcast-btb"
OUT = f"{PAGES}/moteur.html"
UNIVERS_PODCASTS = 3_200_000  # taille du marche vise (podcasts B2B dans le monde) - a ajuster si besoin


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def e(s):
    return html.escape(str(s or ""), quote=True)


def fr_num(n):
    return f"{int(n):,}".replace(",", " ")


DAYS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def fr_date(d):
    return f"{d.day} {MONTHS[d.month - 1]}"


def main():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=2)  # heure de Paris/Berlin (ete)
    today = now.date()
    podcasts = load(f"{PAGES}/data/podcasts.json", [])
    queue = load("automation/marketforge_engine/queue.json", {"podcasts": {}, "journal": {}})
    config = load("automation/marketforge_engine/config.json", {})
    consolidated = load(f"{PAGES}/data/consolidated_questions.json", {"paths": []})
    status = load(f"{PAGES}/data/gsc_index_status.json", {"urls": {}, "impressions": {}})
    gsc_pages = load(f"{PAGES}/data/gsc_pages.json", {"pages": {}}).get("pages", {})

    # --- Fiches hub ---
    by_day = collections.Counter(str(p.get("date", ""))[:10] for p in podcasts)
    total = len(podcasts)
    today_n = by_day.get(today.isoformat(), 0)
    last7 = sum(by_day.get((today - datetime.timedelta(days=i)).isoformat(), 0) for i in range(7))
    days14 = [today - datetime.timedelta(days=i) for i in range(13, -1, -1)]
    series = [(d, by_day.get(d.isoformat(), 0)) for d in days14]
    vmax = max([v for _, v in series] + [1])

    bars = []
    for d, v in series:
        h = max(2, round(v / vmax * 100)) if v else 0
        label = f"{DAYS[d.weekday()]} {fr_date(d)} : {v} fiche{'s' if v > 1 else ''}"
        bars.append(
            f'<div class="bar-col" tabindex="0" aria-label="{e(label)}">'
            f'<div class="tip">{e(label)}</div>'
            f'<div class="bar-track"><div class="bar{" today" if d == today else ""}" style="height:{h}%"></div></div>'
            f'<div class="bar-x">{d.day}</div></div>')

    # --- Indexation Google des fiches hub (statut Search Console, releve par le moteur) ---
    hub_status = load(f"{PAGES}/data/gsc_hub_status.json", {})
    hub_idx = sum(1 for v in hub_status.values() if v.get("indexed_on"))
    hub_refused = sum(1 for v in hub_status.values() if str(v.get("coverage", "")).startswith("Crawled"))
    hub_unknown = sum(1 for v in hub_status.values() if "unknown" in str(v.get("coverage", "")).lower())
    hub_checked = sum(1 for v in hub_status.values() if v.get("date"))
    hub_pct = round(hub_idx / total * 100) if total else 0
    cohorts = collections.OrderedDict()
    for p in sorted(podcasts, key=lambda p: str(p.get("date", ""))):
        m = str(p.get("date", ""))[:7]
        if not m:
            continue
        c = cohorts.setdefault(m, [0, 0])
        c[0] += 1
        c[1] += 1 if hub_status.get(p.get("slug"), {}).get("indexed_on") else 0
    MOIS = {"01": "janv.", "02": "févr.", "03": "mars", "04": "avr.", "05": "mai", "06": "juin", "07": "juil.",
            "08": "août", "09": "sept.", "10": "oct.", "11": "nov.", "12": "déc."}
    cohort_rows = "".join(
        f'<div><span>Créées en {MOIS.get(m[5:], m[5:])} {m[:4]} ({fr_num(n)})</span><b>{fr_num(i)} indexées · {round(i / n * 100)} %</b></div>'
        for m, (n, i) in list(cohorts.items())[-4:])

    # --- Regroupement Google ---
    redirected = len(consolidated.get("paths", []))
    q_total = 0
    for root, _dirs, files in os.walk(f"{PAGES}/questions"):
        q_total += sum(1 for f in files if f.endswith(".html") and f != "index.html")
    inspected = len(status.get("urls", {}))
    indexed = sum(1 for v in status.get("urls", {}).values()
                  if v.get("verdict") == "PASS")
    with_imp = sum(1 for v in status.get("impressions", {}).values() if v.get("impressions", 0) > 0)
    remaining = max(q_total - redirected, 0)
    pct_done = round(redirected / q_total * 100) if q_total else 0
    phase = consolidated.get("phase", load("automation/data/consolidation_config.json", {}).get("phase", 1))

    # --- Visibilite Google des hubs ---
    hub_rows = []
    for url, v in gsc_pages.items():
        if url.endswith("-podcast.html") and "/questions/" not in url:
            hub_rows.append((v.get("impressions", 0), v.get("clicks", 0), url))
    hub_rows.sort(reverse=True)
    hub_imp = sum(r[0] for r in hub_rows)
    names = {p.get("fiche_url"): p.get("podcast_name") for p in podcasts}
    top_hubs = "".join(
        f'<li><a href="{e(u)}" target="_blank" rel="noopener">{e(names.get(u) or u.rsplit("/", 1)[-1])}</a>'
        f'<span class="num">{fr_num(i)} <small>impr.</small></span></li>'
        for i, c, u in hub_rows[:6]) or '<li class="muted">Pas encore de données Search Console pour les hubs.</li>'

    # --- Dernieres fiches ---
    recent = sorted(podcasts, key=lambda p: str(p.get("date", "")), reverse=True)[:24]
    cards = []
    for p in recent:
        try:
            dd = fr_date(datetime.date.fromisoformat(str(p.get("date"))[:10]))
        except ValueError:
            dd = ""
        cover = f'<img src="{e(p.get("cover_image"))}" alt="" loading="lazy">' if p.get("cover_image") else '<div class="ph"></div>'
        cards.append(
            f'<a class="item" href="{e(p.get("fiche_url"))}" target="_blank" rel="noopener">{cover}'
            f'<div class="meta"><div class="t">{e(p.get("podcast_name"))}</div>'
            f'<div class="s">{e(p.get("categorie"))} · {dd}</div></div></a>')

    running = not config.get("pause")
    pill = ('<span class="state on"><i></i>En marche</span>' if running
            else '<span class="state off"><i></i>En pause</span>')

    doc = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Moteur trafic</title>
<style>
:root {{
  --bg:#f5f5f7; --card:#ffffff; --ink:#1d1d1f; --ink2:#6e6e73; --ink3:#86868b;
  --line:#e5e5ea; --accent:#0071e3; --accent-soft:#e8f1fc; --track:#f0f0f3;
  --ok:#1f7a3a; --ok-soft:#e6f4ea; --shadow:0 1px 2px rgba(0,0,0,.04),0 8px 24px rgba(0,0,0,.04);
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#000; --card:#1c1c1e; --ink:#f5f5f7; --ink2:#a1a1a6; --ink3:#8e8e93;
    --line:#2c2c2e; --accent:#2997ff; --accent-soft:#0a2a4a; --track:#2c2c2e;
    --ok:#30d158; --ok-soft:#0f2e19; --shadow:none; }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.45 -apple-system,BlinkMacSystemFont,"SF Pro Text","Inter","Helvetica Neue",Arial,sans-serif;
  -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:56px 24px 80px; }}
header {{ display:flex; align-items:flex-end; justify-content:space-between; gap:16px; flex-wrap:wrap; margin-bottom:36px; }}
.eyebrow {{ color:var(--ink3); font-size:13px; font-weight:600; letter-spacing:.02em; margin:0 0 6px; }}
h1 {{ font-size:44px; line-height:1.05; letter-spacing:-.025em; margin:0; font-weight:700; }}
.sub {{ color:var(--ink2); margin:10px 0 0; font-size:17px; }}
.actions {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
.btn {{ display:inline-flex; align-items:center; font-size:13px; font-weight:600; padding:8px 16px; border-radius:999px;
  background:var(--accent); color:#fff; text-decoration:none; transition:opacity .15s; }}
.btn:hover {{ opacity:.85; }}
.state {{ display:inline-flex; align-items:center; gap:8px; font-size:13px; font-weight:600; padding:7px 14px;
  border-radius:999px; background:var(--card); box-shadow:var(--shadow); border:1px solid var(--line); }}
.state i {{ width:8px; height:8px; border-radius:50%; background:var(--ink3); }}
.state.on i {{ background:#34c759; box-shadow:0 0 0 4px rgba(52,199,89,.18); }}
h2 {{ font-size:22px; letter-spacing:-.015em; margin:48px 0 16px; font-weight:650; }}
.hero {{ text-align:center; padding:28px 24px 32px; }}
.hero-num {{ font-size:96px; line-height:1; font-weight:800; letter-spacing:-.03em; font-variant-numeric:tabular-nums; }}
.hero-den {{ font-size:40px; font-weight:600; color:var(--ink3); }}
.hero-label {{ margin-top:10px; color:var(--ink2); font-size:16px; font-weight:500; }}
@media (max-width:860px) {{ .hero-num {{ font-size:64px; }} .hero-den {{ font-size:28px; }} }}
.grid {{ display:grid; gap:16px; grid-template-columns:repeat(4,1fr); }}
.card {{ background:var(--card); border-radius:20px; padding:22px 24px; box-shadow:var(--shadow); border:1px solid var(--line); }}
.kpi .label {{ color:var(--ink2); font-size:13px; font-weight:500; }}
.kpi .value {{ font-size:40px; font-weight:700; letter-spacing:-.03em; margin-top:6px; font-variant-numeric:tabular-nums; }}
.kpi .hint {{ color:var(--ink3); font-size:13px; margin-top:2px; }}
.two {{ display:grid; gap:16px; grid-template-columns:1.6fr 1fr; }}
.chart-head {{ display:flex; justify-content:space-between; align-items:baseline; margin-bottom:18px; }}
.chart-head b {{ font-size:15px; }} .chart-head span {{ color:var(--ink3); font-size:13px; }}
.bars {{ display:flex; gap:6px; height:180px; align-items:stretch; }}
.bar-col {{ flex:1; display:flex; flex-direction:column; position:relative; outline:none; cursor:default; }}
.bar-track {{ flex:1; display:flex; align-items:flex-end; border-bottom:1px solid var(--line); }}
.bar {{ width:100%; background:var(--accent); opacity:.35; border-radius:4px 4px 0 0; transition:opacity .15s; }}
.bar.today {{ opacity:1; }}
.bar-col:hover .bar, .bar-col:focus .bar {{ opacity:1; }}
.bar-x {{ text-align:center; font-size:11px; color:var(--ink3); margin-top:6px; font-variant-numeric:tabular-nums; }}
.tip {{ position:absolute; bottom:calc(100% - 8px); left:50%; transform:translateX(-50%); white-space:nowrap;
  background:var(--ink); color:var(--bg); font-size:12px; padding:5px 9px; border-radius:8px; opacity:0;
  pointer-events:none; transition:opacity .12s; z-index:2; }}
.bar-col:hover .tip, .bar-col:focus .tip {{ opacity:1; }}
.stack > div {{ display:flex; justify-content:space-between; padding:13px 0; border-bottom:1px solid var(--line); }}
.stack > div:last-child {{ border-bottom:0; }}
.stack span {{ color:var(--ink2); }} .stack b {{ font-variant-numeric:tabular-nums; }}
.progress {{ height:8px; background:var(--track); border-radius:99px; overflow:hidden; margin:14px 0 6px; }}
.progress > div {{ height:100%; background:var(--accent); border-radius:99px; }}
.muted {{ color:var(--ink3); }}
ul.rank {{ list-style:none; margin:0; padding:0; }}
ul.rank li {{ display:flex; justify-content:space-between; gap:12px; padding:11px 0; border-bottom:1px solid var(--line); }}
ul.rank li:last-child {{ border-bottom:0; }}
ul.rank a {{ color:var(--ink); text-decoration:none; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
ul.rank a:hover {{ color:var(--accent); }}
.num {{ font-variant-numeric:tabular-nums; font-weight:600; white-space:nowrap; }} .num small {{ color:var(--ink3); font-weight:400; }}
.list {{ display:grid; grid-template-columns:repeat(2,1fr); gap:10px; }}
.item {{ display:flex; align-items:center; gap:14px; padding:12px 14px; background:var(--card); border-radius:16px;
  border:1px solid var(--line); text-decoration:none; color:var(--ink); transition:transform .15s, box-shadow .15s; min-width:0; }}
.item:hover {{ transform:translateY(-1px); box-shadow:var(--shadow); }}
.item img, .item .ph {{ width:48px; height:48px; border-radius:10px; object-fit:cover; flex:none; background:var(--track); }}
.meta {{ flex:1; min-width:0; }}
.meta .t {{ font-weight:600; font-size:14px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.meta .s {{ color:var(--ink3); font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.pill {{ font-size:11px; font-weight:600; padding:4px 9px; border-radius:99px; background:var(--track); color:var(--ink2); white-space:nowrap; }}
.pill.ok {{ background:var(--ok-soft); color:var(--ok); }}
.pill.warn {{ background:#fdecea; color:#a3271d; }}
@media (prefers-color-scheme: dark) {{ .pill.warn {{ background:#3a1a17; color:#ff6b5b; }} }}
table.track {{ width:100%; border-collapse:collapse; font-size:14px; }}
table.track th {{ text-align:left; font-size:12px; font-weight:600; color:var(--ink3); text-transform:uppercase;
  letter-spacing:.03em; padding:14px 24px; border-bottom:1px solid var(--line); }}
table.track td {{ padding:13px 24px; border-bottom:1px solid var(--line); vertical-align:middle; }}
table.track tr:last-child td {{ border-bottom:0; }}
table.track td.t1 {{ font-weight:600; max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
table.track td.t1 a {{ color:inherit; text-decoration:none; }}
table.track td.t1 a:hover {{ color:var(--accent); text-decoration:underline; }}
table.track td.t3 {{ color:var(--ink2); }}
table.track tbody tr:hover {{ background:var(--track); }}
footer {{ margin-top:56px; color:var(--ink3); font-size:12px; text-align:center; }}
footer a {{ color:var(--ink2); }}
@media (max-width:860px) {{
  .grid {{ grid-template-columns:repeat(2,1fr); }} .two, .list {{ grid-template-columns:1fr; }}
  h1 {{ font-size:34px; }} .wrap {{ padding:32px 16px 60px; }} .kpi .value {{ font-size:32px; }}
}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <p class="eyebrow">Moteur trafic · Listenly</p>
      <h1>Tableau de bord</h1>
      <p class="sub">Fiches hub et visibilité Google — mis à jour le {fr_date(today)} à {now:%H:%M}.</p>
    </div>
    <div class="actions">
      <a class="btn" href="https://docs.google.com/spreadsheets/d/1b53cWGiz6iOuakpotw_Ck4bQBeIMJa3hfq5gP2mFiT4/edit" target="_blank" rel="noopener">Ouvrir le Google Sheet ↗</a>
      {pill}
    </div>
  </header>

  <div class="hero">
    <div class="hero-num">{fr_num(total)}<span class="hero-den"> / {f"{UNIVERS_PODCASTS / 1_000_000:.1f}".replace(".", ",")} M</span></div>
    <div class="hero-label">podcasts référencés</div>
  </div>

  <h2>Indexation Google des fiches hub</h2>
  <div class="two">
    <div class="card">
      <div class="chart-head"><b>Fiches hub indexées par Google</b><span>Statut Search Console</span></div>
      <div class="kpi"><div class="value">{fr_num(hub_idx)} <span class="muted" style="font-size:20px;font-weight:500">/ {fr_num(total)}</span></div></div>
      <div class="progress"><div style="width:{hub_pct}%"></div></div>
      <div class="muted" style="font-size:13px">{hub_pct} % des fiches hub sont dans Google · {fr_num(hub_unknown)} encore inconnues de Google · {fr_num(hub_refused)} explorées mais refusées</div>
    </div>
    <div class="card stack">
      <div><span>Fiches hub vérifiées dans Search Console</span><b>{fr_num(hub_checked)} / {fr_num(total)}</b></div>
      {cohort_rows}
    </div>
  </div>

  <h2>Production</h2>
  <div class="two">
    <div class="card">
      <div class="chart-head"><b>Fiches hub créées par jour</b><span>14 derniers jours</span></div>
      <div class="bars" role="img" aria-label="Fiches hub créées par jour sur 14 jours">{''.join(bars)}</div>
    </div>
    <div class="card stack">
      <div><span>Fiches hub au total</span><b>{fr_num(total)}</b></div>
      <div><span>Créées aujourd'hui</span><b>{fr_num(today_n)}</b></div>
      <div><span>Créées ces 7 derniers jours</span><b>{fr_num(last7)}</b></div>
      <div><span>Découverte par passage</span><b>{config.get("decouverte_max_par_jour", "—")} max</b></div>
    </div>
  </div>

  <h2>Regroupement dans les hubs</h2>
  <div class="two">
    <div class="card">
      <div class="chart-head"><b>Anciennes fiches question regroupées</b><span>Phase {phase}</span></div>
      <div class="kpi"><div class="value">{fr_num(redirected)} <span class="muted" style="font-size:20px;font-weight:500">/ {fr_num(q_total)}</span></div></div>
      <div class="progress"><div style="width:{pct_done}%"></div></div>
      <div class="muted" style="font-size:13px">{pct_done} % redirigées vers le hub de leur podcast · {fr_num(remaining)} encore en ligne</div>
    </div>
    <div class="card stack">
      <div><span>Fiches question vérifiées dans Search Console</span><b>{fr_num(inspected)} / {fr_num(q_total)}</b></div>
      <div><span>Dont indexées (protégées)</span><b>{fr_num(indexed)}</b></div>
      <div><span>Gardées (ont des impressions)</span><b>{fr_num(with_imp)}</b></div>
    </div>
  </div>

  <h2>Visibilité Google des hubs</h2>
  <div class="two">
    <div class="card">
      <div class="chart-head"><b>Hubs les plus vus</b><span>{fr_num(hub_imp)} impressions · période Search Console</span></div>
      <ul class="rank">{top_hubs}</ul>
    </div>
    <div class="card stack">
      <div><span>Hubs visibles dans Google</span><b>{fr_num(len(hub_rows))}</b></div>
      <div><span>Impressions des hubs</span><b>{fr_num(hub_imp)}</b></div>
      <div><span>Clics des hubs</span><b>{fr_num(sum(r[1] for r in hub_rows))}</b></div>
    </div>
  </div>

  <h2>Dernières fiches hub</h2>
  <div class="list">{''.join(cards)}</div>

  <footer>Généré automatiquement à chaque passage du moteur · <a href="index.html">Annuaire des podcasts</a></footer>
</div>
</body>
</html>
"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"[engine-dashboard] {OUT} : {total} hubs, {today_n} aujourd'hui, {hub_idx} indexées.")


if __name__ == "__main__":
    main()

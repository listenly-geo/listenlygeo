#!/usr/bin/env python3
"""
Regroupement des fiches question dans leur hub N1 (27/09/2026) — sans casser l'indexation.

Contexte : ~2 700 fiches question (questions/<podcast>/<question>.html) diluent le site ;
Google en laisse ~1 560 en "Detectee, actuellement non indexee". Strategie Hub : la fiche N1
du podcast contient deja toutes les requetes -> chaque fiche question est redirigee (301)
vers son hub, par phases, en s'appuyant sur l'etat REEL d'indexation (API Search Console).

  python hub_consolidation.py inspect   : inspecte (URL Inspection API) les fiches question
                                          pas encore verifiees, max INSPECT_MAX/run (quota 2000/j)
                                          + impressions 16 mois (Search Analytics)
  python hub_consolidation.py apply     : calcule la liste a regrouper selon la phase,
                                          ecrit data/consolidated_questions.json + bloc .htaccess

Phases (automation/data/consolidation_config.json) :
  phase 1 : seulement les fiches NON indexees ET sans aucune impression (zero risque)
  phase 2 : + les fiches indexees sans aucune impression (la 301 transmet leur valeur au hub)
  Jamais : une fiche qui a eu des impressions (elle reste en ligne telle quelle).
"""
import os, re, sys, json, glob, time, datetime, urllib.request, urllib.error, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_gsc_stats import get_access_token  # noqa: E402  (meme compte de service GSC)

PAGES = "pages/podcast-btb"
BASE = "https://listenly.fr/podcast-btb/"
SITE = os.environ.get("GSC_SITE_URL", "sc-domain:listenly.fr")
STATUS_FILE = f"{PAGES}/data/gsc_index_status.json"
OUT_FILE = f"{PAGES}/data/consolidated_questions.json"
CONFIG_FILE = "automation/data/consolidation_config.json"
HTACCESS = f"{PAGES}/.htaccess"
BEGIN, END = "# BEGIN hub-consolidation (genere par hub_consolidation.py)", "# END hub-consolidation"
INSPECT_MAX = int(os.environ.get("INSPECT_MAX", "1800"))


def log(m):
    print(f"[hub-consolidation] {m}", flush=True)


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def save(p, data):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def question_paths():
    out = []
    for f in glob.glob(f"{PAGES}/questions/*/*.html"):
        if f.endswith("/index.html"):
            continue
        out.append(os.path.relpath(f, PAGES).replace(os.sep, "/"))
    return sorted(out)


def api(token, url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def inspect():
    token = get_access_token(json.loads(os.environ["GSC_SERVICE_ACCOUNT_JSON"]))
    status = load(STATUS_FILE, {"urls": {}, "impressions": {}, "updated": ""})

    # 1) impressions sur ~16 mois (toutes les pages questions/ ayant ete vues au moins une fois)
    end = datetime.date.today()
    start = end - datetime.timedelta(days=480)
    res = api(token, f"https://www.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(SITE, safe='')}/searchAnalytics/query",
              {"startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": ["page"], "rowLimit": 25000,
               "dimensionFilterGroups": [{"filters": [{"dimension": "page", "operator": "contains", "expression": "/podcast-btb/questions/"}]}]})
    imp = {row["keys"][0].replace(BASE, ""): {"impressions": row.get("impressions", 0), "clicks": row.get("clicks", 0)}
           for row in res.get("rows", [])}
    status["impressions"] = imp
    log(f"{len(imp)} fiche(s) question avec au moins une impression sur 16 mois.")

    # 2) inspection des fiches pas encore verifiees (ou verifiees il y a > 14 jours)
    limit = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
    todo = [p for p in question_paths() if status["urls"].get(p, {}).get("date", "") < limit]
    log(f"{len(todo)} fiche(s) a inspecter, {min(len(todo), INSPECT_MAX)} ce run.")
    done = 0
    for p in todo[:INSPECT_MAX]:
        try:
            r = api(token, "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
                    {"inspectionUrl": BASE + p, "siteUrl": SITE})
            ir = r.get("inspectionResult", {}).get("indexStatusResult", {})
            status["urls"][p] = {"verdict": ir.get("verdict", ""), "coverage": ir.get("coverageState", ""),
                                 "date": datetime.date.today().isoformat()}
            done += 1
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")[:200]
            if e.code == 429 or "quota" in body.lower():
                log(f"Quota atteint apres {done} inspection(s) — reprise au prochain run.")
                break
            log(f"Erreur {e.code} sur {p} : {body}")
        if done % 100 == 0 and done:
            save(STATUS_FILE, status)
            log(f"... {done} inspectee(s)")
        time.sleep(0.15)
    status["updated"] = datetime.datetime.utcnow().isoformat(timespec="minutes")
    save(STATUS_FILE, status)
    counts = {}
    for v in status["urls"].values():
        counts[v.get("coverage") or "?"] = counts.get(v.get("coverage") or "?", 0) + 1
    log(f"Inspection : {done} ce run. Etat connu : {counts}")


def is_indexed(v):
    cov = (v.get("coverage") or "").lower()
    return v.get("verdict") == "PASS" or ("indexed" in cov and "not indexed" not in cov)


def apply():
    cfg = load(CONFIG_FILE, {"phase": 1})
    phase = int(cfg.get("phase", 1))
    status = load(STATUS_FILE, {"urls": {}, "impressions": {}})
    keep = set(cfg.get("toujours_garder", []))
    chosen, kept_imp, kept_idx, unknown = [], 0, 0, 0
    for p in question_paths():
        pod = p.split("/")[1]
        if not os.path.exists(f"{PAGES}/{pod}-podcast.html"):
            continue  # pas de hub cible -> on ne touche pas
        if p in keep or status["impressions"].get(p, {}).get("impressions", 0) > 0:
            kept_imp += 1
            continue
        v = status["urls"].get(p)
        if not v:
            unknown += 1
            continue  # pas encore inspectee -> on attend
        if is_indexed(v):
            if phase < 2:
                kept_idx += 1
                continue
        chosen.append(p)

    previous = set(load(OUT_FILE, {}).get("paths", []))
    paths = sorted(set(chosen) | previous)  # jamais de retour arriere automatique
    save(OUT_FILE, {"phase": phase, "updated": datetime.date.today().isoformat(), "count": len(paths), "paths": paths})

    rules = [BEGIN, "# Fiches question regroupees dans le hub N1 de leur podcast (redirection permanente).", "RewriteEngine On"]
    for p in paths:
        pod, q = p.split("/")[1], p.split("/")[2]
        pat = "^questions/" + re.escape(pod) + "/" + re.escape(q) + "$"
        rules.append(f"RewriteRule {pat} /podcast-btb/{pod}-podcast.html [R=301,L]")
    rules.append(END)
    with open(HTACCESS, encoding="utf-8") as f:
        ht = f.read()
    if BEGIN in ht:
        ht = ht[:ht.index(BEGIN)] + ht[ht.index(END) + len(END):].lstrip("\n")
    ht = ht.rstrip("\n") + "\n\n" + "\n".join(rules) + "\n"
    with open(HTACCESS, "w", encoding="utf-8") as f:
        f.write(ht)
    log(f"Phase {phase} : {len(paths)} fiche(s) regroupee(s) (dont {len(set(chosen) - previous)} nouvelle(s)) | "
        f"gardees : {kept_imp} avec impressions, {kept_idx} indexees (phase 2 plus tard) | {unknown} pas encore inspectee(s).")
    # Sitemaps regeneres sans les fiches regroupees (sitemap-questions.xml se vide progressivement)
    for k in ("ANTHROPIC_API_KEY", "PODCAST_RAW_INFO", "PODCAST_URL", "CONTACT_URL", "LISTENLY_URL"):
        os.environ.setdefault(k, "unused")
    import importlib.util
    spec = importlib.util.spec_from_file_location("gpb", os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate_podcast_btb.py"))
    gpb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gpb)
    gpb.build_sitemap()
    print(f"::notice title=Consolidation::Phase {phase} : {len(paths)} fiches regroupees vers leur hub ; "
          f"{kept_imp} gardees (impressions), {kept_idx} indexees gardees, {unknown} en attente d'inspection.")


if __name__ == "__main__":
    {"inspect": inspect, "apply": apply}[sys.argv[1]]()

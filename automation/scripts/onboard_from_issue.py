#!/usr/bin/env python3
"""
MarketForge Engine — onboarding automatique d'un candidat (issue GitHub "candidate") :
  1. cree la fiche podcast sur Listenly (SQL via api/podcast-show-import.php) -> lien Listenly
  2. genere la fiche N1 (generate_podcast_btb.py, inchange) -> podcasts.json
  3. commente + ferme l'issue (label "onboarded")
La fiche N1 entre ensuite toute seule dans la file d'extraction (marketforge_extract_queue.py).

Remplace les etapes manuelles du generateur HTML : lien Listenly admin + YAML + run.

Variables :
  ANTHROPIC_API_KEY, KNOWLEDGE_IMPORT_SECRET, GH_TOKEN, GITHUB_REPOSITORY
  ISSUE_NUMBERS     : "12,15" | "all" (candidats labellises "approved") | "auto" (TOUS les candidats ouverts,
                      mode automatique du run complet MarketForge Engine)
  SHOW_IMPORT_MODE  : insert (defaut) | dry_run  (dry_run : rien n'est cree, ni fiche ni issue fermee)
  MAX_ONBOARD       : plafond par run (defaut 10)
"""
import os, sys, re, json, subprocess, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rss_contact import fetch_channel_info  # noqa: E402

REPO = os.environ.get("GITHUB_REPOSITORY", "listenly-geo/listenlygeo")
GH_TOKEN = os.environ.get("GH_TOKEN", "").strip()
SECRET = os.environ.get("KNOWLEDGE_IMPORT_SECRET", "").strip()
IMPORT_URL = os.environ.get("SHOW_IMPORT_URL", "https://listenly.fr/api/podcast-show-import.php")
RSS_READER_URL = os.environ.get("RSS_READER_URL", "https://listenly.fr/api/rss-reader-register.php")
MODE = (os.environ.get("SHOW_IMPORT_MODE") or "insert").strip()
MAX_ONBOARD = int(os.environ.get("MAX_ONBOARD") or "10")
PODCASTS_FILE = "pages/podcast-btb/data/podcasts.json"


def log(msg):
    print(f"[onboard] {msg}", flush=True)


def gh(method, path, payload=None):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        return json.loads(body) if body else {}


def parse_issue(issue):
    body = issue.get("body") or ""

    def field(label):
        m = re.search(r"\*\*" + re.escape(label) + r" :\*\*\s*(.*)", body)
        return m.group(1).strip().strip("`") if m else ""

    m = re.search(r"<!-- feed_url: (.*?) -->", body)
    reason = body.split("**Raison de qualification :**\n")[1].split("\n\n---")[0].strip() \
        if "**Raison de qualification :**\n" in body else ""
    email = field("Email")
    return {
        "issue_number": issue["number"],
        "podcast_name": re.sub(r"^🎙️\s*", "", issue["title"]).strip(),
        "feed_url": m.group(1).strip() if m else field("Flux RSS"),
        "artist_name": field("Éditeur/hôte"),
        "genre": field("Genre"),
        "language": field("Langue détectée") or "en",
        "apple_url": field("Fiche iTunes"),
        "cover_image": field("Image de couverture"),
        "email": "" if email.startswith("(") else email,
        "reason": reason,
    }


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:40].strip("-") or "podcast"


def create_listenly_show(c):
    payload = {"mode": MODE, "podcast": {
        "title": c["podcast_name"], "rss_url": c["feed_url"], "cover_image": c["cover_image"],
        "author": c["artist_name"], "email": c["email"], "language": c["language"],
        "description": c.get("description", "")}}
    req = urllib.request.Request(IMPORT_URL, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Import-Secret": SECRET,
                                          "User-Agent": "ListenlyGEO/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code} : {e.read().decode(errors='ignore')[:300]}"}


def register_rss_reader(feed_url):
    """Sans cette ligne, la fiche Listenly existe mais ses episodes ne sont jamais scrapes
    (le lecteur RSS de l'admin, table _c_p_rss_readers, ne connait le flux que si on l'y ajoute)."""
    if MODE != "insert" or not feed_url:
        return
    req = urllib.request.Request(
        RSS_READER_URL, data=json.dumps({"mode": "insert", "link": feed_url}).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-Import-Secret": SECRET, "User-Agent": "ListenlyGEO/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        res = {"ok": False, "error": f"HTTP {e.code} : {e.read().decode(errors='ignore')[:300]}"}
    except urllib.error.URLError as e:
        res = {"ok": False, "error": str(e)}
    log(f"Lecteur RSS : {json.dumps(res, ensure_ascii=False)[:200]}")
    return res


def generate_n1(c, listenly_url, slug):
    env = dict(os.environ)
    env.update({
        "RSS_URL": c["feed_url"], "PODCAST_URL": c["apple_url"], "LISTENLY_URL": listenly_url,
        "COVER_IMAGE": c["cover_image"], "PODCAST_SLUG": slug, "ACCENT_COLOR": "#2e8bd6",
        "LANGUAGE": c["language"] if c["language"] in ("fr", "en") else "en",
        "EPISODE_CTA_TARGET": "listenly",
    })
    env.pop("PODCAST_RAW_INFO", None)
    # Correctif 27/09/2026 : sur un run planifie (schedule), generate_podcast_btb.py voyait le fichier
    # .cron-paused et sortait sans rien faire (code 0) -> fiches Listenly creees sans fiche N1.
    env["GITHUB_EVENT_NAME"] = "workflow_dispatch"
    ok = subprocess.run([sys.executable, "automation/scripts/generate_podcast_btb.py"], env=env).returncode == 0
    return ok and os.path.exists(f"pages/podcast-btb/{slug}-podcast.html")  # verification reelle


def _norm_rss(u):
    return (u or "").strip().rstrip("/").lower().replace("http://", "https://")


def existing_by_rss():
    """flux RSS -> slug deja existant (anti-doublon : meme podcast sous un autre nom)."""
    try:
        with open(PODCASTS_FILE, encoding="utf-8") as f:
            return {_norm_rss(p.get("rss_url")): p["slug"] for p in json.load(f) if p.get("rss_url")}
    except (OSError, ValueError):
        return {}


def existing_slugs():
    try:
        with open(PODCASTS_FILE, encoding="utf-8") as f:
            return {p["slug"] for p in json.load(f)}
    except (OSError, ValueError):
        return set()


def main():
    if not SECRET or not GH_TOKEN:
        log("ERREUR : KNOWLEDGE_IMPORT_SECRET et GH_TOKEN requis.")
        sys.exit(1)
    wanted = (os.environ.get("ISSUE_NUMBERS") or "all").strip()
    if wanted == "all":
        issues = gh("GET", "/issues?labels=candidate,approved&state=open&per_page=100")
    elif wanted == "auto":
        issues = gh("GET", "/issues?labels=candidate&state=open&per_page=100&sort=created&direction=asc")
        # Auto-reparation : issues fermees "onboarded" dont la fiche N1 n'existe pas (run rate)
        slugs = existing_slugs()
        for i in gh("GET", "/issues?labels=onboarded&state=closed&per_page=50&sort=updated&direction=desc"):
            name = re.sub(r"^🎙️\s*", "", i.get("title", "")).strip()
            if slugify(name) not in slugs and not os.path.exists(f"pages/podcast-btb/{slugify(name)}-podcast.html"):
                i["state"] = "open"  # retraite (Listenly deja cree -> anti-doublon, seule la N1 est generee)
                issues.insert(0, i)
                log(f"Reparation : fiche N1 manquante pour '{name}' (issue #{i['number']}).")
    else:
        issues = [gh("GET", f"/issues/{n.strip()}") for n in wanted.split(",") if n.strip()]
    issues = [i for i in issues if not i.get("pull_request") and i.get("state") == "open"]
    log(f"{len(issues)} candidat(s) ouvert(s), plafond {MAX_ONBOARD} nouvelle(s) fiche(s) (mode {MODE}).")

    done, failed, report = [], [], []
    new_count = 0
    for issue in issues:
        c = parse_issue(issue)
        rss_slug = existing_by_rss().get(_norm_rss(c["feed_url"]))
        already = slugify(c["podcast_name"]) in existing_slugs() or bool(rss_slug)
        # Deja onboarde avant (fiche N1 existante, issue restee ouverte) : on le rattache a la file
        # et on ferme l'issue, sans consommer le quota du jour (aucun cout Claude).
        if not already and new_count >= MAX_ONBOARD:
            continue
        log(f"### #{c['issue_number']} {c['podcast_name']}")
        if not c["feed_url"]:
            failed.append(c["issue_number"]); log("Pas de flux RSS dans l'issue — ignore."); continue
        info = fetch_channel_info(c["feed_url"])
        c["email"] = c["email"] or info["email"]
        c["description"] = info["description"]  # description publique du RSS (jamais la raison interne)

        res = create_listenly_show(c)
        log(f"Listenly : {json.dumps(res, ensure_ascii=False)[:400]}")
        if not res.get("ok"):
            failed.append(c["issue_number"]); continue
        if MODE != "insert":
            continue
        register_rss_reader(c["feed_url"])
        listenly_url = res["listenly_url"]

        slug = rss_slug or slugify(c["podcast_name"])   # meme flux RSS -> on reutilise la fiche existante
        if not already:
            new_count += 1
        if slug in existing_slugs():
            log(f"Fiche N1 '{slug}' deja presente — pas de regeneration.")
        elif not generate_n1(c, listenly_url, slug):
            failed.append(c["issue_number"]); log("ECHEC generation N1."); continue

        created = "creee" if res.get("created") else "deja existante"
        gh("POST", f"/issues/{c['issue_number']}/comments", {"body": (
            f"✅ Onboardé automatiquement (MarketForge Engine)\n\n"
            f"- Fiche Listenly ({created}) : {listenly_url}\n"
            f"- Fiche N1 : https://listenly.fr/podcast-btb/{slug}-podcast.html\n"
            f"- Email : {c['email'] or '(aucun)'}\n\n"
            f"Entre automatiquement dans la file d'extraction.")})
        gh("POST", f"/issues/{c['issue_number']}/labels", {"labels": ["onboarded"]})
        gh("PATCH", f"/issues/{c['issue_number']}", {"state": "closed", "state_reason": "completed"})
        done.append(slug)
        report.append({"slug": slug, "podcast_name": c["podcast_name"], "email": c["email"],
                       "listenly_url": listenly_url, "listenly_created": bool(res.get("created")),
                       "fiche_url": f"https://listenly.fr/podcast-btb/{slug}-podcast.html"})

    log(f"Termine : {len(done)} onboarde(s) {done}, {len(failed)} echec(s) {failed}.")
    if MODE == "insert":  # lu par sheet_bridge.py pour le compte-rendu envoye au Google Sheet
        with open("automation/marketforge_engine/last_onboard.json", "w", encoding="utf-8") as f:
            json.dump({"onboarded": report, "failed_issues": failed}, f, ensure_ascii=False, indent=2)
    if failed and not done:
        sys.exit(1)


if __name__ == "__main__":
    main()

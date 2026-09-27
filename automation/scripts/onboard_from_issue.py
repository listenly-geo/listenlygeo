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
  ISSUE_NUMBERS     : "12,15" ou "all" (tous les candidats ouverts labellises "approved")
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


def generate_n1(c, listenly_url, slug):
    env = dict(os.environ)
    env.update({
        "RSS_URL": c["feed_url"], "PODCAST_URL": c["apple_url"], "LISTENLY_URL": listenly_url,
        "COVER_IMAGE": c["cover_image"], "PODCAST_SLUG": slug, "ACCENT_COLOR": "#2e8bd6",
        "LANGUAGE": c["language"] if c["language"] in ("fr", "en") else "en",
        "EPISODE_CTA_TARGET": "listenly",
    })
    env.pop("PODCAST_RAW_INFO", None)
    return subprocess.run([sys.executable, "automation/scripts/generate_podcast_btb.py"], env=env).returncode == 0


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
    else:
        issues = [gh("GET", f"/issues/{n.strip()}") for n in wanted.split(",") if n.strip()]
    issues = [i for i in issues if not i.get("pull_request") and i.get("state") == "open"][:MAX_ONBOARD]
    log(f"{len(issues)} candidat(s) a onboarder (mode {MODE}).")

    done, failed = [], []
    for issue in issues:
        c = parse_issue(issue)
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
        listenly_url = res["listenly_url"]

        slug = slugify(c["podcast_name"])
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

    log(f"Termine : {len(done)} onboarde(s) {done}, {len(failed)} echec(s) {failed}.")
    if failed and not done:
        sys.exit(1)


if __name__ == "__main__":
    main()

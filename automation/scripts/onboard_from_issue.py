#!/usr/bin/env python3
"""
MarketForge Engine — onboarding automatique d'un candidat (issue GitHub "candidate") — DB-ONLY (04/10/2026):
  1. cree la fiche podcast sur Listenly (SQL via api/podcast-show-import.php) -> lien Listenly
  2. enregistre le flux RSS pour scraping automatique (register_rss_reader)
  3. ajoute contact a la Sheet de prospection (via last_onboard.json + sheet_bridge.py push)
  4. commente + ferme l'issue (label "onboarded")

Aucune page HTML generee. Tout dans la DB Listenly.
Listenly scrape + extrait Q/R AUTOMATIQUEMENT sans intervention supplementaire.

Variables :
  KNOWLEDGE_IMPORT_SECRET, GH_TOKEN, GITHUB_REPOSITORY (ANTHROPIC_API_KEY pas utilisee ici)
  ISSUE_NUMBERS     : "12,15" | "all" (candidats labellises "approved") | "auto" (TOUS les candidats ouverts)
  SHOW_IMPORT_MODE  : insert (defaut) | dry_run
  MAX_ONBOARD       : plafond par run (defaut 10)
"""
import os, sys, re, json, subprocess, urllib.request, urllib.error
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rss_contact import fetch_channel_info  # noqa: E402

REPO = os.environ.get("GITHUB_REPOSITORY", "listenly-geo/listenlygeo")
GH_TOKEN = os.environ.get("GH_TOKEN", "").strip()
SECRET = os.environ.get("KNOWLEDGE_IMPORT_SECRET", "").strip()
IMPORT_URL = os.environ.get("SHOW_IMPORT_URL", "https://listenly.fr/api/podcast-show-import.php")
RSS_READER_URL = os.environ.get("RSS_READER_URL", "https://listenly.fr/api/rss-reader-register.php")
MODE = (os.environ.get("SHOW_IMPORT_MODE") or "insert").strip()
MAX_ONBOARD = int(os.environ.get("MAX_ONBOARD") or "10")
REQUIRE_EMAIL = os.environ.get("ONBOARD_REQUIRE_EMAIL", "1") == "1"   # sans email = inutile pour la prospection
FREE_MAIL = ("gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com", "icloud.com", "me.com", "aol.com")


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


# ARCHIVE 04/10/2026 : add_podcast_to_json, generate_episode_fiches, generate_n1 - DB-ONLY strategy
# Listenly scrape + extrait Q/R automatiquement dans sa DB. Aucune page HTML ou entry JSON generee.
# Voir git log pour l'historique complet.


# --- ARCHIVE 04/10/2026 : generate_n1 (creation fiche N1 HTML) mise en pause ---
# def generate_n1(c, listenly_url, slug):
#     """PIVOT 04/10/2026 : MISE EN PAUSE. Etait : genere la fiche N1 (page HTML hub).
#     Strategie Listenly-first : on ne cree PAS le Hub a l'onboarding, on le montre seulement
#     quand le prospect a dit oui a Listenly (etape BRIDGE/SALE du funnel).
#     """
#     env = dict(os.environ)
#     env.update({
#         "RSS_URL": c["feed_url"], "PODCAST_URL": c["apple_url"], "LISTENLY_URL": listenly_url,
#         "COVER_IMAGE": c["cover_image"], "PODCAST_SLUG": slug, "ACCENT_COLOR": "#2e8bd6",
#         "LANGUAGE": c["language"] if c["language"] in ("fr", "en") else "en",
#         "EPISODE_CTA_TARGET": "listenly",
#     })
#     env.pop("PODCAST_RAW_INFO", None)
#     env["GITHUB_EVENT_NAME"] = "workflow_dispatch"
#     ok = subprocess.run([sys.executable, "automation/scripts/generate_podcast_btb.py"], env=env).returncode == 0
#     return ok and os.path.exists(f"pages/podcast-btb/{slug}-podcast.html")


# ARCHIVE 04/10/2026 : existing_by_rss, existing_slugs, _norm_rss - plus utilises (DB-ONLY)
# Ces fonctions lisaient podcasts.json, qui n'est plus maintenu (Listenly gere tout).


def mark_failed(number, reason):
    """Un echec ne doit pas bloquer la file a chaque run : on etiquette l'issue, elle est ignoree ensuite."""
    try:
        gh("POST", f"/issues/{number}/labels", {"labels": ["onboard-failed"]})
        gh("POST", f"/issues/{number}/comments", {"body": f"⚠️ Onboarding automatique en échec : {reason}\n\n"
                                                   f"Ignoré aux prochains runs. Pour réessayer : retirer le label `onboard-failed`."})
    except Exception as e:  # ne jamais bloquer le run
        log(f"(etiquetage de l'echec impossible : {e})")


def main():
    if not SECRET or not GH_TOKEN:
        log("ERREUR : KNOWLEDGE_IMPORT_SECRET et GH_TOKEN requis.")
        sys.exit(1)
    wanted = (os.environ.get("ISSUE_NUMBERS") or "all").strip()
    if wanted == "all":
        issues = gh("GET", "/issues?labels=candidate,approved&state=open&per_page=100")
    elif wanted == "auto":
        issues = gh("GET", "/issues?labels=candidate&state=open&per_page=100&sort=created&direction=asc")
        # PIVOT 04/10/2026 : aucune "reparation" (N1 n'est plus generee)
    else:
        issues = [gh("GET", f"/issues/{n.strip()}") for n in wanted.split(",") if n.strip()]
    issues = [i for i in issues if not i.get("pull_request") and i.get("state") == "open"]
    if wanted == "auto":
        skipped = [i for i in issues if any(l.get("name") == "onboard-failed" for l in i.get("labels", []))]
        issues = [i for i in issues if i not in skipped]
        def prio(i):  # email professionnel d'abord, puis email personnel, puis sans email
            e = parse_issue(i)["email"]
            return 2 if not e else (1 if e.rsplit("@", 1)[-1].lower() in FREE_MAIL else 0)
        issues.sort(key=prio)   # tri stable : ordre de creation conserve dans chaque groupe
        log(f"{len(skipped)} candidat(s) en echec ignore(s) (label onboard-failed).")
    log(f"{len(issues)} candidat(s) ouvert(s), plafond {MAX_ONBOARD} nouvelle(s) fiche(s) (mode {MODE}).")

    done, failed, report = [], [], []
    new_count = 0
    for issue in issues:
        c = parse_issue(issue)
        if new_count >= MAX_ONBOARD:
            continue
        log(f"### #{c['issue_number']} {c['podcast_name']}")
        if not c["feed_url"]:
            failed.append(c["issue_number"]); mark_failed(c["issue_number"], "pas de flux RSS dans l'issue"); log("Pas de flux RSS dans l'issue — ignore."); continue
        info = fetch_channel_info(c["feed_url"])
        c["email"] = c["email"] or info["email"]
        if REQUIRE_EMAIL and not c["email"]:
            # Pas d'email : aucun interet pour la prospection, on ferme l'issue.
            gh("POST", f"/issues/{c['issue_number']}/labels", {"labels": ["sans-email"]})
            gh("PATCH", f"/issues/{c['issue_number']}", {"state": "closed", "state_reason": "not_planned"})
            log("Sans email — issue classee (label sans-email)."); continue
        c["description"] = info["description"]  # description publique du RSS

        res = create_listenly_show(c)
        log(f"Listenly : {json.dumps(res, ensure_ascii=False)[:400]}")
        if not res.get("ok"):
            failed.append(c["issue_number"]); mark_failed(c["issue_number"], "creation de la fiche Listenly refusee"); continue
        if MODE != "insert":
            continue
        register_rss_reader(c["feed_url"])
        listenly_url = res["listenly_url"]
        slug = slugify(c["podcast_name"])

        # PIVOT 04/10/2026 DB-ONLY : Listenly scrape + extrait Q/R automatiquement
        # Aucune fonction supplementaire a appeler (add_podcast_to_json, generate_episode_fiches archivees)
        new_count += 1

        created = "creee" if res.get("created") else "deja existante"
        gh("POST", f"/issues/{c['issue_number']}/comments", {"body": (
            f"✅ Onboardé automatiquement (MarketForge Engine) — DB-ONLY\n\n"
            f"- Fiche Listenly ({created}) : {listenly_url}\n"
            f"- Flux RSS enregistre : Listenly scrape + extrait Q/R automatiquement\n"
            f"- Email : {c['email'] or '(aucun)'}\n\n"
            f"NOTE 04/10/2026 : aucune page HTML generee. Tout dans la DB Listenly.\n"
            f"Contact ajoute a la feuille de prospection.")})
        gh("POST", f"/issues/{c['issue_number']}/labels", {"labels": ["onboarded"]})
        gh("PATCH", f"/issues/{c['issue_number']}", {"state": "closed", "state_reason": "completed"})
        done.append(slug)
        report.append({"slug": slug, "podcast_name": c["podcast_name"], "email": c["email"],
                       "listenly_url": listenly_url, "listenly_created": bool(res.get("created")),
                       "rss_registered": True, "latest_episode_question": None, "latest_episode_moment_id": None,
                       "host_name": c.get("artist_name", ""), "thematique": ""})

    log(f"Termine : {len(done)} onboarde(s) {done}, {len(failed)} echec(s) {failed}.")
    if MODE == "insert":  # lu par sheet_bridge.py pour le compte-rendu envoye au Google Sheet
        with open("automation/marketforge_engine/last_onboard.json", "w", encoding="utf-8") as f:
            json.dump({"onboarded": report, "failed_issues": failed}, f, ensure_ascii=False, indent=2)
    if failed and not done:
        sys.exit(1)


if __name__ == "__main__":
    main()

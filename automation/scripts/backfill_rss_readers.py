#!/usr/bin/env python3
"""
MarketForge Engine — rattrapage : enregistre dans le lecteur RSS de Listenly (table _c_p_rss_readers,
via api/rss-reader-register.php) le flux de tous les podcasts deja onboardes dont la fiche existe mais
dont le flux n'a jamais ete ajoute au lecteur (donc jamais scrape).

  python backfill_rss_readers.py            # reel
  DRY_RUN=1 python backfill_rss_readers.py   # affiche seulement ce qui serait fait

Variables : KNOWLEDGE_IMPORT_SECRET (requis)
"""
import os, sys, json, time, urllib.request, urllib.error

SECRET = os.environ.get("KNOWLEDGE_IMPORT_SECRET", "").strip()
URL = os.environ.get("RSS_READER_URL", "https://listenly.fr/api/rss-reader-register.php")
PODCASTS_FILE = "pages/podcast-btb/data/podcasts.json"
DRY_RUN = os.environ.get("DRY_RUN", "").strip() not in ("", "0", "false", "FALSE")


def log(msg):
    print(f"[backfill-rss] {msg}", flush=True)


def call(link, mode):
    req = urllib.request.Request(
        URL, data=json.dumps({"mode": mode, "link": link}).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-Import-Secret": SECRET, "User-Agent": "ListenlyGEO/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code} : {e.read().decode(errors='ignore')[:300]}"}
    except urllib.error.URLError as e:
        return {"ok": False, "error": str(e)}


def main():
    if not SECRET:
        log("ERREUR : KNOWLEDGE_IMPORT_SECRET requis.")
        sys.exit(1)
    with open(PODCASTS_FILE, encoding="utf-8") as f:
        podcasts = json.load(f)
    links = sorted({p["rss_url"].strip() for p in podcasts if p.get("rss_url")})
    log(f"{len(podcasts)} fiche(s), {len(links)} flux RSS unique(s) a verifier (mode {'dry_run' if DRY_RUN else 'insert'}).")

    created, existing, errors = [], [], []
    for i, link in enumerate(links, 1):
        res = call(link, "dry_run" if DRY_RUN else "insert")
        if not res.get("ok"):
            errors.append((link, res.get("error")))
            log(f"  [{i}/{len(links)}] ERREUR {link} : {res.get('error')}")
        elif DRY_RUN:
            (created if not res.get("id") else existing).append(link)
        elif res.get("created"):
            created.append(link)
            log(f"  [{i}/{len(links)}] + ajoute : {link}")
        else:
            existing.append(link)
        if i % 25 == 0:
            log(f"  ... {i}/{len(links)}")
        time.sleep(0.2)

    log(f"Termine : {len(created)} ajoute(s), {len(existing)} deja present(s), {len(errors)} erreur(s).")
    if errors:
        for link, err in errors[:20]:
            log(f"  erreur : {link} -> {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()

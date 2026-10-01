#!/usr/bin/env python3
"""
Compteur de backlinks vers listenly.fr (01/10/2026).
Pour chaque podcast contacte (queue.json), cherche un lien vers listenly.fr dans son flux RSS (notes d'episodes)
et sur la page d'accueil de son site (balise <link> du flux). Resultat : pages/podcast-btb/data/backlinks.json
  {"checked": {slug: "AAAA-MM-JJ"}, "found": {slug: {"url": ..., "where": "rss|site", "date": ...}}, "total": N}
Limite par run (BACKLINK_MAX, defaut 120) : on verifie les moins recemment verifies d'abord. Ne casse jamais le run.
"""
import os, re, json, datetime, urllib.request

DATA = "pages/podcast-btb/data"
OUT = f"{DATA}/backlinks.json"
MAX = int(os.environ.get("BACKLINK_MAX", "120"))
UA = {"User-Agent": "Mozilla/5.0 (compatible; ListenlyBot/1.0; +https://listenly.fr)"}
# lien vers listenly.fr qui n'est pas NOTRE propre fiche hub generee (on cherche un lien POSE par le podcast)
PAT = re.compile(r"https?://(?:www\.)?listenly\.fr/[^\s\"'<>)]*", re.I)


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def get(url, limit=1_500_000):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read(limit).decode("utf-8", "ignore")


def main():
    today = datetime.date.today().isoformat()
    state = load(OUT, {"checked": {}, "found": {}, "total": 0})
    recs = {r["fiche_url"].rsplit("/", 1)[-1].replace(".html", ""): r for r in load(f"{DATA}/podcasts.json", [])}
    queue = load("automation/marketforge_engine/queue.json", {}).get("podcasts", {})
    cand = [s for s, v in queue.items() if v.get("status") in ("contact", "extrait", "reponse", "repondu")
            or v.get("proof_date")]
    cand.sort(key=lambda s: state["checked"].get(s, ""))
    n = 0
    for s in cand[:MAX]:
        rec = recs.get(s if s.endswith("-podcast") else s + "-podcast") or recs.get(s) or {}
        rss = rec.get("rss_url")
        if not rss:
            state["checked"][s] = today
            continue
        n += 1
        found = None
        try:
            xml = get(rss)
            for m in PAT.finditer(xml):
                u = m.group(0)
                if "/podcast-btb/" in u or "/podcast/show/" in u or u.rstrip("/").endswith("listenly.fr"):
                    found = {"url": u, "where": "rss"}
                    break
            if not found:
                lk = re.search(r"<link>\s*(https?://[^<\s]+)\s*</link>", xml.split("<item>")[0])
                if lk and "listenly.fr" not in lk.group(1):
                    html = get(lk.group(1))
                    m = PAT.search(html)
                    if m:
                        found = {"url": m.group(0), "where": "site"}
        except Exception:
            pass
        state["checked"][s] = today
        if found:
            found["date"] = state["found"].get(s, {}).get("date", today)
            state["found"][s] = found
    state["total"] = len(state["found"])
    state["updated"] = today
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    print(f"[backlink-check] verifies: {n} | backlinks trouves au total: {state['total']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Lien "question du hub -> lecteur au bon moment" (29/09/2026).

Chaque bouton "Ecouter ce moment" d'un hub N1 ouvre /podcast-btb/ecouter.html?p=<slug>&m=<id> : une page
(copie du lecteur de la page Listenly Knowledge Search) qui lit l'audio de l'episode a la seconde exacte,
avec un lien vers la vraie page de l'episode sur Listenly (service get-episode-url.php deja utilise par
les fiches question) et la barre de recherche existante (api/listenly-search.php).

Ce module est la source unique pour :
  - moment_id(slug, question)              : identifiant stable d'une question
  - lookup(slug) / resolve_entry(...)       : la question a-t-elle son moment exact / au moins son episode ?
  - page_url(slug, id)                      : adresse du lecteur
  - main()                                  : ecrit data/moments/<slug>.json (lu par la page) et resout
                                              les adresses d'episodes Listenly manquantes.

Usage : python automation/scripts/moments_index.py [--no-resolve]
Variables : RESOLVE_MAX (defaut 120) = nombre max d'appels a get-episode-url.php par passage.
"""
import os, re, sys, json, glob, hashlib, datetime, time, urllib.request, collections

PAGES_DIR = "pages/podcast-btb"
KNOWLEDGE_DIR = f"{PAGES_DIR}/data/knowledge_moments"
INDEX_DIR = f"{PAGES_DIR}/data/moments"
EP_URLS_FILE = f"{PAGES_DIR}/data/listenly_episode_urls.json"
PODCASTS_FILE = f"{PAGES_DIR}/data/podcasts.json"
EPISODE_URL_API = "https://listenly.fr/api/get-episode-url.php"
PLAYER_PAGE = "/"   # page d accueil Listenly (recherche + lecteur en barre, lien profond) ; repli : /podcast-btb/ecouter.html
RETRY_NEGATIVE_DAYS = 14


def norm(q):
    return re.sub(r"\s+", " ", (q or "").strip().lower())


def moment_id(slug, question):
    return hashlib.sha1(f"{slug}|{norm(question)}".encode("utf-8")).hexdigest()[:10]


def page_url(slug, mid):
    return f"{PLAYER_PAGE}?p={slug}&m={mid}"


_cache = {}


def invalidate(slug=None):
    """A appeler apres l'ecriture d'un nouveau fichier de moments dans le meme processus."""
    if slug is None:
        _cache.clear()
    else:
        _cache.pop(slug, None)


def load_moments(slug):
    """Knowledge moments d'un podcast (fichiers <slug>--<episode>.json), avec audio."""
    if slug in _cache:
        return _cache[slug]
    out = []
    for path in sorted(glob.glob(f"{KNOWLEDGE_DIR}/{glob.escape(slug)}--*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        for m in data if isinstance(data, list) else []:
            if m.get("question") and m.get("audio_url"):
                out.append(m)
    _cache[slug] = out
    return out


def lookup(slug):
    """(exact, episodes) : norm(question) -> moment ; norm(titre episode) -> 1er moment de l'episode."""
    exact, eps = {}, {}
    for m in load_moments(slug):
        exact.setdefault(norm(m["question"]), m)
        eps.setdefault(norm(m.get("episode_title")), m)
    return exact, eps


def resolve_entry(slug, question, episode_title, lk=None):
    """(id, approx) si la question peut ouvrir le lecteur, sinon None.
    approx=True : l'episode est connu mais pas l'horodatage exact (lecture depuis le debut)."""
    exact, eps = lk if lk is not None else lookup(slug)
    if norm(question) in exact:
        return moment_id(slug, question), False
    if episode_title and norm(episode_title) in eps:
        return moment_id(slug, question), True
    return None


# ---------------------------------------------------------------------------------------------
# Adresses d'episodes Listenly
# ---------------------------------------------------------------------------------------------
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")


def seed_episode_urls(ep_urls):
    """Recupere, sans reseau, les adresses d'episodes deja presentes dans les anciennes fiches question."""
    added = 0
    for reg in glob.glob(f"{PAGES_DIR}/questions/*/_qa_registry.json"):
        slug = reg.split("/")[-2]
        for p in load_json(reg, {}).get("published", []):
            key = norm(p.get("source_episode_title"))
            if not key or ep_urls.get(slug, {}).get(key, {}).get("u"):
                continue
            rel = (p.get("url") or "").replace("https://listenly.fr/podcast-btb/", "")
            try:
                with open(f"{PAGES_DIR}/{rel}", encoding="utf-8", errors="ignore") as f:
                    html_ = f.read()
            except OSError:
                continue
            urls = re.findall(r"https://listenly\.fr/podcast/episode/([A-Za-z0-9_\-]+)", html_)
            if urls:
                best = collections.Counter(urls).most_common(1)[0][0]
                ep_urls.setdefault(slug, {})[key] = {"u": f"https://listenly.fr/podcast/episode/{best}", "d": "seed"}
                added += 1
    return added


def resolve_episode_urls(ep_urls, podcasts, max_calls):
    """Interroge get-episode-url.php (rss_url + titre) pour les episodes sans adresse connue."""
    today = datetime.date.today()
    rss = {p["slug"]: p.get("rss_url", "") for p in podcasts}
    todo = []
    for slug in sorted({m for m in rss}):
        seen = set()
        for m in load_moments(slug):
            key = norm(m.get("episode_title"))
            if not key or key in seen:
                continue
            seen.add(key)
            rec = ep_urls.get(slug, {}).get(key)
            if rec and rec.get("u"):
                continue
            if rec and rec.get("d") not in (None, "seed"):
                try:
                    if (today - datetime.date.fromisoformat(rec["d"])).days < RETRY_NEGATIVE_DAYS:
                        continue
                except ValueError:
                    pass
            todo.append((slug, key, m.get("episode_title")))
    found = calls = errors = 0
    for slug, key, title in todo[:max_calls]:
        if not rss.get(slug):
            continue
        calls += 1
        try:
            req = urllib.request.Request(
                EPISODE_URL_API, method="POST", headers={"Content-Type": "application/json", "User-Agent": "ListenlyGEO/1.0"},
                data=json.dumps({"rss_url": rss[slug], "episode_title": title}).encode("utf-8"))
            with urllib.request.urlopen(req, timeout=8) as r:
                d = json.loads(r.read())
            url = f"https://listenly.fr/podcast/episode/{d['seo_url']}" if d.get("found") and d.get("seo_url") else ""
            ep_urls.setdefault(slug, {})[key] = {"u": url, "d": today.isoformat()}
            found += 1 if url else 0
        except Exception:
            errors += 1
            if errors >= 5 and found == 0:
                print("[moments] service get-episode-url.php injoignable — resolution reportee au prochain passage.")
                break
        time.sleep(0.15)
    return len(todo), calls, found


# ---------------------------------------------------------------------------------------------
# Index lu par la page ecouter.html
# ---------------------------------------------------------------------------------------------
def _trim(text, limit=650):
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def build_index(podcast, ep_urls):
    slug = podcast["slug"]
    moments = load_moments(slug)
    reg = load_json(f"{PAGES_DIR}/questions/{slug}/_qa_registry.json", {})
    exact, eps = lookup(slug)
    urls = ep_urls.get(slug, {})
    entries = {}

    def ep_link(title):
        return (urls.get(norm(title)) or {}).get("u", "")

    snippets = {norm(p.get("question")): p.get("answer_snippet") for p in reg.get("published", [])}
    for m in moments:
        mid = moment_id(slug, m["question"])
        if mid in entries:
            continue
        entries[mid] = {
            "q": m["question"], "a": _trim(m.get("transcript_excerpt") or snippets.get(norm(m["question"]))),
            "x": m.get("expert_name") or "",
            "e": m.get("episode_title") or "", "u": m["audio_url"], "t": int(m.get("start_seconds") or 0),
            "l": ep_link(m.get("episode_title")),
        }
    for p in reg.get("published", []):   # anciennes fiches : episode connu, horodatage inconnu -> lecture depuis le debut
        q, ep = p.get("question"), p.get("source_episode_title")
        if not q or moment_id(slug, q) in entries or norm(ep) not in eps:
            continue
        src = eps[norm(ep)]
        entries[moment_id(slug, q)] = {
            "q": q, "a": _trim(p.get("answer_snippet")), "x": src.get("expert_name") or "",
            "e": src.get("episode_title") or ep, "u": src["audio_url"], "t": 0, "ap": 1,
            "l": ep_link(src.get("episode_title")),
        }
    if not entries:
        return 0
    save_json(f"{INDEX_DIR}/{slug}.json", {
        "podcast": podcast.get("podcast_name", slug), "slug": slug,
        "hub": f"/podcast-btb/{slug}-podcast.html", "show": podcast.get("listenly_url", ""),
        "cover": podcast.get("cover_image", ""),
        "entries": entries,
    }, compact=True)
    return len(entries)


def main():
    podcasts = load_json(PODCASTS_FILE, [])
    ep_urls = load_json(EP_URLS_FILE, {})
    seeded = seed_episode_urls(ep_urls)
    todo = calls = found = 0
    if "--no-resolve" not in sys.argv:
        todo, calls, found = resolve_episode_urls(ep_urls, podcasts, int(os.environ.get("RESOLVE_MAX", "120")))
    save_json(EP_URLS_FILE, ep_urls)
    files = entries = 0
    for p in podcasts:
        n = build_index(p, ep_urls)
        if n:
            files += 1
            entries += n
    known = sum(1 for v in ep_urls.values() for r in v.values() if r.get("u"))
    msg = (f"{entries} moment(s) dans {files} podcast(s) | adresses d'episodes Listenly connues : {known} "
           f"(+{seeded} depuis les fiches, +{found} via le service ; {max(todo - calls, 0)} restantes)")
    print(f"[moments] {msg}")
    print(f"::notice title=Lecteur de moments::{msg}")


if __name__ == "__main__":
    main()

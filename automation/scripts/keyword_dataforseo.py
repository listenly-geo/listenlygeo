#!/usr/bin/env python3
"""
Connecteur DataForSEO (volumes de recherche) pour le moteur des pages de moment (16/10/2026).

Secrets attendus (GitHub Actions secrets) :
  DATAFORSEO_LOGIN      identifiant API DataForSEO
  DATAFORSEO_PASSWORD   mot de passe API DataForSEO (ne jamais l'ecrire dans le depot)

Sans ces secrets : ecrit le statut « non connecte » et ne fait aucun appel.
Usage : python3 automation/scripts/keyword_dataforseo.py "question 1" "question 2" ...
Sortie : pages/podcast-btb/data/keyword_dataforseo.json
"""
import os, re, sys, json, base64, datetime, urllib.request, urllib.error

BASE = "https://api.dataforseo.com/v3"
OUT = "pages/podcast-btb/data/keyword_dataforseo.json"
LOCATION = 2840   # Etats-Unis
LANGUAGE = "en"


def auth_header():
    raw = f"{os.environ['DATAFORSEO_LOGIN']}:{os.environ['DATAFORSEO_PASSWORD']}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Authorization": auth_header(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def write(out):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)


CACHE = "pages/podcast-btb/data/keyword_cache.json"
CANDIDATES = "pages/podcast-btb/data/keyword_candidates.json"
MAX_NEW_PER_RUN = 100   # plafond de requetes nouvelles par jour (maitrise du budget)
TTL_DAYS = 30           # un volume reste valable 30 jours

STOP = set("what why how is are was were does do did the a an of in for to and or with by on at from be can could would "
           "should it its this that which who whom when where whose their there as than into about over under "
           "has have had will may might must between through during including such more most other some any each "
           "both so too very just only also not no you your we they our role work works changed change changes "
           "function functions nature mean means matter matters".split())


def phrase_from_question(q):
    """Forme courte d'une question pour la requete : mots pleins, sans mots interrogatifs, 4 mots max."""
    words = re.findall(r"[a-zA-Z][a-zA-Z\-']*", (q or "").lower())
    return " ".join([w for w in words if w not in STOP][:4])


def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def cached_volume(phrase, cache=None):
    """Volume mis en cache pour une forme courte, ou None (inconnu, pas de donnee ou expire)."""
    cache = cache if cache is not None else load_json(CACHE, {})
    item = cache.get(phrase)
    if not item or item.get("volume") is None:
        return None
    try:
        age = (datetime.date.today() - datetime.date.fromisoformat(item["date"])).days
    except (KeyError, ValueError):
        return None
    return item["volume"] if age <= TTL_DAYS else None


def refresh():
    """Mode quotidien (GitHub Actions) : interroge DataForSEO pour les formes courtes candidates non connues."""
    today = datetime.date.today().isoformat()
    cand = load_json(CANDIDATES, [])
    cache = load_json(CACHE, {})
    cache = {k: v for k, v in cache.items() if not k.startswith("_")
             and (datetime.date.today() - datetime.date.fromisoformat(v.get("date", "1970-01-01"))).days <= TTL_DAYS}
    todo = [p for p in dict.fromkeys(cand) if p and p not in cache][:MAX_NEW_PER_RUN]
    if not todo:
        print("DataForSEO : rien a interroger aujourd'hui.")
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return
    missing = [k for k in ("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD") if not os.environ.get(k)]
    if missing:
        print("DataForSEO : non connecte. Secrets manquants : " + ", ".join(missing))
        return
    try:
        resp = call("POST", "/keywords_data/google_ads/search_volume/live",
                    [{"keywords": todo, "location_code": LOCATION, "language_code": LANGUAGE}])
    except urllib.error.HTTPError as e:
        print(f"DataForSEO : erreur HTTP {e.code} : {e.read().decode(errors='ignore')[:300]}")
        sys.exit(1)
    results = ((resp.get("tasks") or [{}])[0].get("result")) or []
    got = {r.get("keyword"): r.get("search_volume") for r in results}
    for kw in todo:
        cache[kw] = {"volume": got.get(kw), "date": today}
    cache["_meta"] = {"date": today, "solde": ((resp.get("tasks") or [{}])[0].get("cost"))}
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"DataForSEO : {len(todo)} formes interrogees, {sum(1 for kw in todo if got.get(kw) is not None)} avec volume.")


def main():
    global OUT
    args = sys.argv[1:]
    if args[:1] == ["--refresh"]:
        refresh()
        return
    if args[:1] == ["--file"]:   # simulation : une requete par ligne dans le fichier
        args = [l.strip() for l in open(args[1], encoding="utf-8") if l.strip()]
    if args[:1] == ["--out"]:
        OUT = args[1]
        args = args[2:]
    keywords = [k.strip() for k in args if k.strip()]
    today = datetime.date.today().isoformat()
    missing = [k for k in ("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD") if not os.environ.get(k)]
    if missing:
        write({"statut": "non connecte", "date": today, "secrets_manquants": missing})
        print("DataForSEO : non connecte. Secrets manquants : " + ", ".join(missing))
        return
    try:
        info = call("GET", "/appendix/user_data")
        money = ((info.get("tasks") or [{}])[0].get("result") or [{}])[0].get("money") or {}
        solde = money.get("balance")
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError) as e:
        write({"statut": "erreur", "date": today, "detail": str(e)[:300]})
        print(f"DataForSEO : erreur de connexion ({e})")
        sys.exit(1)
    if not keywords:
        write({"statut": "connecte", "date": today, "solde": solde, "volumes": []})
        print(f"DataForSEO : connecte, solde {solde}. Aucune requete a tester.")
        return
    try:
        resp = call("POST", "/keywords_data/google_ads/search_volume/live",
                    [{"keywords": keywords, "location_code": LOCATION, "language_code": LANGUAGE}])
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")[:500]
        write({"statut": "erreur", "date": today, "code": e.code, "detail": body})
        print(f"DataForSEO : erreur HTTP {e.code} : {body}")
        sys.exit(1)
    results = ((resp.get("tasks") or [{}])[0].get("result")) or []
    volumes = [{"mot_cle": r.get("keyword"), "volume_mensuel": r.get("search_volume"),
                "concurrence": r.get("competition")} for r in results]
    write({"statut": "connecte", "date": today, "solde": solde, "volumes": volumes})
    print(f"DataForSEO : connecte, solde {solde}, {len(volumes)} volume(s) recupere(s).")
    for v in volumes:
        print(f"  {v['volume_mensuel']!s:>8}  {v['mot_cle']}")


if __name__ == "__main__":
    main()

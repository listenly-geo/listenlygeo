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
import os, sys, json, base64, datetime, urllib.request, urllib.error

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


def main():
    keywords = [k.strip() for k in sys.argv[1:] if k.strip()]
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
        write({"statut": "erreur", "date": today, "code": e.code, "detail": e.read().decode()[:300]})
        print(f"DataForSEO : erreur HTTP {e.code}")
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

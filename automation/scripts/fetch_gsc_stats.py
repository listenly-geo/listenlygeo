#!/usr/bin/env python3
"""
Recupere les statistiques reelles (clics, impressions, CTR) depuis l'API Google
Search Console pour les fiches du Moteur Trafic (/podcast-btb/), et les ecrit dans
pages/podcast-btb/data/gsc_stats.json — consomme ensuite par build_dashboard()
(generate_podcast_btb.py) pour afficher la carte "Statistiques Search Console" du
dashboard, a la place de l'ancienne carte "cout estime".

PREREQUIS (a faire une seule fois, cote Google Cloud + Search Console) :
  1. Dans Google Cloud Console, activer l'API "Google Search Console API" sur un
     projet (nouveau ou existant).
  2. Creer un compte de service (Service Account), generer une cle JSON.
  3. Dans Google Search Console (search.google.com/search-console) sur la propriete
     listenly.fr, aller dans Parametres > Utilisateurs et autorisations > Ajouter,
     et ajouter l'email du compte de service (ex: xxx@projet.iam.gserviceaccount.com)
     avec le role "Complet" ou "Restreint" (lecture seule suffit).
  4. Ajouter le CONTENU COMPLET du fichier JSON de la cle comme secret GitHub, nomme
     GSC_SERVICE_ACCOUNT_JSON (Settings > Secrets and variables > Actions > New
     repository secret) -- ne JAMAIS coller cette cle ailleurs (chat, fichier commite).

Variables d'environnement :
  GSC_SERVICE_ACCOUNT_JSON — obligatoire, contenu JSON complet de la cle de service
  GSC_SITE_URL              — propriete Search Console (defaut: "https://listenly.fr/")
  GSC_PATH_FILTER           — filtre de page (defaut: "/podcast-btb/")
  GSC_DAYS                  — nombre de jours a recuperer (defaut: 30)

Sortie : pages/podcast-btb/data/gsc_stats.json
"""

import os, sys, json, datetime
import urllib.request, urllib.error

SITE_URL = os.environ.get("GSC_SITE_URL", "https://listenly.fr/")
PATH_FILTER = os.environ.get("GSC_PATH_FILTER", "/podcast-btb/")
DAYS = int(os.environ.get("GSC_DAYS", "30"))
OUTPUT_FILE = "pages/podcast-btb/data/gsc_stats.json"

SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def log(msg):
    print(f"[gsc-stats] {msg}", flush=True)


def get_access_token(sa_info):
    """Echange les credentials du compte de service contre un access token OAuth2
    (JWT bearer flow), sans dependance externe (google-auth) — juste stdlib + une
    lib de signature RSA minimale via le module cryptography si disponible, sinon
    via openssl en subprocess pour rester portable sur le runner GitHub Actions."""
    import base64, time, subprocess, tempfile

    header = {"alg": "RS256", "typ": "JWT"}
    now = int(time.time())
    claim = {
        "iss": sa_info["client_email"],
        "scope": SCOPE,
        "aud": TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }

    def b64url(data):
        return base64.urlsafe_b64encode(data).rstrip(b"=")

    header_b64 = b64url(json.dumps(header, separators=(",", ":")).encode())
    claim_b64 = b64url(json.dumps(claim, separators=(",", ":")).encode())
    signing_input = header_b64 + b"." + claim_b64

    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as kf:
        kf.write(sa_info["private_key"])
        key_path = kf.name
    try:
        proc = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", key_path],
            input=signing_input, capture_output=True, check=True,
        )
        signature = b64url(proc.stdout)
    finally:
        os.unlink(key_path)

    jwt = (signing_input + b"." + signature).decode()

    data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    return result["access_token"]


import urllib.parse  # noqa: E402 (utilise dans get_access_token)


def query_search_analytics(access_token, start_date, end_date, dimensions):
    url = f"https://www.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(SITE_URL, safe='')}/searchAnalytics/query"
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "dimensionFilterGroups": [{
            "filters": [{"dimension": "page", "operator": "contains", "expression": PATH_FILTER}]
        }],
        "rowLimit": 25000,
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def main():
    raw_sa = os.environ.get("GSC_SERVICE_ACCOUNT_JSON")
    if not raw_sa:
        log("ERREUR : GSC_SERVICE_ACCOUNT_JSON absent — voir le guide de configuration en tete de ce fichier.")
        sys.exit(1)

    try:
        sa_info = json.loads(raw_sa)
    except json.JSONDecodeError:
        log("ERREUR : GSC_SERVICE_ACCOUNT_JSON n'est pas un JSON valide.")
        sys.exit(1)

    access_token = get_access_token(sa_info)

    today = datetime.date.today()
    # GSC a un delai de fraicheur de 2-3 jours -- on s'arrete a J-3 pour n'avoir que
    # des jours dont les donnees sont completes et stables.
    end_date = today - datetime.timedelta(days=3)
    start_date = end_date - datetime.timedelta(days=DAYS - 1)
    prev_end_date = start_date - datetime.timedelta(days=1)
    prev_start_date = prev_end_date - datetime.timedelta(days=DAYS - 1)

    log(f"Periode actuelle : {start_date} -> {end_date}")
    daily_result = query_search_analytics(access_token, start_date.isoformat(), end_date.isoformat(), ["date"])
    rows = daily_result.get("rows", [])
    daily = [
        {"date": r["keys"][0], "clicks": int(r.get("clicks", 0)), "impressions": int(r.get("impressions", 0))}
        for r in rows
    ]
    daily.sort(key=lambda d: d["date"])

    clicks_total = sum(d["clicks"] for d in daily)
    impressions_total = sum(d["impressions"] for d in daily)

    log(f"Periode precedente (comparaison) : {prev_start_date} -> {prev_end_date}")
    prev_result = query_search_analytics(access_token, prev_start_date.isoformat(), prev_end_date.isoformat(), [])
    prev_rows = prev_result.get("rows", [])
    clicks_previous_period = int(prev_rows[0].get("clicks", 0)) if prev_rows else 0

    output = {
        "site_url": SITE_URL,
        "path_filter": PATH_FILTER,
        "period_label": f"{DAYS} derniers jours",
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "clicks_total": clicks_total,
        "impressions_total": impressions_total,
        "clicks_previous_period": clicks_previous_period,
        "daily": daily,
        "fetched_at": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log(f"Termine : {clicks_total} clics, {impressions_total} impressions sur {len(daily)} jour(s) -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

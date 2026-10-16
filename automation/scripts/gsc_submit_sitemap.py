#!/usr/bin/env python3
"""Soumet chaque jour le plan des moments (sitemap-moments.xml) a la Search Console de listenly.org.
Secret requis : GSC_SERVICE_ACCOUNT_JSON (compte de service avec acces complet a la propriete).
Ne bloque jamais le workflow : en cas d'erreur, affiche le motif et sort en code 0.
Ajoute le 16/10/2026 (decision : integration au systeme quotidien)."""
import os, json, requests

SITE = os.environ.get("GSC_SITE", "sc-domain:listenly.org")
SITEMAP = os.environ.get("GSC_SITEMAP", "https://listenly.org/podcast-btb/sitemap-moments.xml")
SCOPES = ["https://www.googleapis.com/auth/webmasters"]


def token():
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    info = json.loads(os.environ["GSC_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    creds.refresh(Request())
    return creds.token


def main():
    if not os.environ.get("GSC_SERVICE_ACCOUNT_JSON"):
        print("[gsc-sitemap] secret absent : rien soumis")
        return
    try:
        tok = token()
        site = requests.utils.quote(SITE, safe="")
        feed = requests.utils.quote(SITEMAP, safe="")
        url = f"https://www.googleapis.com/webmasters/v3/sites/{site}/sitemaps/{feed}"
        r = requests.put(url, headers={"Authorization": f"Bearer {tok}"}, timeout=60)
        if r.status_code in (200, 204):
            print(f"[gsc-sitemap] plan soumis : {SITEMAP}")
        else:
            print(f"[gsc-sitemap] refus {r.status_code} : {r.text[:300]}")
    except Exception as e:
        print(f"[gsc-sitemap] erreur : {str(e)[:300]}")


if __name__ == "__main__":
    main()

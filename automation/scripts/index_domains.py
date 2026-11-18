#!/usr/bin/env python3
"""
Domaine du client (18/11/2026) : pour chaque Index "Pret" dont le client a donne un domaine, relie le domaine a l'Index,
l'ajoute a l'hebergement (cPanel, si les secrets CPANEL_* existent), verifie DNS + HTTPS et fait avancer le statut :
  Pret  -> "DNS a faire" (mail au client avec la ligne a copier, et au webmaster si indique)
        -> "En ligne"    (le domaine repond en HTTPS : mail "Your Index is live")
Variables : MFE_SHEET_URL, HUB_IMPORT_TOKEN ; optionnelles : CPANEL_HOST, CPANEL_USER, CPANEL_TOKEN, DRY_RUN=1
"""
import os, sys, re, json, urllib.request, urllib.parse, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet_bridge as sb  # noqa: E402

HUB_DOMAIN = "https://app.marketforge.fr/hub/domain"
APP_HOST = "app.marketforge.fr"
CP_HOST = os.environ.get("CPANEL_HOST", "").strip()
CP_USER = os.environ.get("CPANEL_USER", "").strip()
CP_TOKEN = os.environ.get("CPANEL_TOKEN", "").strip()
DRY_RUN = os.environ.get("DRY_RUN", "").strip() in ("1", "true", "yes")
DOCROOT = os.environ.get("CPANEL_DOCROOT", "app.marketforge.fr/public")


def log(msg):
    print(f"[index-domains] {msg}", flush=True)


def clean_domain(d):
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return re.sub(r"[/?#].*$", "", d).strip(".")


def clean_label(s):
    s = re.sub(r"[^a-z0-9-]", "", (s or "expertise").strip().lower()).strip("-")
    return s[:40] or "expertise"


def hub(payload):
    token = os.environ.get("HUB_IMPORT_TOKEN", "")
    req = urllib.request.Request(HUB_DOMAIN, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Hub-Token": token, "User-Agent": "MarketForge/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"ok": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cpanel(module, func, version, **params):
    """Appel cPanel (jeton API). Retourne (ok, message)."""
    if not (CP_HOST and CP_USER and CP_TOKEN):
        return False, "cPanel non configure"
    q = urllib.parse.urlencode(dict(params, cpanel_jsonapi_module=module, cpanel_jsonapi_func=func, cpanel_jsonapi_apiversion=version))
    url = f"https://{CP_HOST}:2083/json-api/cpanel?{q}"
    req = urllib.request.Request(url, headers={"Authorization": f"cpanel {CP_USER}:{CP_TOKEN}"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            j = json.loads(r.read().decode())
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    res = (j.get("cpanelresult") or {})
    data = res.get("data") or [{}]
    first = data[0] if isinstance(data, list) and data else {}
    ok = bool(first.get("result", 0)) if isinstance(first, dict) and "result" in first else not res.get("error")
    return ok, str(first.get("reason") or res.get("error") or "")[:200]


def add_to_hosting(host):
    """Ajoute le domaine a l'hebergement (meme dossier que l'app) puis demande le certificat. Deja present = succes."""
    label = re.sub(r"[^a-z0-9]", "-", host)[:60].strip("-")
    ok, msg = cpanel("AddonDomain", "addaddondomain", "2", dir=DOCROOT, newdomain=host, subdomain=label)
    if not ok and re.search(r"already|exist|existe", msg, re.I):
        ok = True
    log(f"hebergement {host} : {'OK' if ok else 'ECHEC'} {msg}")
    ok2, msg2 = cpanel("SSL", "start_autossl_check", "3")
    log(f"certificat (AutoSSL) : {'demande' if ok2 else 'non demande'} {msg2}")
    return ok


def main():
    if not sb.URL:
        log("MFE_SHEET_URL manquant : rien a faire.")
        return
    j = sb.call(payload={"action": "onboarding_domains"})
    rows = j.get("rows", []) if isinstance(j, dict) and j.get("ok") else []
    log(f"{len(rows)} domaine(s) a traiter.")
    for r in rows:
        num = r["row"]
        apex = clean_domain(r.get("Domaine"))
        sub = clean_label(r.get("Sous-domaine"))
        m = re.search(r"/docs/([a-z0-9-]+)", r.get("Notes", ""))
        if not apex or "." not in apex or not m:
            log(f"Ligne {num} ignoree : domaine ou Index introuvable ({apex!r}).")
            continue
        host, slug = f"{sub}.{apex}", m.group(1)
        if DRY_RUN:
            log(f"[dry] ligne {num} : {host} -> {slug}")
            continue
        res = hub({"action": "link", "site": slug, "host": host})
        if not res.get("ok"):
            log(f"Ligne {num} : liaison refusee ({res.get('error')}).")
            sb.call(payload={"action": "onboarding_domain_update", "row": num, "statut": "Erreur", "note": f"Domaine {host} : {res.get('error')}", "host": host})
            continue
        add_to_hosting(host)
        chk = hub({"action": "check", "host": host})
        log(f"Ligne {num} : {host} dns={chk.get('dns')} https={chk.get('https')} actif={chk.get('active')}")
        if chk.get("active"):
            sb.call(payload={"action": "onboarding_domain_update", "row": num, "statut": "En ligne", "host": host, "target": APP_HOST, "note": f"En ligne : https://{host}"})
        elif r.get("Statut") == "Pret":
            sb.call(payload={"action": "onboarding_domain_update", "row": num, "statut": "DNS a faire", "host": host, "target": APP_HOST, "note": f"DNS a faire : {host} CNAME {APP_HOST}"})


if __name__ == "__main__":
    main()

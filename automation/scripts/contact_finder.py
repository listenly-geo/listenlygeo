#!/usr/bin/env python3
"""
Module "Qui contacter" du MarketForge Engine (V2.5) : tourne A COTE du moteur, ne touche ni a l'envoi ni a l'extraction.

Pour chaque prospect du Sheet (statut "Pret" d'abord) :
  1. calcule un SCORE DE PRIORITE (0-100) : entreprise B2B, contenu extrait, question prete, decideur identifie...
  2. cherche le FONDATEUR / DIRIGEANT / RESPONSABLE MARKETING-CONTENT-PODCAST sur le site public du podcast
     (pages accueil / a propos / equipe / contact), via Claude qui n'extrait QUE des noms ecrits sur ces pages.
  3. ecrit le resultat dans les colonnes S a X du Sheet (action web "contacts"). Les colonnes A-R ne sont jamais modifiees.

Regles : jamais d'adresse inventee ; une adresse n'est retenue que si elle est ecrite sur le site de l'entreprise et
passe le filtre rss_contact.email_problem. Aucun nom ni email n'est ecrit dans le depot (public) : seul
contact_state.json (dates, drapeaux, scores) est commite.

  python contact_finder.py            : un passage (MAX_PAR_RUN prospects recherches)
Variables : MFE_SHEET_URL, ANTHROPIC_API_KEY, CONTACT_MAX (defaut 40), CONTACT_DRY (1 = n'ecrit pas dans le Sheet)
"""
import os, re, sys, json, datetime, urllib.request, urllib.parse
from urllib.parse import urlparse, urljoin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet_bridge  # noqa: E402
from rss_contact import email_problem, EMAIL_RE, fetch_channel_info  # noqa: E402

STATE_FILE = "automation/marketforge_engine/contact_state.json"
PODCASTS_FILE = "pages/podcast-btb/data/podcasts.json"
MAX_RUN = int(os.environ.get("CONTACT_MAX", "40") or 40)
DRY = os.environ.get("CONTACT_DRY", "") == "1"
REFRESH_DAYS = 30
MODEL = "claude-haiku-4-5-20251001"
UA = {"User-Agent": "Mozilla/5.0 (compatible; ListenlyGEO/1.0; +https://listenly.fr)"}
PATHS = ["", "/about", "/about-us", "/team", "/our-team", "/leadership", "/contact", "/company"]
FREE = ("gmail.", "outlook.", "hotmail.", "yahoo.", "icloud.", "proton", "gmx.", "aol.", "live.", "msn.", "me.com")
HOSTS = ("anchor.fm", "spotify.com", "apple.com", "buzzsprout.com", "libsyn.com", "podbean.com", "simplecast.com",
         "transistor.fm", "captivate.fm", "acast.com", "megaphone.fm", "soundcloud.com", "youtube.com", "linkedin.com",
         "facebook.com", "twitter.com", "x.com", "instagram.com", "podcasts.apple.com", "castos.com", "fireside.fm",
         "podcastpage.io", "wixsite.com", "squarespace.com", "wordpress.com", "substack.com", "medium.com")
FOUNDER = re.compile(r"\b(co-?found|found|owner|ceo|chief executive|managing director|president|principal|partner|proprietor)", re.I)
MARKETING = re.compile(r"\b(cmo|chief marketing|head of (marketing|content|growth|brand|communications|podcast)|"
                       r"(marketing|content|brand|communications|podcast|growth|demand)\b.*\b(director|manager|lead|head|producer|officer)|"
                       r"(director|manager|lead|head|producer|vp)\b.*\b(marketing|content|brand|communications|podcast|growth))", re.I)


def log(m):
    print(f"[contact-finder] {m}", flush=True)


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def domain_of(url_or_email):
    s = (url_or_email or "").strip().lower()
    if "@" in s:
        return s.rsplit("@", 1)[1]
    try:
        h = urlparse(s if "//" in s else "//" + s).netloc
    except ValueError:
        return ""
    return re.sub(r"^www\.", "", h)


def corporate_domain(d):
    d = (d or "").lower()
    return bool(d) and not any(d.startswith(f) or f in d for f in FREE) and not any(d == h or d.endswith("." + h) for h in HOSTS)


def http_get(url, timeout=12, cap=400_000):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get("Content-Type", "")
            if "html" not in ctype and "text" not in ctype:
                return ""
            return r.read(cap).decode("utf-8", "ignore")
    except Exception:
        return ""


def to_text(html):
    html = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = re.sub(r"&nbsp;|&#160;", " ", html)
    return re.sub(r"\s+", " ", html).strip()


def role_rank(role):
    role = role or ""
    if FOUNDER.search(role):
        return 1
    if MARKETING.search(role):
        return 2
    return 9


def site_for(slug, prospect, pods):
    """Site de l'entreprise : site du podcast (podcasts.json), sinon domaine de l'email de contact s'il est d'entreprise."""
    rec = pods.get(slug) or {}
    for u in (rec.get("podcast_url"), ):
        d = domain_of(u)
        if u and corporate_domain(d):
            return "https://" + d
    d = domain_of(prospect.get("Email", ""))
    if corporate_domain(d):
        return "https://" + d
    if rec.get("rss_url"):   # le flux RSS donne parfois le lien du site
        try:
            info = fetch_channel_info(rec["rss_url"])
            m = re.search(r"https?://[^\s\"'<>]+", info.get("description", ""))
            if m and corporate_domain(domain_of(m.group(0))):
                return "https://" + domain_of(m.group(0))
        except Exception:
            pass
    return ""


def fetch_site(base):
    pages, found = [], 0
    for path in PATHS:
        if found >= 5:
            break
        html = http_get(urljoin(base + "/", path.lstrip("/")))
        if len(html) < 400:
            continue
        found += 1
        pages.append((path or "/", html))
    return pages


def ask_claude(podcast, host_hint, texts):
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or not texts:
        return []
    corpus = "\n\n".join(f"[PAGE {p}]\n{t[:5000]}" for p, t in texts)[:17000]
    prompt = (
        f"Podcast : {podcast}. Hote connu (peut etre vide) : {host_hint or '-'}.\n"
        "Voici le texte de pages publiques du site de l'entreprise. Liste UNIQUEMENT les personnes dont le NOM COMPLET et le POSTE "
        "sont ecrits explicitement sur ces pages et qui sont : fondateur / co-fondateur / CEO / dirigeant / proprietaire, ou responsable "
        "marketing / contenu / communication / podcast. N'invente rien, ne deduis rien. Si une adresse email est ecrite a cote de la personne, "
        "recopie-la dans email, sinon laisse vide.\n"
        'Reponds en JSON strict : {"people":[{"name":"","role":"","email":"","page":""}]} (liste vide si rien de sur).\n\n' + corpus)
    body = json.dumps({"model": MODEL, "max_tokens": 600, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.loads(r.read().decode())
        txt = "".join(b.get("text", "") for b in out.get("content", []))
        m = re.search(r"\{.*\}", txt, re.S)
        return (json.loads(m.group(0)).get("people") or []) if m else []
    except Exception as e:
        log(f"  claude: {e}")
        return []


def find_contact(slug, prospect, pods):
    rec = pods.get(slug) or {}
    host_hint = " ".join(x for x in (rec.get("host_name"), prospect.get("Hote")) if x and str(x).strip().lower() not in ("undefined", "null", "n/a"))[:120]
    base = site_for(slug, prospect, pods)
    result = {"nom": "", "poste": "", "email": "", "source": "", "fiabilite": ""}
    if not base:
        result["fiabilite"] = "Pas de site d'entreprise trouve"
        return result, ""
    pages = fetch_site(base)
    if not pages:
        result["fiabilite"] = "Site inaccessible"
        return result, base
    # emails ecrits sur le site (meme domaine uniquement)
    dom = domain_of(base)
    site_emails = set()
    for _, html in pages:
        for e in EMAIL_RE.findall(html):
            e = e.lower()
            if domain_of(e).endswith(dom) and not email_problem(e):
                site_emails.add(e)
    people = ask_claude(prospect.get("Podcast", ""), host_hint, [(p, to_text(h)) for p, h in pages])
    people = [p for p in people if isinstance(p, dict) and len((p.get("name") or "").split()) >= 2 and role_rank(p.get("role")) < 9]
    people.sort(key=lambda p: role_rank(p.get("role")))
    if not people:
        result["fiabilite"] = "Aucun decideur nomme sur le site"
        return result, base
    best = people[0]
    email = (best.get("email") or "").strip().lower()
    first = best["name"].split()[0].lower()
    if not email or email_problem(email) or not domain_of(email).endswith(dom):
        email = next((e for e in sorted(site_emails) if e.split("@")[0].startswith(first[:3])), "")
    result.update({"nom": best["name"].strip(), "poste": (best.get("role") or "").strip()[:80],
                   "email": email, "source": base})
    result["fiabilite"] = ("Haute : e-mail ecrit sur le site (" + dt_today() + ")") if email else ("Moyenne : nom + poste trouves, e-mail a verifier (" + dt_today() + ")")
    return result, base


def dt_today():
    return datetime.date.today().strftime("%d/%m/%Y")


def score(prospect, rec, contact_rank, added_recent):
    s = 0
    dom = domain_of(prospect.get("Email", ""))
    if corporate_domain(dom):
        s += 25
    if rec.get("host_company") or rec.get("host_title"):
        s += 10
    try:
        qr = int(prospect.get("Q/R extraites") or 0)
    except (TypeError, ValueError):
        qr = 0
    s += 15 if qr >= 15 else 8 if qr >= 5 else 0
    if prospect.get("Dernier épisode Q") and prospect.get("Dernier épisode Moment ID"):
        s += 15
    if str(prospect.get("Thematique", "")).strip():
        s += 10
    s += {1: 15, 2: 12}.get(contact_rank, 0)
    if added_recent:
        s += 5
    cat = str(rec.get("categorie") or "")
    if cat and not re.search(r"divertissement|loisir|sport|musique|jeux|humour|true crime|fiction", cat, re.I):
        s += 5
    return min(100, s)


def main():
    if not sheet_bridge.URL:
        log("MFE_SHEET_URL absent : rien a faire")
        return 0
    state = load(STATE_FILE, {})
    pods = {p["slug"]: p for p in load(PODCASTS_FILE, []) if isinstance(p, dict) and p.get("slug")}
    try:
        data = sheet_bridge.call({"action": "status"})
    except Exception as e:
        log(f"Sheet injoignable : {e}")
        return 0
    prospects = [p for p in data.get("prospects", []) if p.get("Slug")]
    today = datetime.date.today()
    log(f"{len(prospects)} prospects dans le Sheet")

    def old_enough(slug):
        d = (state.get(slug) or {}).get("date")
        if not d:
            return True
        try:
            return (today - datetime.date.fromisoformat(d)).days >= REFRESH_DAYS
        except ValueError:
            return True

    todo = [p for p in prospects if p.get("Statut") == "Pret" and old_enough(p["Slug"])]
    todo.sort(key=lambda p: (0 if (p.get("Dernier épisode Q") and p.get("Dernier épisode Moment ID")) else 1))
    todo = todo[:MAX_RUN]
    log(f"{len(todo)} prospects a rechercher ce passage")

    rows, found = {}, 0
    for p in todo:
        slug = p["Slug"]
        try:
            res, base = find_contact(slug, p, pods)
        except Exception as e:  # un site qui plante ne doit jamais arreter le module
            log(f"  {slug}: erreur {type(e).__name__}")
            res, base = {"nom": "", "poste": "", "email": "", "source": "", "fiabilite": "Erreur de recherche"}, ""
        rank = role_rank(res["poste"]) if res["nom"] else 9
        st = state.setdefault(slug, {})
        st.update({"date": today.isoformat(), "trouve": bool(res["nom"]), "email_trouve": bool(res["email"]), "rang": rank})
        rows[slug] = {"slug": slug, **res}
        found += 1 if res["nom"] else 0
        log(f"  {slug}: {'decideur trouve (' + res['fiabilite'].split(':')[0] + ')' if res['nom'] else res['fiabilite']}")

    # scores : recalcules pour tous (sans reseau) ; on n'envoie que ce qui a change
    push = {}
    for p in prospects:
        slug = p["Slug"]
        st = state.setdefault(slug, {})
        added = str(p.get("Ajoute le") or "")
        recent = False
        m = re.search(r"(\d{2})/(\d{2})/(\d{4})", added) or None
        try:
            if m:
                recent = (today - datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))).days <= 30
            elif re.match(r"\d{4}-\d{2}-\d{2}", added):
                recent = (today - datetime.date.fromisoformat(added[:10])).days <= 30
        except ValueError:
            pass
        sc = score(p, pods.get(slug) or {}, st.get("rang", 9), recent)
        if st.get("score") != sc or slug in rows:
            st["score"] = sc
            push[slug] = {**rows.get(slug, {"slug": slug}), "score": sc}
    log(f"decideurs trouves : {found}/{len(todo)} ; lignes a ecrire dans le Sheet : {len(push)}")

    if DRY:
        log("CONTACT_DRY=1 : aucune ecriture")
    elif push:
        items = list(push.values())
        for i in range(0, len(items), 120):
            try:
                r = sheet_bridge.call(payload={"action": "contacts", "rows": items[i:i + 120]})
                log(f"Sheet : {r}")
            except Exception as e:
                log(f"ecriture Sheet impossible ({e}) : sera retente au prochain passage")
                for it in items[i:i + 120]:   # on oublie le score pour que la ligne soit renvoyee
                    state.get(it["slug"], {}).pop("score", None)
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

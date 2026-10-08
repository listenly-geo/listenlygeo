#!/usr/bin/env python3
"""
Module "Qui contacter" du MarketForge Engine (V2.5) : tourne A COTE du moteur, ne touche ni a l'envoi ni a l'extraction.

Pour chaque prospect du Sheet (statut "Pret" d'abord) :
  1. calcule un SCORE DE PRIORITE (0-100) : entreprise B2B, contenu extrait, question prete, decideur identifie...
  2. cherche le FONDATEUR / DIRIGEANT / RESPONSABLE MARKETING-CONTENT-PODCAST sur le site public du podcast
     (pages accueil / a propos / equipe / contact), via Claude qui n'extrait QUE des noms ecrits sur ces pages.
  3. ecrit le resultat dans les colonnes S a X du Sheet (action web "contacts"). Les colonnes A-R ne sont jamais modifiees.

V2.6 (cascade d'adresses) : pour chaque dirigeant nomme, 1) e-mail ecrit sur le site (fiabilite "Haute") ; sinon 2) adresse DEDUITE
(prenom@domaine puis prenom.nom@domaine) puis CONFIRMEE "Valid" par MyEmailVerifier via l'action web "verify" du script Google
(la cle reste dans le script) ; 3) sinon aucun e-mail (le mail part comme avant a l'adresse du flux).

Regles : une adresse n'est ecrite dans le Sheet que si elle est ecrite sur le site de l'entreprise OU confirmee "Valid" ; jamais une
adresse seulement devinee. Domaines "attrape-tout" (Catch All) = aucune adresse deduite. Filtre rss_contact.email_problem partout.
Aucun nom ni email n'est ecrit dans le depot ni dans les journaux (publics) : seul contact_state.json (dates, drapeaux, scores,
domaines d'entreprise attrape-tout, resume chiffre du dernier passage) est commite.

  python contact_finder.py            : un passage (MAX_PAR_RUN prospects recherches)
Variables : MFE_SHEET_URL, ANTHROPIC_API_KEY, CONTACT_MAX (defaut 40), CONTACT_DRY (1 = n'ecrit pas dans le Sheet),
CONTACT_VERIFY (0 = ne verifie rien, defaut 1), CONTACT_VERIF_MAX (verifications par passage, defaut 30),
CONTACT_VERIF_PAR_PODCAST (defaut 4), CONTACT_HOST (0 = n'utilise pas l'animateur comme candidat, defaut 1)
"""
import os, re, sys, time, json, datetime, unicodedata, collections, urllib.request, urllib.parse
from urllib.parse import urlparse, urljoin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet_bridge  # noqa: E402
from rss_contact import email_problem, EMAIL_RE, fetch_channel_info  # noqa: E402

STATE_FILE = "automation/marketforge_engine/contact_state.json"
PODCASTS_FILE = "pages/podcast-btb/data/podcasts.json"
MAX_RUN = int(os.environ.get("CONTACT_MAX", "40") or 40)
DRY = os.environ.get("CONTACT_DRY", "") == "1"
REFRESH_DAYS = 30
ALGO_VERSION = 3   # 2 = cascade d'adresses (V2.6) : les prospects traites avec l'ancienne version sont refaits
VERIFY = os.environ.get("CONTACT_VERIFY", "1") != "0"
VERIF_MAX = int(os.environ.get("CONTACT_VERIF_MAX", "30") or 30)
VERIF_PAR_PODCAST = int(os.environ.get("CONTACT_VERIF_PAR_PODCAST", "4") or 4)
USE_HOST = os.environ.get("CONTACT_HOST", "1") != "0"
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


TITLES = {"dr", "mr", "mrs", "ms", "mx", "prof", "sir", "madam"}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "phd", "md", "cpa", "esq", "mba", "cfa", "pmp", "dds"}
CORP = re.compile(r"\b(podcast|media|inc|llc|ltd|team|studio|studios|network|group|company|agency|productions?|radio|news|show|hq|"
                  r"talks?|capital|partners|ventures|digital|labs?|consulting|institute|association|foundation|university|magazine|"
                  r"journal|press|publishing|tv|fm|live|daily|weekly|global|international|solutions|systems|advisors?|associates|"
                  r"official|channel|hub|works|academy|collective|club)\b|&|\d", re.I)
SUB_LABELS = {"www", "podcast", "podcasts", "show", "shows", "listen", "blog", "media", "pod", "audio"}


def person_like(name):
    """Vrai si le texte ressemble a un nom de personne (2 a 3 mots avec majuscule, pas un nom de societe ou de podcast)."""
    n = (name or "").strip()
    if not n or CORP.search(n) or re.search(r"undefined|null|n/a|[{}@]|http", n, re.I):
        return False
    w = n.split()
    return 2 <= len(w) <= 3 and all(re.fullmatch(r"[A-Z][A-Za-z\u00C0-\u00FF'\u2019.-]+", x) for x in w)


def name_parts(full):
    """'Dr. Jean-Pierre O'Neil Jr.' -> ('jeanpierre', 'oneil') ; None si prenom ou nom manque. Sans accents, lettres seulement."""
    s = unicodedata.normalize("NFKD", full or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\([^)]*\)|\"[^\"]*\"", " ", s)
    toks = [t.strip(".") for t in re.split(r"[\s,]+", s) if t.strip(".")]
    toks = [t for t in toks if t.lower() not in TITLES and t.lower() not in SUFFIXES]
    if len(toks) < 2:
        return None
    clean = lambda x: re.sub(r"[^a-z]", "", x.lower())
    f, l = clean(toks[0]), clean(toks[-1])
    return (f, l) if len(f) >= 2 and len(l) >= 2 else None


def mail_domain(site_domain):
    """Domaine de messagerie probable : retire un sous-domaine 'podcast.' / 'www.' (podcast.acme.com -> acme.com)."""
    labels = (site_domain or "").lower().split(".")
    while len(labels) > 2 and labels[0] in SUB_LABELS:
        labels = labels[1:]
    return ".".join(labels)


def candidate_addresses(name, dom):
    """Formats testes, du plus courant au moins courant : prenom@ puis prenom.nom@ (aucune adresse n'est ecrite sans verification)."""
    parts = name_parts(name)
    if not parts or not dom:
        return []
    f, l = parts
    out = []
    for a in (f"{f}@{dom}", f"{f}.{l}@{dom}"):
        if a not in out and not email_problem(a):
            out.append(a)
    return out


VERIF_RAISON = ""   # derniere cause d'indisponibilite (sans adresse ni cle), pour le resume


def verify_email(email):
    """Statut MyEmailVerifier via le script Google : valid | invalid | catchall | unknown | greylisted | disposable | refuse |
    quota | indisponible. Reessaie jusqu'a 3 fois si le script repond de travers (reponse passagere de Google)."""
    global VERIF_RAISON
    st = "indisponible"
    for attempt in range(3):
        try:
            r = sheet_bridge.call(payload={"action": "verify", "emails": [email]})
        except Exception as e:
            VERIF_RAISON = ("appel impossible : " + type(e).__name__ + " " + str(e))[:90]
        else:
            if isinstance(r, dict) and r.get("ok"):
                st = str((r.get("results") or {}).get(email, "indisponible"))
                if st != "indisponible":
                    return st
                VERIF_RAISON = "script joint, mais MyEmailVerifier sans reponse exploitable (cle, credits ou autorisation)"
            else:
                VERIF_RAISON = ("reponse du script : " + str(r).replace(email, "<adresse>"))[:120]
        if attempt < 2:
            time.sleep(3 * (attempt + 1))
    return "indisponible"


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


INBOX_ROOT = "automation/inbox/moteur-trafic-transcripts"


def intro_text(slug, n=2800):
    """Debut de la transcription d'un episode deja extrait (la, l'animateur se presente)."""
    d = os.path.join(INBOX_ROOT, slug)
    try:
        files = sorted(f for f in os.listdir(d) if f.endswith(".json"))
    except OSError:
        return ""
    for f in files[:3]:
        t = (load(os.path.join(d, f), {}).get("transcript_full") or "").strip()
        if len(t) > 300:
            return t[:n]
    return ""


def host_from_transcript(podcast, slug):
    """Nom complet de l'animateur, dit a voix haute dans l'intro d'un episode. '' si aucun nom complet clair."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    intro = intro_text(slug)
    if not key or not intro:
        return ""
    prompt = (f"Podcast : {podcast}. Voici le debut de la transcription d'un episode.\n"
              "Qui est l'ANIMATEUR principal (celui qui presente l'emission) ? Reponds uniquement si son NOM COMPLET (prenom et nom) "
              "est prononce dans ce texte (ex. \"I'm Jane Doe\", \"this is John Smith\"). N'invente rien, ne devine pas a partir du nom du "
              "podcast, ignore les invites. Reponds en JSON strict : {\"host\":\"\"} (chaine vide si pas sur).\n\n" + intro)
    body = json.dumps({"model": MODEL, "max_tokens": 80, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            out = json.loads(r.read().decode())
        m = re.search(r"\{.*\}", "".join(b.get("text", "") for b in out.get("content", [])), re.S)
        h = str((json.loads(m.group(0)) if m else {}).get("host") or "").strip()
        return h if person_like(h) else ""
    except Exception as e:
        log(f"  claude (animateur): {e}")
        return ""


def find_contact(slug, prospect, pods, ctx):
    """Cascade : 1) e-mail ecrit sur le site, 2) adresse deduite puis confirmee 'Valid', 3) rien (le mail part comme avant).
    ctx : {"state": dict, "verif_left": int, "verif_ok": bool, "stats": dict} (compteurs partages entre prospects)."""
    rec = pods.get(slug) or {}
    host_raw = " ".join(x for x in (rec.get("host_name"), prospect.get("Hote")) if x and str(x).strip().lower() not in ("undefined", "null", "n/a"))[:120]
    base = site_for(slug, prospect, pods)
    result = {"nom": "", "poste": "", "email": "", "source": "", "fiabilite": "", "verifie": False, "ecrit_site": False}
    stats = ctx["stats"]
    if not base:
        result["fiabilite"] = "Pas de site d'entreprise trouve"
        return result, ""
    pages = fetch_site(base)   # peut etre vide : l'animateur (transcription, flux) suffit pour deduire une adresse
    dom = domain_of(base)
    mdom = mail_domain(dom)
    # emails ecrits sur le site (meme domaine uniquement)
    site_emails = set()
    for _, html in pages:
        for e in EMAIL_RE.findall(html):
            e = e.lower()
            if domain_of(e).endswith(mdom) and not email_problem(e):
                site_emails.add(e)
    people = ask_claude(prospect.get("Podcast", ""), host_raw, [(p, to_text(h)) for p, h in pages])
    people = [p for p in people if isinstance(p, dict) and len((p.get("name") or "").split()) >= 2 and role_rank(p.get("role")) < 9]
    people.sort(key=lambda p: role_rank(p.get("role")))
    # candidat de repli : l'animateur du podcast (poste non confirme), seulement s'il ressemble a une personne et n'est pas deja dans la liste
    if USE_HOST:
        th = host_from_transcript(prospect.get("Podcast", ""), slug)
        tp = name_parts(th) if th else None
        if tp and not any((name_parts(p.get("name")) or ("", ""))[1] == tp[1] for p in people):
            people.append({"name": th, "role": "Animateur du podcast (nom entendu dans l'episode)", "email": "", "page": "", "_host": True, "_transcript": True})
    if USE_HOST and person_like(host_raw):
        hp = name_parts(host_raw)
        if hp and not any((name_parts(p.get("name")) or ("", ""))[1] == hp[1] for p in people):
            people.append({"name": host_raw, "role": "Animateur du podcast (poste non confirme)", "email": "", "page": "", "_host": True})
    if not people:
        stats["sans_nom"] += 1
        result["fiabilite"] = "Aucun nom trouve (site, transcription, flux)"
        return result, base
    stats["noms"] += 1
    first_person = people[0]
    if first_person.get("_host"):
        stats["animateur_seul"] += 1
        if first_person.get("_transcript"):
            stats["nom_transcription"] += 1
    result.update({"nom": first_person["name"].strip(), "poste": (first_person.get("role") or "").strip()[:80], "source": base})
    dates = dt_today()
    dcache = ctx["state"].setdefault("_domaines", {})
    tested = 0
    for person in people[:3]:
        name, role = person["name"].strip(), (person.get("role") or "").strip()[:80]
        pfirst = (name_parts(name) or ("", ""))[0]
        # 1) e-mail ecrit sur le site, a cote de la personne ou commencant par son prenom
        em = (person.get("email") or "").strip().lower()
        if not em or email_problem(em) or not domain_of(em).endswith(mdom):
            em = next((e for e in sorted(site_emails) if pfirst and e.split("@")[0].startswith(pfirst[:3])), "")
        if em:
            result.update({"nom": name, "poste": role, "email": em, "ecrit_site": True,
                           "fiabilite": "Haute : e-mail ecrit sur le site (" + dates + ")"})
            stats["ecrit_site"] += 1
            return result, base
        # 2) adresse deduite puis confirmee
        if not VERIFY or not ctx["verif_ok"] or dcache.get(mdom, {}).get("statut") == "catchall" and _recent(dcache[mdom].get("date")):
            if dcache.get(mdom, {}).get("statut") == "catchall":
                stats["domaines_attrape_tout"] += 1
            continue
        for addr in candidate_addresses(name, mdom):
            if tested >= VERIF_PAR_PODCAST or ctx["verif_left"] <= 0 or not ctx["verif_ok"]:
                break
            tested += 1
            ctx["verif_left"] -= 1
            stats["testees"] += 1
            st = verify_email(addr)
            stats["statut_" + st] = stats.get("statut_" + st, 0) + 1
            if st == "valid":
                fmt = "prenom@" if addr.split("@")[0] == pfirst else "prenom.nom@"
                result.update({"nom": name, "poste": role, "email": addr, "verifie": True,
                               "fiabilite": f"Verifiee ({fmt}) le {dates}"})
                dcache[mdom] = {"statut": "ok", "date": datetime.date.today().isoformat()}
                stats["verifiees"] += 1
                return result, base
            if st == "catchall":
                dcache[mdom] = {"statut": "catchall", "date": datetime.date.today().isoformat()}
                stats["domaines_attrape_tout"] += 1
                break   # tout est "valide" sur ce domaine : inutile d'insister
            if st in ("quota", "indisponible"):
                ctx["verif_ok"] = False
                break
        if dcache.get(mdom, {}).get("statut") == "catchall":
            break   # meme domaine pour tout le monde
    if not ctx["verif_ok"]:
        result["fiabilite"] = "Nom + poste trouves, verification indisponible (" + dates + ")"
    elif dcache.get(mdom, {}).get("statut") == "catchall":
        result["fiabilite"] = "Domaine attrape-tout : adresse non verifiable (" + dates + ")"
    elif tested:
        result["fiabilite"] = "Aucun format d'adresse confirme (" + dates + ")"
    else:
        result["fiabilite"] = "Nom + poste trouves, e-mail non confirme (" + dates + ")"
    return result, base


def _recent(iso, days=30):
    try:
        return (datetime.date.today() - datetime.date.fromisoformat(iso)).days < days
    except (TypeError, ValueError):
        return False


def dt_today():
    return datetime.date.today().strftime("%d/%m/%Y")


def score(prospect, rec, contact_rank, added_recent, email_ok=False):
    s = 5 if email_ok else 0   # adresse de dirigeant utilisable (verifiee ou ecrite sur le site)
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
        if (state.get(slug) or {}).get("v", 1) < ALGO_VERSION:
            return True   # traite avec l'ancienne version (sans adresses deduites) : on refait
        d = (state.get(slug) or {}).get("date")
        if not d:
            return True
        try:
            return (today - datetime.date.fromisoformat(d)).days >= REFRESH_DAYS
        except ValueError:
            return True

    todo = [p for p in prospects if p.get("Statut") == "Pret" and old_enough(p["Slug"])]
    # d'abord ceux ou un decideur avait deja ete nomme (meilleur rendement), puis ceux qui ont une question prete
    todo.sort(key=lambda p: (0 if (state.get(p["Slug"]) or {}).get("trouve") else 1,
                             0 if (p.get("Dernier épisode Q") and p.get("Dernier épisode Moment ID")) else 1))
    todo = todo[:MAX_RUN]
    log(f"{len(todo)} prospects a rechercher ce passage")

    stats = collections.defaultdict(int)
    ctx = {"state": state, "verif_left": VERIF_MAX if VERIFY else 0, "verif_ok": VERIFY, "stats": stats}
    rows, found = {}, 0
    for p in todo:
        slug = p["Slug"]
        try:
            res, base = find_contact(slug, p, pods, ctx)
        except Exception as e:  # un site qui plante ne doit jamais arreter le module
            log(f"  {slug}: erreur {type(e).__name__}")
            res, base = {"nom": "", "poste": "", "email": "", "source": "", "fiabilite": "Erreur de recherche", "verifie": False, "ecrit_site": False}, ""
        rank = role_rank(res["poste"]) if res["nom"] else 9
        if not DRY:   # un essai (CONTACT_DRY=1) ne marque rien comme traite : le vrai passage refera ces prospects
            st = state.setdefault(slug, {})
            st.update({"v": ALGO_VERSION, "date": today.isoformat(), "trouve": bool(res["nom"]), "email_trouve": bool(res["email"]),
                       "verifie": bool(res.get("verifie")), "rang": rank})
        rows[slug] = {"slug": slug, **{k: res[k] for k in ("nom", "poste", "email", "source", "fiabilite")}}
        found += 1 if res["nom"] else 0
        # jamais de nom ni d'adresse dans les journaux (publics) : seulement le type de resultat
        log(f"  {slug}: {'adresse ' + ('verifiee' if res.get('verifie') else 'ecrite sur le site') if res['email'] else ('nom trouve, pas d adresse' if res['nom'] else res['fiabilite'])}")
    emails_ok = sum(1 for r in rows.values() if r["email"])
    state["_resume"] = {"date": today.isoformat(), "traites": len(todo), "noms": found, "adresses_utilisables": emails_ok,
                        "verifications": VERIF_MAX - ctx["verif_left"] if VERIFY else 0, "detail": dict(stats), "raison_indispo": VERIF_RAISON,
                        "ecriture_sheet": not DRY}
    log(f"RESUME : {len(todo)} traites, {found} avec un nom, {emails_ok} avec une adresse utilisable, detail {dict(stats)}" + (f" | verification indisponible : {VERIF_RAISON}" if VERIF_RAISON else ""))

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
        sc = score(p, pods.get(slug) or {}, st.get("rang", 9), recent, bool(st.get("email_trouve")))
        if st.get("score") != sc or (slug in rows and not DRY):
            if not DRY:
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

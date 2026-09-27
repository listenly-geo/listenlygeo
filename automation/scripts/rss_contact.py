"""
Extraction de l'email de contact d'un podcast depuis son flux RSS (aucun appel API payant).

Ordre de priorite : itunes:owner/itunes:email (obligatoire pour Apple Podcasts) ->
itunes:email au niveau channel -> managingEditor -> webMaster -> podcast:... autres
balises contenant un email. Renvoie "" si rien de fiable n'est trouve.
Utilise par discover_podcasts.py et marketforge_extract_queue.py.
"""
import re
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
IGNORED = ("example.com", "noreply", "no-reply", "donotreply")

# --- Anti-rebond (27/09/2026) : 6 rebonds sur 23 envois (26 %) au premier lot ---
# Adresses d'hebergeurs / plateformes : generees automatiquement, rarement lues -> rebond ou silence.
BLOCKED_DOMAINS = (
    "anchor.fm", "spotify.com", "spreaker.com", "libsyn.com", "megaphone.fm", "buzzsprout.com",
    "podbean.com", "simplecast.com", "transistor.fm", "captivate.fm", "acast.com", "omny.fm",
    "omnystudio.com", "soundcloud.com", "iheart.com", "iheartmedia.com", "audioboom.com", "redcircle.com",
    "art19.com", "pinecast.com", "blubrry.com", "podcastics.com", "ausha.co", "podomatic.com",
    "castos.com", "fireside.fm", "podigee.com", "riverside.fm", "zencast.fm", "whooshkaa.com",
    "example.com", "example.org", "test.com", "domain.com", "email.com",
)
# Boites techniques : jamais lues par un humain.
BLOCKED_LOCAL = re.compile(
    r"^(no-?reply|do-?not-?reply|noreply\d*|feeds?|rss|bounces?|postmaster|mailer-daemon|abuse|dmca|"
    r"copyright|unsubscribe|privacy|legal|billing|invoices?|accounting|applepodcasts?|itunes|"
    r"podcasts?\d+(\+.*)?)$")


def email_problem(email):
    """"" si l'adresse est envoyable, sinon la raison (texte court). Sans reseau."""
    email = (email or "").strip().lower()
    if not EMAIL_RE.fullmatch(email):
        return "format invalide"
    local, domain = email.rsplit("@", 1)
    if any(domain == d or domain.endswith("." + d) for d in BLOCKED_DOMAINS):
        return f"adresse d'hebergeur ({domain})"
    if BLOCKED_LOCAL.match(local.split("+")[0]) or BLOCKED_LOCAL.match(local):
        return f"boite technique ({local}@)"
    return ""


_MX_CACHE = {}


def domain_accepts_mail(domain, timeout=10):
    """True si le domaine a un MX (ou a defaut une IP) — via DNS-over-HTTPS Google. Doute -> True."""
    domain = domain.lower()
    if domain in _MX_CACHE:
        return _MX_CACHE[domain]
    ok = True
    try:
        for rtype in ("MX", "A"):
            url = "https://dns.google/resolve?" + urllib.parse.urlencode({"name": domain, "type": rtype})
            with urllib.request.urlopen(url, timeout=timeout) as r:
                d = json.loads(r.read())
            if d.get("Status") == 3:        # NXDOMAIN : le domaine n'existe pas
                ok = False
                break
            if any(a.get("type") in (15, 1) for a in d.get("Answer", [])):
                ok = True
                break
            ok = False
    except Exception:
        ok = True  # reseau indisponible : on ne bloque pas
    _MX_CACHE[domain] = ok
    return ok


def check_email(email):
    """"" si envoyable (regles + domaine qui recoit des mails), sinon la raison."""
    why = email_problem(email)
    if why:
        return why
    if not domain_accepts_mail(email.rsplit("@", 1)[1]):
        return "domaine sans serveur mail"
    return ""


def _clean(text):
    for m in EMAIL_RE.finditer(text or ""):
        email = m.group(0).strip().strip(".").lower()
        if any(x in email for x in IGNORED) or email_problem(email):
            continue
        return email
    return ""


def extract_contact_email(xml_bytes):
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return _clean(xml_bytes.decode("utf-8", "ignore")[:20000]) if isinstance(xml_bytes, bytes) else ""
    channel = root.find("channel")
    if channel is None:
        return ""
    candidates = []
    owner = channel.find(f"{ITUNES}owner")
    if owner is not None:
        candidates.append(owner.findtext(f"{ITUNES}email"))
    candidates.append(channel.findtext(f"{ITUNES}email"))
    candidates.append(channel.findtext("managingEditor"))
    candidates.append(channel.findtext("webMaster"))
    for el in channel:  # autres balises niveau channel (podcast:person, author...)
        if el.tag.endswith("item"):
            continue
        candidates.append(el.text)
    for c in candidates:
        email = _clean(c)
        if email:
            return email
    return ""


def fetch_contact_email(rss_url, timeout=20):
    try:
        req = urllib.request.Request(rss_url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; ListenlyGEO/1.0; +https://listenly.fr)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return extract_contact_email(resp.read())
    except Exception:
        return ""


def fetch_channel_info(rss_url, timeout=20):
    """Email + description publique du podcast (channel description / itunes:summary), texte brut."""
    try:
        req = urllib.request.Request(rss_url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; ListenlyGEO/1.0; +https://listenly.fr)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            xml_bytes = resp.read()
    except Exception:
        return {"email": "", "description": ""}
    desc = ""
    try:
        channel = ET.fromstring(xml_bytes).find("channel")
        if channel is not None:
            desc = channel.findtext("description") or channel.findtext(f"{ITUNES}summary") or ""
    except ET.ParseError:
        pass
    desc = re.sub(r"<[^>]+>", " ", desc)
    desc = re.sub(r"\s+", " ", desc).strip()[:2000]
    return {"email": extract_contact_email(xml_bytes), "description": desc}

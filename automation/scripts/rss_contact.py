"""
Extraction de l'email de contact d'un podcast depuis son flux RSS (aucun appel API payant).

Ordre de priorite : itunes:owner/itunes:email (obligatoire pour Apple Podcasts) ->
itunes:email au niveau channel -> managingEditor -> webMaster -> podcast:... autres
balises contenant un email. Renvoie "" si rien de fiable n'est trouve.
Utilise par discover_podcasts.py et marketforge_extract_queue.py.
"""
import re
import urllib.request
import xml.etree.ElementTree as ET

ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
IGNORED = ("example.com", "noreply", "no-reply", "donotreply")


def _clean(text):
    m = EMAIL_RE.search(text or "")
    if not m:
        return ""
    email = m.group(0).strip().strip(".").lower()
    return "" if any(x in email for x in IGNORED) else email


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

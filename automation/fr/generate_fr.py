#!/usr/bin/env python3
"""
GENERATEUR FRANCAIS INDEPENDANT (17/11/2026) : un flux RSS en entree, des fiches moment en francais en sortie.

Totalement separe du moteur trafic americain :
  - ne lit ni n'ecrit aucun fichier du moteur (podcasts.json, queue.json, moments/, sitemaps, Sheet MarketForge...) ;
  - tout vit dans pages/podcast-btb/fr/ (donnees, pages, sitemap) ;
  - ne reutilise que des fonctions de lecture/transcription (generate_episode_fiches_btb.py) SANS les modifier.

Ce que fait un lancement (un seul podcast, quelques episodes) :
  1. lit le flux RSS (nom, pochette, description, episodes) ;
  2. cree la fiche podcast sur Listenly et enregistre le flux (comme le moteur americain, via les memes API) ;
  3. transcrit les N derniers episodes (Whisper via Groq, uniquement les premieres minutes) ;
  4. extrait les vraies questions/reponses avec leurs minutages (Claude Haiku), en francais ;
  5. rallonge chaque reponse (2 paragraphes) et ecrit un titre Google court ;
  6. ecrit les pages : fr/data/moments/<slug>.json (lu par fr/m.php), le hub fr/<slug>.html, fr/sitemap-fr.xml ;
  7. ecrit fr/data/derniere_generation.json : les liens des fiches moment (lus par la page du generateur).

Variables d'environnement :
  RSS_URL (obligatoire) | EPISODES (defaut 3) | MINUTES_AUDIO (defaut 25, 0 = episode entier)
  QUESTIONS_PAR_EPISODE (defaut 4) | DRY_RUN=1 (lit le flux et planifie, n'ecrit rien, n'appelle aucune API payante)
  PUSH_LISTENLY=1 (defaut) : pousse aussi les moments dans la recherche Listenly (base) | HUB_INDEX=1 : hub indexable
  Secrets : ANTHROPIC_API_KEY, GROQ_API_KEY, KNOWLEDGE_IMPORT_SECRET
"""
import os, sys, re, json, time, glob, hashlib, datetime, tempfile, shutil, subprocess, importlib.util
import urllib.request, urllib.error
import xml.etree.ElementTree as ET

ROOT = "pages/podcast-btb/fr"
DATA = f"{ROOT}/data"
MOMENTS_DIR = f"{DATA}/moments"
KNOW_DIR = f"{DATA}/knowledge_moments"
PODCASTS_FILE = f"{DATA}/podcasts.json"
SITE = "https://listenly.org/podcast-btb/fr"
SHOW_IMPORT_URL = os.environ.get("SHOW_IMPORT_URL", "https://listenly.org/api/podcast-show-import.php")
RSS_READER_URL = os.environ.get("RSS_READER_URL", "https://listenly.org/api/rss-reader-register.php")
SECRET = os.environ.get("KNOWLEDGE_IMPORT_SECRET", "")
RSS_URL = (os.environ.get("RSS_URL") or "").strip()
EPISODES = max(1, int(os.environ.get("EPISODES") or 3))
MINUTES = max(0, int(os.environ.get("MINUTES_AUDIO") or 25))
Q_MAX = max(1, int(os.environ.get("QUESTIONS_PAR_EPISODE") or 4))
DRY = (os.environ.get("DRY_RUN") or "").strip().lower() in ("1", "true", "yes")
PUSH = (os.environ.get("PUSH_LISTENLY") or "1").strip().lower() not in ("0", "false", "no")
HUB_INDEX = (os.environ.get("HUB_INDEX") or "").strip().lower() in ("1", "true", "yes")
MODEL = "claude-haiku-4-5-20251001"
TODAY = datetime.date.today().isoformat()
NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}


def log(msg):
    print(f"[fr] {msg}", flush=True)


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


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower().encode("ascii", "ignore").decode() or "")
    return s.strip("-")[:40].strip("-") or "podcast"


def moment_id(slug, question):
    return hashlib.sha1(f"{slug}|{norm(question)}".encode("utf-8")).hexdigest()[:10]


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def clean(s, n=0):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n].rsplit(" ", 1)[0] + "…" if n and len(s) > n else s


# ---------------------------------------------------------------- Claude (Haiku)
def claude(prompt, max_tokens=700):
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["content"][0]["text"].strip()


def reecrire_fr(question, extrait, texte):
    """Reponse en 2 paragraphes, uniquement a partir de la transcription (meme regle que le moteur americain, en francais)."""
    prompt = (
        "Tu rédiges la section « réponse » d'une page web de questions-réponses tirée d'un podcast, en utilisant UNIQUEMENT la transcription ci-dessous. "
        "N'ajoute jamais un fait absent de la transcription. Écris 2 paragraphes (130 à 200 mots au total), en français, prose simple, "
        "à la troisième personne, avec les détails et chiffres de la transcription, sans remplissage, sans écrire « la transcription ». "
        "Si la transcription ne permet pas de répondre à la question, réponds exactement NONE.\n\n"
        f"QUESTION : {question}\n\nEXTRAIT DÉJÀ CONNU : {extrait}\n\nTRANSCRIPTION :\n{texte[:20000]}\n\n"
        "Réponds par les deux paragraphes séparés par une ligne vide, rien d'autre.")
    t = claude(prompt, 800)
    if t.upper().startswith("NONE"):
        return None
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    if len(paras) < 2 or sum(len(p.split()) for p in paras) < 90:
        return None
    return paras[:3]


def titre_seo_fr(question):
    """Titre Google : question francaise courte + ' | Listenly' (58 caracteres maximum)."""
    suffix = " | Listenly"
    room = 58 - len(suffix)
    for essai in range(2):
        t = claude("Reformule cette question de podcast en une question de recherche Google courte et naturelle, en français, "
                   f"{room - 4 * essai} caractères maximum, point d'interrogation compris, en gardant le sens et les mots-clés "
                   f"principaux. Pas de guillemets, réponds uniquement par la question.\n\n{question}", 80).strip(' "«»\n')
        t = re.sub(r"\s+", " ", t)
        if t and not t.endswith("?"):
            t += " ?" if False else "?"
        t = t[:1].upper() + t[1:]
        if t and len(t + suffix) <= 58:
            return t + suffix
    return question[:room].rsplit(" ", 1)[0] + "?" + suffix if len(question) > room else question + suffix


# ---------------------------------------------------------------- module d'extraction existant (lecture seule)
_m = None


def emod(slug):
    global _m
    if _m is None:
        os.environ["PODCAST_SLUG"] = slug
        os.environ.setdefault("ANTHROPIC_API_KEY", "unused")
        sys.path.insert(0, "automation/scripts")
        spec = importlib.util.spec_from_file_location("ep_module_fr", "automation/scripts/generate_episode_fiches_btb.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["ep_module_fr"] = mod
        spec.loader.exec_module(mod)
        mod.SLUG = slug
        mod.KNOWLEDGE_MOMENTS_DIR = KNOW_DIR        # JSON des moments : dossier FR, jamais celui du moteur americain
        if not PUSH:
            mod.KNOWLEDGE_IMPORT_SECRET = ""        # pas de pousse vers la base Listenly
        _m = mod
    return _m


# ---------------------------------------------------------------- RSS
def channel_info(xml_bytes):
    root = ET.fromstring(xml_bytes)
    ch = root.find("channel")
    if ch is None:
        raise ValueError("Flux RSS invalide : pas de <channel>")

    def txt(tag, ns=None):
        el = ch.find(tag, ns) if ns else ch.find(tag)
        return (el.text or "").strip() if el is not None and el.text else ""

    img = ch.find("itunes:image", NS)
    cover = (img.attrib.get("href", "") if img is not None else "") or ""
    if not cover:
        u = ch.find("image/url")
        cover = (u.text or "").strip() if u is not None and u.text else ""
    return {
        "title": clean(txt("title")), "description": clean(txt("description") or txt("itunes:summary", NS), 900),
        "cover": cover, "author": clean(txt("itunes:author", NS)), "language": txt("language").lower(), "link": txt("link"),
    }


# ---------------------------------------------------------------- Listenly (fiche + flux), memes API que le moteur americain
def post_json(url, payload, retries=(0, 15, 45)):
    last = {"ok": False, "error": "inconnue"}
    for pause in retries:
        if pause:
            time.sleep(pause)
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers={
            "Content-Type": "application/json", "X-Import-Secret": SECRET, "User-Agent": "ListenlyFR/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = {"ok": False, "error": f"HTTP {e.code} : {e.read().decode(errors='ignore')[:200]}"}
            if e.code not in (429, 500, 502, 503, 504):
                return last
        except Exception as e:
            last = {"ok": False, "error": str(e)}
    return last


def create_listenly_show(info):
    if not SECRET:
        log("AVERTISSEMENT : KNOWLEDGE_IMPORT_SECRET absent — fiche Listenly non creee.")
        return ""
    res = post_json(SHOW_IMPORT_URL, {"mode": "insert", "podcast": {
        "title": info["title"], "rss_url": RSS_URL, "cover_image": info["cover"], "author": info["author"],
        "email": "", "language": "fr", "description": info["description"]}})
    log(f"Fiche Listenly : {json.dumps(res, ensure_ascii=False)[:240]}")
    url = res.get("listenly_url") or ""
    reg = post_json(RSS_READER_URL, {"mode": "insert", "link": RSS_URL})
    log(f"Flux RSS enregistre : {json.dumps(reg, ensure_ascii=False)[:200]}")
    return url


# ---------------------------------------------------------------- extraction d'un episode
def fenetre(transcript, segments, t, te):
    """Texte de la transcription autour de la reponse (meilleur contexte pour la reecriture, moins de mots envoyes)."""
    try:
        a, b = max(0, t - 90), (te if te > t else t + 300) + 90
        txt = " ".join(str(s.get("text", "")).strip() for s in segments if a <= float(s.get("start", 0) or 0) <= b).strip()
        if len(txt) > 600:
            return txt
    except Exception:
        pass
    return transcript


def extract_episode(m, podcast, ep):
    tmp = tempfile.mkdtemp(prefix="fr_")
    try:
        audio = os.path.join(tmp, "episode.mp3")
        size = m.download_audio(ep["audio_url"], audio)
        trimmed = False
        if MINUTES:
            try:
                out = os.path.join(tmp, "episode_trim.mp3")
                subprocess.run(["ffmpeg", "-y", "-i", audio, "-t", str(MINUTES * 60), "-vn", "-ac", "1", "-ar", "16000",
                                "-b:a", "32k", out], check=True, capture_output=True)
                audio, size, trimmed = out, os.path.getsize(out), True
                log(f"Audio coupe aux {MINUTES} premieres minutes ({size / 1024 / 1024:.1f} Mo).")
            except Exception as e:
                log(f"Coupe audio impossible ({type(e).__name__}) : episode complet.")
        if not trimmed:
            audio = m.compress_audio_if_needed(audio, size)
        transcript, segments = m.transcribe(audio, "fr")
        if not transcript:
            log("Transcription vide — episode ignore.")
            return []
        guest, qa, quote, stats, entities = m.extract_real_qa(transcript, ep, podcast, segments)
        qa = [q for q in (qa or []) if isinstance(q, dict) and q.get("q") and q.get("r")]
        qa.sort(key=lambda q: -(q.get("score") or 0))
        qa = [q for q in qa if (q.get("score") or 0) >= 6][:Q_MAX]
        if not qa:
            log("Aucune question assez solide dans cet episode.")
            return []
        m.save_knowledge_moments(podcast, ep, guest, qa)     # JSON (dossier FR) + base Listenly
        gname = f"{guest.get('prenom', '')} {guest.get('nom', '')}".strip()
        grole = ", ".join(x for x in [guest.get("titre", ""), guest.get("entreprise", "")] if x)
        out = []
        for q in qa:
            t = int(q.get("start_seconds") or 0)
            te = int(q.get("end_seconds") or 0)
            e = {"q": q["q"].strip(), "a": clean(q["r"], 700), "x": gname, "e": ep["title"], "u": ep["audio_url"], "t": t,
                 "sc": int(q.get("score") or 0)}
            if te > t:
                e["te"] = te
            if grole:
                e["gt"] = grole
            if quote:
                e["rq"] = quote[:400]
            if stats:
                e["ks"] = stats[:6]
            if entities:
                e["en"] = entities[:8]
            try:
                paras = reecrire_fr(e["q"], e["a"], fenetre(transcript, segments, t, te))
            except Exception as ex:
                log(f"Reecriture impossible ({str(ex)[:80]}).")
                paras = None
            if paras:
                e["f"] = paras
                e["enrichi"] = TODAY
            try:
                e["ts"] = titre_seo_fr(e["q"])
            except Exception as ex:
                log(f"Titre Google impossible ({str(ex)[:80]}).")
            out.append(e)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- pages : porte qualite, hub, sitemap
def gate(entries, mid):
    e = entries[mid]
    paras = [p for p in (e.get("f") or []) if str(p).strip()] or ([e["a"]] if e.get("a") else [])
    wc = lambda s: len(re.findall(r"\S+", s or ""))
    related = [o for k, o in entries.items() if k != mid and o.get("e") == e.get("e") and int(o.get("t") or 0) > 0 and len(o.get("a") or "") >= 80]
    score = wc(" ".join(paras)) + wc(" ".join(e.get("ks") or [])) + wc(e.get("rq")) + 8 * min(len(related), 4)
    return len(paras) >= 2 and wc(" ".join(paras)) >= 25 and score >= 90 and int(e.get("t") or 0) > 0 and bool((e.get("x") or "").strip())


def build_hub(rec, entries):
    slug = rec["slug"]
    robots = "" if HUB_INDEX else '<meta name="robots" content="noindex,follow">\n'
    cards = []
    for mid, e in sorted(entries.items(), key=lambda kv: (kv[1].get("e", ""), int(kv[1].get("t") or 0))):
        ts = f"{int(e.get('t') or 0) // 60}:{int(e.get('t') or 0) % 60:02d}"
        cards.append(
            f'<a class="q" href="/podcast-btb/fr/m/{slug}/{mid}"><b>{esc(e["q"])}</b>'
            f'<span>{esc(e.get("x") or "Invité")} · {esc(e.get("e", ""))} · réponse à {ts}</span></a>')
    cover = f'<img src="{esc(rec["cover"])}" alt="{esc(rec["title"])}" width="120" height="120">' if rec.get("cover") else ""
    show = f'<a class="btn" href="{esc(rec["listenly_url"])}">Écouter le podcast sur Listenly</a>' if rec.get("listenly_url") else ""
    page = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(rec["title"])} : toutes les réponses des experts | Listenly</title>
<meta name="description" content="{esc(clean(rec.get("description", ""), 150) or rec["title"])}">
<link rel="canonical" href="{SITE}/{slug}.html">
{robots}<style>
:root{{--bg:#000;--panel:#1C1C1E;--ink:#F5F5F7;--soft:#86868B;--line:rgba(255,255,255,.1);--accent:#2997FF}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Inter,system-ui,sans-serif}}
a{{color:inherit;text-decoration:none}}header{{padding:16px clamp(16px,4vw,40px)}}header a{{font-weight:700;font-size:18px}}
.w{{max-width:760px;margin:0 auto;padding:8px 20px 60px}}.id{{display:flex;gap:18px;align-items:center;margin:8px 0 18px}}.id img{{border-radius:16px;flex:none}}
h1{{font-size:clamp(26px,4vw,36px);letter-spacing:-.02em;margin:0 0 6px}}p.d{{color:#B5B5BA;line-height:1.6;font-size:15.5px}}
.btn{{display:inline-block;background:var(--accent);color:#fff;border-radius:999px;padding:11px 20px;font-weight:600;font-size:14.5px;margin:6px 0 24px}}
h2{{font-size:19px;margin:8px 0 12px}}.q{{display:block;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:0 0 10px}}
.q:hover{{border-color:var(--accent)}}.q b{{display:block;font-size:16px;margin-bottom:4px}}.q span{{color:var(--soft);font-size:13px}}
</style></head><body>
<header><a href="https://listenly.org/">Listenly</a></header>
<div class="w"><div class="id">{cover}<div><h1>{esc(rec["title"])}</h1><div style="color:var(--soft);font-size:14px">{esc(rec.get("author", ""))}</div></div></div>
<p class="d">{esc(rec.get("description", ""))}</p>{show}
<h2>Les réponses de ce podcast</h2>
{chr(10).join(cards)}
</div></body></html>
"""
    os.makedirs(ROOT, exist_ok=True)
    with open(f"{ROOT}/{slug}.html", "w", encoding="utf-8") as f:
        f.write(page)


def build_sitemap():
    urls = []
    for path in sorted(glob.glob(f"{MOMENTS_DIR}/*.json")):
        d = load_json(path, {})
        ents = d.get("entries", {})
        for mid in ents:
            if gate(ents, mid):
                urls.append(f"{SITE}/m/{d.get('slug') or os.path.basename(path)[:-5]}/{mid}")
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    xml += [f"<url><loc>{u}</loc><lastmod>{TODAY}</lastmod></url>" for u in urls]
    xml.append("</urlset>")
    with open(f"{ROOT}/sitemap-fr.xml", "w", encoding="utf-8") as f:
        f.write("\n".join(xml) + "\n")
    return len(urls)


# ---------------------------------------------------------------- principal
def main():
    if not RSS_URL:
        log("ERREUR : RSS_URL manquant.")
        sys.exit(1)
    for k in (["ANTHROPIC_API_KEY", "GROQ_API_KEY"] if not DRY else []):
        if not os.environ.get(k):
            log(f"ERREUR : secret {k} manquant.")
            sys.exit(1)

    m = emod("fr-podcast")
    log(f"Lecture du flux : {RSS_URL}")
    xml = m.fetch_rss(RSS_URL)
    info = channel_info(xml)
    episodes = [e for e in m.parse_episodes(xml) if e.get("audio_url")]
    if not info["title"] or not episodes:
        log("ERREUR : flux sans titre ou sans episode audio.")
        sys.exit(1)
    slug = slugify(info["title"])
    m.SLUG = slug
    lang_ok = info["language"].startswith("fr") or not info["language"]
    log(f"Podcast : {info['title']} (langue du flux : {info['language'] or 'non indiquee'}) — slug {slug} — {len(episodes)} episodes.")
    if not lang_ok:
        log("AVERTISSEMENT : le flux n'annonce pas le francais ; la generation continue en francais.")

    podcasts = load_json(PODCASTS_FILE, [])
    rec = next((p for p in podcasts if p.get("rss_url") == RSS_URL or p.get("slug") == slug), None)
    if rec is None:
        rec = {"slug": slug, "rss_url": RSS_URL, "added": TODAY, "episodes_done": []}
        podcasts.append(rec)
    rec.update({"title": info["title"], "podcast_name": info["title"], "description": info["description"], "cover": info["cover"],
                "author": info["author"]})
    todo = [e for e in episodes if e["guid"] not in rec["episodes_done"]][:EPISODES]
    log(f"{len(todo)} episode(s) a traiter (les {EPISODES} plus recents pas encore faits), "
        f"audio limite a {MINUTES or 'tout'} min, {Q_MAX} question(s) max par episode.")
    for e in todo:
        log(f"  - {e['title'][:90]}")
    if DRY:
        log("DRY_RUN : rien n'est ecrit, aucune API payante appelee.")
        return

    if not rec.get("listenly_url"):
        rec["listenly_url"] = create_listenly_show(info)
    podcast = {"slug": slug, "podcast_name": info["title"], "language": "fr"}

    path = f"{MOMENTS_DIR}/{slug}.json"
    idx = load_json(path, {"entries": {}})
    entries = idx.get("entries", {})
    nouveaux, erreurs = [], []
    for ep in todo:
        log(f"### {ep['title'][:100]}")
        try:
            items = extract_episode(m, podcast, ep)
        except Exception as ex:
            erreurs.append(f"{ep['title'][:60]} : {type(ex).__name__} {str(ex)[:100]}")
            log(f"ERREUR sur cet episode : {ex}")
            continue
        rec["episodes_done"].append(ep["guid"])
        for e in items:
            mid = moment_id(slug, e["q"])
            if mid in entries and entries[mid].get("f") and not e.get("f"):
                continue
            entries[mid] = e
            nouveaux.append(mid)

    save_json(path, {"podcast": info["title"], "slug": slug, "hub": f"/podcast-btb/fr/{slug}.html",
                     "show": rec.get("listenly_url", ""), "cover": info["cover"], "entries": entries}, compact=True)
    save_json(PODCASTS_FILE, podcasts)
    build_hub(rec, entries)
    n_sitemap = build_sitemap()

    liens = []
    for mid in dict.fromkeys(nouveaux):
        e = entries[mid]
        liens.append({"question": e["q"], "titre_google": e.get("ts", ""), "url": f"{SITE}/m/{slug}/{mid}",
                      "indexable": gate(entries, mid), "episode": e.get("e", "")})
    res = {"date": TODAY, "heure": datetime.datetime.utcnow().strftime("%H:%M UTC"), "podcast": info["title"], "slug": slug,
           "hub": f"{SITE}/{slug}.html", "fiche_listenly": rec.get("listenly_url", ""), "episodes_traites": len(todo),
           "moments": liens, "erreurs": erreurs, "sitemap": f"{SITE}/sitemap-fr.xml"}
    save_json(f"{DATA}/derniere_generation.json", res)
    hist = load_json(f"{DATA}/historique.json", [])
    hist.append({k: res[k] for k in ("date", "heure", "podcast", "slug", "hub")} | {"moments": len(liens)})
    save_json(f"{DATA}/historique.json", hist[-200:])

    log(f"TERMINE : {len(liens)} fiche(s) moment, {sum(1 for l in liens if l['indexable'])} indexable(s), sitemap : {n_sitemap} page(s).")
    lines = [f"## {info['title']} — {len(liens)} fiche(s) moment", "", f"Hub : {res['hub']} (noindex tant que HUB_INDEX n'est pas actif)", ""]
    lines += [f"- {l['url']} — {l['question']}" + ("" if l["indexable"] else "  _(noindex : réponse trop courte)_") for l in liens]
    lines += [""] + [f"⚠️ {x}" for x in erreurs]
    for l in lines[3:]:
        print(l, flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    if not liens:
        sys.exit(2)


if __name__ == "__main__":
    main()

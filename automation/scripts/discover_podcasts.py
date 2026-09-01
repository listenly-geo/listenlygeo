#!/usr/bin/env python3
"""
Decouverte automatique de podcasts candidats pour le Moteur BTB.

Principe : interroge l'API publique iTunes Search (gratuite, sans cle) avec une
liste de mots-cles sectoriels B2B, deduplique et filtre grossierement les
resultats, puis fait passer chaque candidat restant dans le meme filtre de
pre-qualification GEO que l'onboarding manuel (check_podcast_qualification.py)
— mass-media/celebrite rejete, sujet deja tres couvert rejete.

Ne fait JAMAIS d'onboarding automatique : produit uniquement une liste de
candidats ONBOARD, avec leur flux RSS, pour validation manuelle avant de
lancer le workflow "Fiche Podcast-BTB" (Moteur N1).

Variables d'environnement :
  ANTHROPIC_API_KEY     — obligatoire (qualification GEO)
  DISCOVERY_COUNTRIES   — codes pays iTunes separes par virgule (defaut: pays anglophones)
  DISCOVERY_MAX_QUALIFY — nombre max de candidats a qualifier par run (defaut: 15,
                          controle le cout des appels Claude+recherche web)
  DISCOVERY_KEYWORDS_FILE — chemin du fichier JSON de mots-cles (defaut ci-dessous)

Sortie :
  - pages/podcast-btb/data/discovery_candidates.json (historique cumulatif des
    candidats deja vus, pour ne jamais re-proposer un candidat deja traite)
  - Resume lisible sur stdout et dans $GITHUB_STEP_SUMMARY si present
"""

import os, sys, json, re, time
import urllib.request, urllib.error, urllib.parse

API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-haiku-4-5-20251001"
COUNTRIES = [c.strip() for c in os.environ.get("DISCOVERY_COUNTRIES", "us,gb,au,ca,ie,nz,sg,za").split(",") if c.strip()]  # pays anglophones elargis (30/08/2026)
MAX_QUALIFY = int(os.environ.get("DISCOVERY_MAX_QUALIFY", "15"))
KEYWORDS_FILE = os.environ.get(
    "DISCOVERY_KEYWORDS_FILE", "automation/data/discovery_keywords.json"
)
PODCASTS_FILE = "pages/podcast-btb/data/podcasts.json"
PAUSED_FILE = "pages/podcast-btb/data/paused_podcasts.json"
CANDIDATES_FILE = "pages/podcast-btb/data/discovery_candidates.json"


def log(msg):
    print(f"[discover] {msg}", flush=True)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def normalize_name(name):
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def itunes_search(term, country, limit=25):
    url = (
        "https://itunes.apple.com/search?"
        + urllib.parse.urlencode({"term": term, "media": "podcast", "limit": limit, "country": country})
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        return data.get("results", [])
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        log(f"  ERREUR recherche '{term}' ({country}) : {e}")
        return []


QUALIFICATION_PROMPT = """Tu es un analyste GEO (Generative Engine Optimization) charge de decider si un
podcast merite d'etre onboarde sur un moteur de fiches B2B, sur la base de donnees reelles observees :

DONNEES DE REFERENCE (Search Console, 3 derniers mois, 30/08/2026) :
- Podcasts mass-media / celebrite grand public : CTR moyen 1.19%, position moyenne 19.3 — grosse
  concurrence documentaire deja existante, quasi impossible a battre malgre un volume de recherche eleve.
- Podcasts niche B2B a expertise pointue (peu connus du grand public, invites qui donnent des chiffres/
  methodes precis) : CTR moyen 3.76%, position moyenne 14.0 — peu ou pas de concurrence documentaire,
  la fiche devient LA source citee par les moteurs IA.

TA MISSION : a partir des metadonnees iTunes ci-dessous, et en utilisant la recherche web pour verifier
le niveau de couverture documentaire existante, determine si ce podcast est un bon candidat.

METADONNEES ITUNES :
- Nom du podcast : {name}
- Editeur/hote (artistName iTunes) : {artist}
- Genre : {genre}
- Description : {description}
- Nombre d'episodes : {track_count}

Determine aussi la langue principale de ce podcast (a partir du nom, de l'editeur et de la description) —
UNIQUEMENT "fr" (francais), "en" (anglais), ou "other" (toute autre langue, y compris si incertain).

Reponds STRICTEMENT avec un objet JSON valide, rien d'autre :
{{
  "mass_media_or_celebrity": true/false,
  "existing_coverage_level": "faible/moyen/eleve",
  "detected_language": "fr" ou "en" ou "other",
  "verdict": "ONBOARD" ou "REJECT",
  "reason": "1-2 phrases en francais expliquant le verdict"
}}"""


def call_claude_with_search(prompt):
    payload = {
        "model": MODEL,
        "max_tokens": 1200,
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        "messages": [{"role": "user", "content": prompt}],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=data,
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read())
    parts = [b.get("text", "") for b in result.get("content", []) if b.get("type") == "text"]
    return "".join(parts).strip()


def extract_json(text):
    text = re.sub(r"^```json\s*", "", text.strip())
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("Aucun JSON trouve : " + text[:300])
    return json.loads(m.group(0))


def write_summary(md):
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        with open(gh_summary, "a", encoding="utf-8") as f:
            f.write(md + "\n")


def main():
    keywords = load_json(KEYWORDS_FILE, [])
    if not keywords:
        log(f"ERREUR : aucun mot-cle charge depuis {KEYWORDS_FILE}")
        sys.exit(1)
    log(f"{len(keywords)} mots-cles charges, {len(COUNTRIES)} pays cibles.")

    existing_podcasts = load_json(PODCASTS_FILE, [])
    existing_names = {normalize_name(p.get("podcast_name", "")) for p in existing_podcasts}

    paused = load_json(PAUSED_FILE, {})
    paused_names = {normalize_name(slug.replace("-", " ")) for slug in paused.keys()}

    seen_candidates = load_json(CANDIDATES_FILE, {})  # feedUrl -> record deja traite

    # --- 1) Collecte brute via iTunes Search -- on garde le mot-cle qui a trouve chaque
    # resultat, pour pouvoir diversifier la selection ensuite (voir etape 3).
    raw_results = {}  # feed_url -> (record, keyword)
    for kw in keywords:
        for country in COUNTRIES:
            for r in itunes_search(kw, country):
                feed_url = r.get("feedUrl")
                if not feed_url:
                    continue
                if feed_url not in raw_results:
                    raw_results[feed_url] = (r, kw)
            time.sleep(0.2)  # courtoisie API

    log(f"{len(raw_results)} podcasts uniques trouves (avant filtrage).")

    # --- 2) Filtrage grossier : deja onboarde, deja pausé, deja traite, heuristiques ---
    # Regroupe par mot-cle d'origine (proxy de secteur/categorie) plutot qu'en liste plate.
    by_keyword = {}
    total_new = 0
    for feed_url, (r, kw) in raw_results.items():
        name = r.get("collectionName", "")
        norm = normalize_name(name)
        if norm in existing_names:
            continue
        if norm in paused_names:
            continue
        if feed_url in seen_candidates:
            continue
        track_count = r.get("trackCount", 0)
        if track_count < 3:
            continue  # trop peu d'episodes, probablement inactif/test
        by_keyword.setdefault(kw, []).append(r)
        total_new += 1

    log(f"{total_new} candidats nouveaux (non deja onboardes/pausés/traites), repartis sur {len(by_keyword)} mot(s)-cle(s).")

    # --- 3) Qualification GEO (plafonnee pour controler le cout) -- selection en
    # round-robin entre mots-cles/secteurs plutot qu'en ordre brut : evite qu'un seul
    # secteur riche en resultats (ex: commercial real estate, tres dense aux US) ne
    # monopolise tout le budget de qualification au detriment de la diversite sectorielle
    # visee par la strategie GEO (30/08/2026 : cibler large tant que ca reste B2B/dirigeants).
    to_qualify = []
    keyword_pools = list(by_keyword.values())
    while len(to_qualify) < MAX_QUALIFY and any(keyword_pools):
        for pool in keyword_pools:
            if not pool:
                continue
            to_qualify.append(pool.pop(0))
            if len(to_qualify) >= MAX_QUALIFY:
                break

    new_candidates = to_qualify  # conserve pour compatibilite avec le resume plus bas
    if total_new > MAX_QUALIFY:
        log(f"Plafonne a {MAX_QUALIFY} candidats sur ce run, repartis entre secteurs (les autres seront vus au prochain passage).")

    onboard_list = []
    reject_list = []
    for r in to_qualify:
        name = r.get("collectionName", "?")
        prompt = QUALIFICATION_PROMPT.format(
            name=name,
            artist=r.get("artistName", "?"),
            genre=r.get("primaryGenreName", "?"),
            description=(r.get("description") or r.get("collectionCensoredName") or "")[:800],
            track_count=r.get("trackCount", "?"),
        )
        log(f"Qualification : {name}...")
        try:
            raw = call_claude_with_search(prompt)
            result = extract_json(raw)
        except Exception as e:
            log(f"  ERREUR qualification ({e}) — ignore ce candidat par prudence.")
            continue

        detected_language = result.get("detected_language", "other")
        verdict = result.get("verdict", "REJECT")
        reason = result.get("reason", "")
        # Politique produit (30/08/2026) : uniquement des podcasts anglophones, pour un impact GEO
        # maximal (audience/volume de requetes bien plus large qu'en francais). Ecrase le verdict
        # de Claude si la langue detectee n'est pas l'anglais, quel que soit le fond du jugement --
        # jamais d'ambiguite dans le fichier de sortie consomme tel quel par le generateur.
        if detected_language != "en" and verdict == "ONBOARD":
            verdict = "REJECT"
            reason = f"Langue detectee : {detected_language} (hors perimetre, anglais uniquement). " + reason

        record = {
            "podcast_name": name,
            "artist_name": r.get("artistName", ""),
            "feed_url": r.get("feedUrl", ""),
            "genre": r.get("primaryGenreName", ""),
            "track_count": r.get("trackCount", 0),
            "collection_view_url": r.get("collectionViewUrl", ""),
            "cover_image": r.get("artworkUrl600") or r.get("artworkUrl100") or r.get("artworkUrl60") or "",
            "detected_language": detected_language,
            "verdict": verdict,
            "reason": reason,
            "checked_date": __import__("datetime").date.today().isoformat(),
        }
        seen_candidates[r.get("feedUrl", "")] = record
        if record["verdict"] == "ONBOARD":
            onboard_list.append(record)
        else:
            reject_list.append(record)
        time.sleep(0.3)

    with open(CANDIDATES_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_candidates, f, ensure_ascii=False, indent=2)

    log(f"Termine : {len(onboard_list)} candidats ONBOARD, {len(reject_list)} REJECT.")

    summary_lines = [
        "## Decouverte automatique de podcasts — resultats",
        "",
        f"{len(raw_results)} podcasts trouves via iTunes Search, {total_new} nouveaux "
        f"(sur {len(by_keyword)} secteur(s)/mot(s)-cle(s) distinct(s)), "
        f"{len(to_qualify)} qualifies sur ce run (repartis entre secteurs).",
        "",
        f"### Candidats ONBOARD ({len(onboard_list)})",
        "",
        "| Podcast | Editeur | Episodes | Flux RSS | Raison |",
        "|---|---|---|---|---|",
    ]
    for c in onboard_list:
        summary_lines.append(
            f"| {c['podcast_name']} | {c['artist_name']} | {c['track_count']} | `{c['feed_url']}` | {c['reason']} |"
        )
    summary_lines.append("")
    summary_lines.append(f"### Candidats REJECT ({len(reject_list)})")
    summary_lines.append("")
    for c in reject_list:
        summary_lines.append(f"- **{c['podcast_name']}** — {c['reason']}")

    write_summary("\n".join(summary_lines))
    for line in summary_lines:
        print(line)


if __name__ == "__main__":
    main()

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

# GitHub Issues comme file d'attente des candidats (01/09/2026) -- remplace l'ecriture directe
# dans discovery_candidates.json. Raison : le fichier JSON s'accumulait indefiniment (jamais
# purge), et un fichier HTML statique local ne peut jamais supprimer/fermer une entree en un
# clic sans exposer une cle d'ecriture (le repo est PUBLIC). Les issues GitHub offrent
# nativement : pagination, recherche, fermeture en un clic (Etienne est deja connecte a
# GitHub avec ses propres droits, aucune cle necessaire cote generateur pour la lecture --
# repo public).
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "listenly-geo/listenlygeo").strip()
CANDIDATE_LABEL = "candidate"
COUNTRIES = [c.strip() for c in os.environ.get("DISCOVERY_COUNTRIES", "us").split(",") if c.strip()]  # US uniquement par defaut (01/09/2026) -- 8 pays generaient trop de requetes (429 Too Many Requests) et diluaient le budget de qualification sans reel gain de diversite
MAX_QUALIFY = int(os.environ.get("DISCOVERY_MAX_QUALIFY", "15"))
KEYWORDS_FILE = os.environ.get(
    "DISCOVERY_KEYWORDS_FILE", "automation/data/discovery_keywords.json"
)
PODCASTS_FILE = "pages/podcast-btb/data/podcasts.json"
PAUSED_FILE = "pages/podcast-btb/data/paused_podcasts.json"
# Historique permanent (01/09/2026) : seul fichier qui accumule pour toujours, utilise
# uniquement pour la deduplication interne ("deja qualifie, ne pas re-payer un appel Claude").
# Jamais lu par le generateur -- les candidats visibles/actionnables sont desormais des
# issues GitHub (voir GITHUB_TOKEN plus bas), qui remplacent l'ancien discovery_candidates.json
# : celui-ci s'accumulait indefiniment sans jamais etre purge, et un fichier HTML statique ne
# peut pas fermer/supprimer une entree en un clic sans exposer une cle d'ecriture (repo public).
SEEN_HISTORY_FILE = "automation/data/discovery_seen_history.json"


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


def itunes_search(term, country, limit=25, max_retries=3):
    url = (
        "https://itunes.apple.com/search?"
        + urllib.parse.urlencode({"term": term, "media": "podcast", "limit": limit, "country": country})
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read())
            return data.get("results", [])
        except urllib.error.HTTPError as e:
            # Fix du 02/09/2026 : le 403 s'est avere aussi frequent que le 429 en pratique --
            # les runners GitHub Actions partagent des plages d'IP avec d'autres utilisateurs,
            # et iTunes semble parfois renvoyer 403 plutot que 429 sous charge/reputation d'IP
            # partagee. Meme logique de retry pour les deux codes.
            if e.code in (429, 403) and attempt < max_retries - 1:
                wait = 6 * (2 ** attempt)  # 6s, 12s, 24s
                log(f"  {e.code} sur '{term}' ({country}) -- pause {wait}s puis nouvelle tentative ({attempt+1}/{max_retries})")
                time.sleep(wait)
                continue
            log(f"  ERREUR recherche '{term}' ({country}) : {e}")
            return []
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            log(f"  ERREUR recherche '{term}' ({country}) : {e}")
            return []
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


def github_api_request(method, path, payload=None):
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "listenly-discovery-bot",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def list_existing_candidate_feed_urls():
    """Recupere le feed_url de TOUTES les issues candidates existantes (ouvertes ET fermees)
    -- sert de deduplication permanente : un podcast deja propose une fois (accepte ou rejete
    par Etienne en fermant l'issue) ne doit jamais generer une nouvelle issue en double."""
    seen = set()
    page = 1
    while True:
        try:
            issues = github_api_request(
                "GET",
                f"/issues?labels={CANDIDATE_LABEL}&state=all&per_page=100&page={page}",
            )
        except Exception as e:
            log(f"AVERTISSEMENT : lecture des issues existantes echouee ({e}) -- deduplication partielle possible.")
            break
        if not issues:
            break
        for issue in issues:
            m = re.search(r"<!-- feed_url: (.*?) -->", issue.get("body", "") or "")
            if m:
                seen.add(m.group(1).strip())
        if len(issues) < 100:
            break
        page += 1
    return seen


def create_candidate_issue(record):
    """Cree une issue GitHub pour un candidat ONBOARD. Le feed_url est encode dans un
    commentaire HTML cache dans le corps, pour un matching fiable independant du formatage
    visible (voir list_existing_candidate_feed_urls)."""
    title = f"🎙️ {record['podcast_name']}"
    body = (
        f"<!-- feed_url: {record['feed_url']} -->\n\n"
        f"**Éditeur/hôte :** {record['artist_name']}\n"
        f"**Genre :** {record['genre']}\n"
        f"**Épisodes :** {record['track_count']}\n"
        f"**Langue détectée :** {record['detected_language']}\n"
        f"**Flux RSS :** `{record['feed_url']}`\n"
        f"**Fiche iTunes :** {record['collection_view_url']}\n"
        f"**Image de couverture :** {record['cover_image']}\n\n"
        f"**Raison de qualification :**\n{record['reason']}\n\n"
        f"---\n_Détecté automatiquement le {record['checked_date']}. Ferme cette issue une fois "
        f"le podcast traité (onboardé ou écarté) pour qu'elle disparaisse définitivement du générateur._"
    )
    try:
        github_api_request("POST", "/issues", {"title": title, "body": body, "labels": [CANDIDATE_LABEL]})
        return True
    except Exception as e:
        log(f"  ERREUR creation issue pour '{record['podcast_name']}' : {e}")
        return False


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

    seen_candidates = load_json(SEEN_HISTORY_FILE, {})  # feedUrl -> record deja traite (historique permanent)

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
    #
    # Fix du 01/09/2026 : le round-robin seul ne suffisait pas -- des que la plupart des
    # mots-cles niche (peu de resultats iTunes) etaient epuises, les rounds suivants ne
    # tiraient plus QUE des mots-cles riches (real estate...), qui finissaient par
    # monopoliser le budget malgre le round-robin. Ajout d'un plafond dur par mot-cle : un
    # seul mot-cle ne peut jamais fournir plus de MAX_PER_KEYWORD candidats sur un run,
    # quel que soit le nombre de rounds restants.
    MAX_PER_KEYWORD = 2
    to_qualify = []
    taken_per_keyword = {}
    keyword_pools = list(by_keyword.items())
    progress = True
    while len(to_qualify) < MAX_QUALIFY and progress:
        progress = False
        for kw, pool in keyword_pools:
            if not pool:
                continue
            if taken_per_keyword.get(kw, 0) >= MAX_PER_KEYWORD:
                continue
            to_qualify.append(pool.pop(0))
            taken_per_keyword[kw] = taken_per_keyword.get(kw, 0) + 1
            progress = True
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

    os.makedirs(os.path.dirname(SEEN_HISTORY_FILE), exist_ok=True)
    with open(SEEN_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_candidates, f, ensure_ascii=False, indent=2)

    # Creation d'une issue GitHub par candidat ONBOARD (remplace l'ecriture dans
    # discovery_candidates.json, voir commentaire sur GITHUB_TOKEN plus haut). Verification
    # anti-doublon supplementaire ici (au-dela du filtre seen_candidates) : filet de securite
    # si l'historique JSON venait a etre perdu/reinitialise alors que des issues existent deja.
    created_count = 0
    if onboard_list:
        if not GITHUB_TOKEN:
            log("AVERTISSEMENT : GITHUB_TOKEN absent -- aucune issue creee pour les candidats ONBOARD.")
        else:
            existing_issue_feed_urls = list_existing_candidate_feed_urls()
            for record in onboard_list:
                if record["feed_url"] in existing_issue_feed_urls:
                    log(f"  Issue deja existante pour '{record['podcast_name']}' -- ignore.")
                    continue
                if create_candidate_issue(record):
                    created_count += 1
                time.sleep(0.5)

    log(f"Termine : {len(onboard_list)} candidats ONBOARD ({created_count} nouvelle(s) issue(s) creee(s)), {len(reject_list)} REJECT.")

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

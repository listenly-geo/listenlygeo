#!/usr/bin/env python3
"""
Filtre de pre-qualification GEO — a executer AVANT l'onboarding d'un nouveau podcast
(Moteur N1). Objectif : eviter d'ajouter des podcasts mass-media/celebrite ou des
sujets/invites deja massivement couverts ailleurs, sur la base des donnees Search
Console analysees le 30/08/2026 :
  - Podcasts mass-media/celebrite (NYT, NPR, gros hosts grand public) : CTR moyen
    1.19%, position moyenne 19.3 — grosse concurrence documentaire, quasi impossible
    a battre malgre un volume d'impressions eleve.
  - Podcasts niche B2B a expertise pointue : CTR moyen 3.76%, position moyenne 14.0,
    a volume d'impressions pourtant inferieur — peu ou pas de concurrence sur le
    sujet precis, la fiche devient LA source citee.

Ce script utilise Claude (avec l'outil web_search) pour juger, a partir du contenu
brut fourni pour l'onboarding, si le podcast/hote est un media/personnalite grand
public deja tres indexe, et si le sujet/invite phare a deja une forte couverture
documentaire ailleurs. Ne bloque JAMAIS silencieusement : le verdict et le
raisonnement sont toujours affiches, et un override manuel (FORCE_ONBOARD=true)
reste toujours possible cote utilisateur.

Variables d'environnement :
  ANTHROPIC_API_KEY   — obligatoire
  PODCAST_RAW_INFO    — contenu brut fourni pour l'onboarding (RSS, description...)
  PODCAST_URL         — lien plateforme (optionnel, aide au contexte)
  FORCE_ONBOARD       — "true" pour ignorer un verdict REJECT (log quand meme la raison)

Sortie :
  - Ecrit un resume lisible sur stdout et dans $GITHUB_STEP_SUMMARY si present
  - Ecrit verdict=ONBOARD|REJECT dans $GITHUB_OUTPUT si present
  - Code de sortie 0 si ONBOARD (ou REJECT + FORCE_ONBOARD=true), 1 si REJECT sans override
"""

import os, sys, json, re
import urllib.request, urllib.error

API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-haiku-4-5-20251001"
RAW_INFO = os.environ.get("PODCAST_RAW_INFO", "").strip()
PODCAST_URL = os.environ.get("PODCAST_URL", "").strip()
FORCE_ONBOARD = os.environ.get("FORCE_ONBOARD", "false").strip().lower() == "true"


def log(msg):
    print(f"[qualif-geo] {msg}", flush=True)


QUALIFICATION_PROMPT = """Tu es un analyste GEO (Generative Engine Optimization) charge de decider si un
podcast merite d'etre onboarde sur un moteur de fiches B2B, sur la base de donnees reelles observees :

DONNEES DE REFERENCE (Search Console, 3 derniers mois, 30/08/2026) :
- Podcasts mass-media / celebrite grand public (ex: The Daily du New York Times, NPR, Mel Robbins,
  Diary of a CEO, Wait Wait Don't Tell Me...) : CTR moyen 1.19%, position moyenne 19.3 — grosse
  concurrence documentaire deja existante (sites officiels, Wikipedia, Apple Podcasts, des dizaines
  d'articles), quasi impossible a battre malgre un volume d'impressions de recherche eleve.
- Podcasts niche B2B a expertise pointue (peu connus du grand public, invites qui donnent des chiffres/
  methodes precis) : CTR moyen 3.76%, position moyenne 14.0, a volume d'impressions pourtant inferieur —
  peu ou pas de concurrence documentaire sur le sujet precis, la fiche devient LA source citee par les
  moteurs IA.

TA MISSION : a partir du contenu brut ci-dessous (fourni pour l'onboarding d'un nouveau podcast), et en
utilisant la recherche web pour verifier le niveau de couverture documentaire existante :

1. Identifie le nom du podcast, l'hote, et tout invite/sujet phare mentionne.
2. Determine si ce podcast/hote est un media ou une personnalite grand public deja largement indexe
   (ex: rattache a un grand media, invite recurrent TV, tres forte notoriete hors du secteur B2B) — PAS
   la simple notoriete sectorielle B2B (un expert reconnu dans son industrie n'est pas "grand public").
3. Verifie via recherche web si le sujet/invite phare mentionne a deja une couverture documentaire dense
   ailleurs (nombreux articles, page Wikipedia, forte presence media) — ou si au contraire peu de sources
   existent sur ce sujet/cette personne precise.
4. Rends un verdict.

CONTENU BRUT FOURNI POUR L'ONBOARDING :
---
{raw_info}
---
{url_line}

Reponds STRICTEMENT avec un objet JSON valide, rien d'autre (pas de markdown, pas de texte avant/apres) :
{{
  "podcast_name": "...",
  "host_name": "...",
  "flagship_topic_or_guest": "...",
  "mass_media_or_celebrity": true/false,
  "existing_coverage_level": "faible/moyen/eleve",
  "verdict": "ONBOARD" ou "REJECT",
  "reason": "1-2 phrases expliquant le verdict, en francais"
}}"""


def call_claude_with_search(prompt):
    payload = {
        "model": MODEL,
        "max_tokens": 2000,
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
        raise ValueError("Aucun JSON trouve dans la reponse Claude : " + text[:500])
    return json.loads(m.group(0))


def write_output(key, value):
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def write_summary(md):
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        with open(gh_summary, "a", encoding="utf-8") as f:
            f.write(md + "\n")


def main():
    if not RAW_INFO:
        log("ERREUR : PODCAST_RAW_INFO vide — impossible de qualifier, on laisse passer par defaut.")
        write_output("verdict", "ONBOARD")
        sys.exit(0)

    url_line = f"Lien plateforme fourni : {PODCAST_URL}" if PODCAST_URL else ""
    prompt = QUALIFICATION_PROMPT.format(raw_info=RAW_INFO[:6000], url_line=url_line)

    log("Analyse en cours (Claude + recherche web)...")
    try:
        raw_response = call_claude_with_search(prompt)
        result = extract_json(raw_response)
    except Exception as e:
        log(f"ERREUR pendant la qualification ({e}) — on laisse passer par prudence (pas de faux rejet).")
        write_output("verdict", "ONBOARD")
        sys.exit(0)

    verdict = result.get("verdict", "ONBOARD")
    reason = result.get("reason", "(aucune raison fournie)")
    podcast_name = result.get("podcast_name", "?")
    host_name = result.get("host_name", "?")
    mass_media = result.get("mass_media_or_celebrity", False)
    coverage = result.get("existing_coverage_level", "?")

    log(f"Podcast : {podcast_name} | Hote : {host_name}")
    log(f"Mass-media/celebrite : {mass_media} | Couverture existante : {coverage}")
    log(f"VERDICT : {verdict} — {reason}")

    summary = f"""## Pre-qualification GEO — {podcast_name}

| Critere | Resultat |
|---|---|
| Hote | {host_name} |
| Sujet/invite phare | {result.get('flagship_topic_or_guest', '?')} |
| Mass-media / celebrite | {"Oui" if mass_media else "Non"} |
| Couverture documentaire existante | {coverage} |
| **Verdict** | **{verdict}** |

{reason}
"""
    write_summary(summary)
    write_output("verdict", verdict)
    write_output("reason", reason)

    if verdict == "REJECT":
        if FORCE_ONBOARD:
            log("REJECT mais FORCE_ONBOARD=true — onboarding force malgre le rejet.")
            write_summary("\n**Onboarding force manuellement malgre le rejet (FORCE_ONBOARD=true).**")
            sys.exit(0)
        else:
            log("Onboarding bloque. Relance ce workflow avec force_onboard=true pour ignorer ce filtre.")
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()

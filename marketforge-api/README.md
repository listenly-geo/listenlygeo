# Marketforge AI Visibility Hub — API (MVP)

L'API ne génère rien elle-même. Elle **déclenche le moteur trafic existant** de ce dépôt
(`.github/workflows/marketforge-hub.yml` → `generate_podcast_btb.py` puis
`generate_qa_fiches_btb.py`) et **lit ce qu'il a produit** (`pages/podcast-btb/questions/<slug>/_qa_registry.json`)
pour alimenter le dashboard. Les fiches sont publiées sur `https://listenly.fr/podcast-btb/`.

Sources traitées : podcast (RSS), vidéo et webinar (YouTube, Vimeo, .mp4 — yt-dlp + transcription du moteur),
article et site web (texte de la page, rendu JavaScript si besoin), document (PDF). Les sources non-podcast passent
par `automation/scripts/marketforge_run.py`, qui réutilise le moteur sans le modifier. Un client sans podcast obtient
un hub entreprise (`<slug>-podcast.html`, décrit comme entreprise, JSON-LD Organization).

Prompts Bolt à coller dans l'ordre : `BOLT.md` (branchement), `BOLT-2.md` (abonnement, factures, visibilité),
`BOLT-3.md` (toutes les sources), `BOLT-4.md` (suivi data), `BOLT-5.md` (pause client et pause générale).

| Route | Rôle |
|---|---|
| `GET /health` | Vérification (`engine_configured` = token GitHub présent) |
| `POST /api/onboarding/sources` `{client_id, type, value}` | `type` ∈ website, podcast, video, document, webinar, article. Podcast : `value` = URL RSS (vérifiée). Website : `value` = URL du site (sert de CTA des fiches) |
| `POST /api/onboarding/strategy` `{client_id, strategy}` | `strategy` ∈ hub, site, both |
| `POST /api/run/{client_id}` | Déclenche le moteur (1 run / 12 h / client, 10 runs / jour max) |
| `GET /api/dashboard/{client_id}` | Compteurs réels + `status` (idle/running/done/error) + `sources` + `hub_urls` |
| `GET /api/opportunities/{client_id}` | Questions extraites (publiées ou en file d'attente) |
| `POST /api/pause/{client_id}` `{paused}` | Pause/reprise des analyses d'un client (annule l'analyse en cours) |
| `GET/POST /api/admin/pause` `{paused}` | Pause générale (en-tête `X-Admin-Key` = `ADMIN_KEY`) : bloque tout et annule les runs en cours |

`client_id` = email de connexion de l'utilisateur (normalisé en minuscules).

## Local
```
pip install -r requirements.txt pytest
GITHUB_TOKEN=... uvicorn main:app --reload
pytest -q
```

## Railway
New Project → Deploy from GitHub repo `listenly-geo/listenlygeo` → Settings : Root Directory `marketforge-api`
→ Variables : `GITHUB_TOKEN` → Volume monté sur `/app/data` → Networking → Generate Domain.

Le token GitHub (fine-grained) : dépôt `listenly-geo/listenlygeo` uniquement, permissions **Actions : Read and write**
et **Contents : Read-only**. Les clés Anthropic / OpenAI / FTP restent dans les secrets GitHub, pas sur Railway.

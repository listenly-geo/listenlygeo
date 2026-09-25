# Marketforge AI Visibility Hub — API (MVP)

FastAPI + un fichier JSON par client. Seul le type `podcast` est traité (RSS → 3 derniers épisodes → Claude → 2-4 Q/R par épisode, tirées uniquement du titre + description).

| Route | Rôle |
|---|---|
| `GET /health` | Vérification |
| `POST /api/onboarding/sources` `{client_id, type, value}` | `type` ∈ website, podcast, video, document, webinar, article. Pour `podcast`, `value` = URL du flux RSS |
| `POST /api/onboarding/strategy` `{client_id, strategy}` | `strategy` ∈ hub, site, both |
| `POST /api/run/{client_id}` | Lance le traitement en tâche de fond |
| `GET /api/dashboard/{client_id}` | Compteurs + `status` (idle/running/done/error) + `sources` (avec `supported` et `status`) |
| `GET /api/opportunities/{client_id}` | Liste des questions/réponses extraites |

`client_id` = email de connexion de l'utilisateur (normalisé en minuscules).

## Local
```
pip install -r requirements.txt
ANTHROPIC_API_KEY=... uvicorn main:app --reload
pytest -q
```

## Railway
New Project → Deploy from GitHub repo → Root Directory `marketforge-api` → Variables `ANTHROPIC_API_KEY` → Volume monté sur `/app/data` → Networking → Generate Domain.

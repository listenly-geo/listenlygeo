# MarketForge Engine

**Run complet automatique** : `marketforge-engine-run.yml` (tous les jours ~7h17, ou bouton Run workflow)
= découverte → onboarding auto (fiche Listenly SQL + N1) → extraction → commit → FTP.
`onboarding_auto: false` pour repasser en validation manuelle (label `approved`).

# Détail : extraction

Chaîne : découverte (`discover-podcasts.yml`) → fiche N1 (générateur) → **extraction ici** → hub knowledge → mail (Apps Script).

## Robinet : `config.json`
| Clé | Rôle |
|---|---|
| `pause` | `true` = tout s'arrête |
| `decouverte_max_par_jour` | candidats qualifiés par run (coût Claude) |
| `onboarding_auto` / `onboarding_max_par_jour` | fiches Listenly + N1 créées automatiquement par run |
| `episodes_par_jour` | débit quotidien (épisodes transcrits/jour, tous podcasts confondus) |
| `episodes_par_podcast` | profondeur par prospect |
| `minutes_audio_max_jour` | garde-fou coût Whisper |
| `questions_max_par_episode` | plafond Q/R extraites par épisode (6 par défaut, identique au moteur trafic) |
| `entree_auto_depuis_date` | tout podcast de `podcasts.json` créé depuis cette date entre dans la file |
| `ajouter_manuellement` / `exclure` | forcer / bannir des slugs |
| `proof_url_template` | lien preuve envoyé dans le mail (`{fiche_url}` = fiche N1 du podcast, par défaut ; aussi `{slug}`, `{podcast_name}`, `{podcast_name_url}`) |

## État : `queue.json`
Par podcast : `status` (`en_attente` → `en_cours` → `extrait`), `podcast_name`, `email` (lu dans le RSS ; `status_email: sans_email` si absent), `episodes_done`, `moments_count`, `proof_url`.
`journal` = consommation par jour (le budget est respecté même avec plusieurs runs/jour).

## Pour le mail (Apps Script)
Lire `https://raw.githubusercontent.com/listenly-geo/listenlygeo/main/automation/marketforge_engine/queue.json`,
et n'envoyer que si `podcasts[slug].proof_url` est rempli.

## Ce que produit chaque épisode extrait (1 seul passage Whisper)
1. **Knowledge moments** (`pages/podcast-btb/data/knowledge_moments/`) + import en base (Knowledge Search).
2. **Hub de la fiche N1** : le bloc « Les réponses de ce podcast » affiche les Q/R extraites (timestamp + « Écouter ce moment »), déployé en FTP. C'est la preuve du mail. Limité aux podcasts de la file (`hub_index.merge_extracted`).
3. **Stock pour la future machine à fiches** : `automation/inbox/moteur-trafic-transcripts/<slug>/mfe-*.json`, format déjà lu par `generate_qa_fiches_btb.py`. Activer le moteur trafic sur le podcast suffit : il génère les fiches sans re-transcrire, et le hub ajoute alors le lien « Réponse complète ».

Aucune fiche question HTML n'est générée ; l'extraction réutilise `generate_episode_fiches_btb.py`
(Whisper → `extract_real_qa` → `save_knowledge_moments` → import DB).

## Onboarding automatique (remplace lien Listenly admin + YAML + run)
1. Découverte → issue `candidate` (avec email).
2. Tu valides : bouton **✅ Valider** du générateur, ou label `approved` sur l'issue.
3. `marketforge-onboard.yml` : fiche Listenly créée en SQL (`server/api/podcast-show-import.php`, table `_c_p_shows`, sans doublon RSS/titre) → fiche N1 (`generate_podcast_btb.py`) → issue commentée + fermée.
4. La fiche N1 entre seule dans la file d'extraction.

Mise en service (une fois) : Actions → workflow → `deploy_api`, puis `describe` (vérifier le mapping des colonnes), puis `onboard` en `dry_run`.

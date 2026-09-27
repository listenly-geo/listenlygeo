# MarketForge Engine — extraction

Chaîne : découverte (`discover-podcasts.yml`) → fiche N1 (générateur) → **extraction ici** → hub knowledge → mail (Apps Script).

## Robinet : `config.json`
| Clé | Rôle |
|---|---|
| `pause` | `true` = tout s'arrête |
| `episodes_par_jour` | débit quotidien (épisodes transcrits/jour, tous podcasts confondus) |
| `episodes_par_podcast` | profondeur par prospect |
| `minutes_audio_max_jour` | garde-fou coût Whisper |
| `questions_max_par_episode` | plafond Q/R extraites par épisode (6 par défaut, identique au moteur trafic) |
| `entree_auto_depuis_date` | tout podcast de `podcasts.json` créé depuis cette date entre dans la file |
| `ajouter_manuellement` / `exclure` | forcer / bannir des slugs |
| `proof_url_template` | lien preuve envoyé dans le mail (`{slug}`, `{podcast_name}`, `{podcast_name_url}`) |

## État : `queue.json`
Par podcast : `status` (`en_attente` → `en_cours` → `extrait`), `episodes_done`, `moments_count`, `proof_url`.
`journal` = consommation par jour (le budget est respecté même avec plusieurs runs/jour).

## Pour le mail (Apps Script)
Lire `https://raw.githubusercontent.com/listenly-geo/listenlygeo/main/automation/marketforge_engine/queue.json`,
et n'envoyer que si `podcasts[slug].proof_url` est rempli.

Aucune fiche question HTML n'est générée ; l'extraction réutilise `generate_episode_fiches_btb.py`
(Whisper → `extract_real_qa` → `save_knowledge_moments` → import DB).

# Regles du depot

## MarketForge Engine : journal des optimisations (OBLIGATOIRE)
Toute optimisation du MarketForge Engine (ciblage, mots-cles, envoi, delivrabilite, mail, mesure, correction de bug)
doit etre ajoutee dans `automation/marketforge_engine/optimisations.json` dans le MEME commit :
- une ligne par optimisation : `section`, `version` (V1.0, V1.1… = lot de mise en ligne), `texte` (phrase claire, en francais, comprehensible sans contexte technique), `date` (JJ/MM/AAAA), `statut`
- statut : `en_cours` a la mise en ligne, `valide` quand Etienne l'a valide (contenu ou resultat), `a_faire` pour ce qui est decide mais pas commence
- ce fichier alimente automatiquement l'onglet "Optimisations" du Google Sheet (chaque run, via `sheet_bridge.py optimisations`)
Le proprietaire (Etienne) veut une clarte complete, chaque jour, sur ce qui a ete optimise et ou ca en est.

# Corentin Voice Engine — déploiement automatique

Ce dossier contient le code du script Apps Script "Corentin AI Voice"
(prospection SaaS), déployé automatiquement via GitHub Actions + clasp.

## Comment ça marche

- Le code vit dans `src/Code.gs`, modifiable ici comme n'importe quel fichier.
- `ACTION.txt` contient un seul mot : `dry`, `deploy` ou `publish`.
  - `dry` = ne touche à rien, affiche juste l'état actuel du script en ligne.
  - `deploy` = pousse le code + crée une nouvelle version Apps Script (le web app en ligne ne change pas encore).
  - `publish` = pousse le code + crée une version + branche le web app sur cette version (même URL, toujours).
- Changer `ACTION.txt` puis pousser sur GitHub déclenche automatiquement le workflow.
- Le résultat (lecture OK / version créée / erreur) est visible dans l'onglet "Actions" du dépôt GitHub.

## Mise en place, une seule fois

1. Sur ton PC, dans PowerShell :
   ```
   npx.cmd @google/clasp login
   ```
   Connecte-toi avec `partnership.voiceover@corentin-cugnet.fr`. Cela crée
   `C:\Users\<toi>\.clasprc.json`.

2. Ouvre ce fichier avec un éditeur de texte (Bloc-notes), copie tout son
   contenu.

3. Dans les paramètres du dépôt GitHub → Settings → Secrets and variables →
   Actions → "New repository secret" :
   - Nom : `CLASPRC_JSON`
   - Valeur : colle le contenu du fichier.

4. Donne l'ID du script (dans l'URL de l'éditeur Apps Script :
   `script.google.com/d/CET_ID/edit`) pour compléter `.clasp.json` ici.

5. Vérifie que l'API Apps Script est activée pour ce compte :
   https://script.google.com/home/usersettings (bascule sur ON).

Une fois ces 5 points faits, plus jamais besoin d'y retoucher : tout passe
par ce dossier + `ACTION.txt`.

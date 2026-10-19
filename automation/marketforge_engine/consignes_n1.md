# Consignes des fiches N1 (hubs podcast)

Décision du 19/10/2026 : les fiches N1 suivent deux modèles. Les anciennes ne sont pas touchées. Seules les nouvelles fiches suivent le modèle N1.2.

## N1.1 : ancien modèle (référence, ne plus produire)
- Description très longue, environ 1 000 mots, en paragraphes et sections explicatives.
- Questions-réponses sous forme de texte.
- Pas de barre de recherche, pas de lecteur audio intégré (seulement des liens vers les plateformes).
- Pas de liste d'épisodes détaillée.
- Exemple : https://listenly.org/podcast-btb/made-right-here-podcast.html
- Statut : conservé tel quel. Aucune migration ni suppression décidée.

## Interrupteur
- Fichier : `automation/marketforge_engine/modele_n1.json` (champ `modele_actif`).
- `N1.2` : les nouvelles fiches sont générées au modèle HUB.
- `N1.1` : retour à l'ancien modèle. Le générateur ne produit plus de N1.2 et renvoie vers la copie figée `pages/podcast-btb/n1-1-archive/`.
- L'ancien modèle n'est jamais supprimé. Les fiches N1.1 déjà en ligne ne sont jamais modifiées.

## N1.2 : nouveau modèle HUB (à appliquer aux prochaines fiches uniquement)
Objectif : une porte d'entrée claire et courte vers les pages de moment, qui sont les pages citées par Google et les IA.

Contenu, dans cet ordre :
1. **En-tête** : logo Listenly en haut à gauche, barre de recherche qui renvoie vers Listenly (« Explore more expert answers »).
2. **Bloc « À propos »** : pochette, nom du podcast, présentateur, puis un texte descriptif court de 80 à 120 mots. Il est composé uniquement à partir de données réelles du podcast (sujet, public, experts, nombre d'épisodes, période couverte). Pas de texte générique. À valider sur aperçu avant application au générateur.
   - **Thèmes couverts** : liste courte de sujets réellement traités, tirés des questions.
   - **Experts** : noms et rôles des invités, avec leur entreprise si connue.
   - **Faits datés** : nombre d'épisodes, période couverte, fréquence.
3. **Liste des questions** : chaque question réelle de l'épisode, avec son lien vers la page de moment (horodatage).
4. **Liste des épisodes** sources, si disponible.
5. **Pied de page** : mentions et lien vers Listenly.

Bouton « Listen to the podcast » (libellé en anglais) en tête de fiche, qui renvoie toujours vers la page du podcast sur Listenly (champ `listenly_url`), jamais vers Apple Podcasts. Pas de lecteur audio sur la fiche N1 : l'écoute se fait sur chaque page moment.

Style :
- Charte sombre Listenly : fond #000000, cartes #1C1C1E, texte #F5F5F7, accent #2997FF, police système.
- Pas de « Powered by » artificiel.
- Branding de l'entreprise (pochette, couleurs) non utilisé dans cette phase.

Règles :
- Pas de description longue : si le texte dépasse trois phrases, on le coupe.
- Une N1 par podcast. Elle est créée à la découverte, si le podcast apporte de nouvelles questions.
- Qualité minimale identique aux pages de moment (sinon noindex).

Statut : le bloc « À propos », les thèmes, les experts et les faits datés sont à valider sur l'aperçu avant d'être ajoutés au générateur.

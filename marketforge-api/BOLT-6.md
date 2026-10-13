# Prompt à coller dans Bolt.ai — Tableau de bord « Podcast Hub »

Colle tout le bloc ci-dessous dans le chat Bolt. Il remplace l'accueil (Overview) ; les autres pages ne changent pas pour l'instant.

---

Refonds la page Overview (`/app`) autour du concept Podcast Hub. Garde le design existant (couleurs, typographies, sidebar, cartes). Ne change que le contenu et la hiérarchie.

**Principe** : le client doit comprendre en 5 secondes (1) où en est son Hub, (2) ce que le Hub lui apporte, (3) ce qui reste à faire. Les compteurs d'activité ne sont plus le titre de la page : ils passent en bas, en petit, avec une légende qui dit ce qu'ils mesurent.

**Données** : utilise `getClientId`, `getDashboard` et `getOpportunities` de `src/lib/api.ts` (voir BOLT.md). Ne crée pas de nouvel appel réseau sauf indication contraire ci-dessous.

---

**1. Synthèse (en haut, sous le titre)**
- Une phrase d'état, construite à partir de `status` et des compteurs :
  - `running` : « Votre Hub est en préparation : nous analysons vos épisodes. »
  - `done` avec `resources_published > 0` : « Votre Hub publie {resources_published} pages d'expertise à partir de vos épisodes. »
  - `done` sans page publiée : « Votre analyse est terminée. Aucune page n'est encore publiée. »
  - `error` : « L'analyse n'a pas abouti. Vérifiez l'URL de votre flux RSS ou contactez-nous. »
  - `idle` sans source : « Ajoutez votre podcast pour démarrer la construction de votre Hub. »
- Si l'API renvoie une pause (la bannière de maintenance existante reste telle quelle).
- Bouton principal : « Voir mon Hub » vers `hub_urls[0]` (nouvel onglet). Si `hub_urls` est vide, le bouton est remplacé par « Votre Hub n'est pas encore publié ». Ne jamais écrire qu'une version « a été créée » si rien n'est publié.

**2. Trois bénéfices recherchés (le cœur de la page)**
Trois cartes côte à côte, dans cet ordre, avec un titre de bénéfice et une valeur principale :

- **Visibilité de votre expertise** : valeur = `resources_published` (pages publiées). Sous-texte : « Vos épisodes deviennent des réponses lisibles par Google et les IA. »
- **Réponses prêtes à être trouvées** : valeur = nombre d'éléments de `getOpportunities` avec `published === true`. Sous-texte : « Questions réelles de votre audience, avec une réponse autonome. »
- **Passage vers vous** : pas de donnée pour l'instant. Affiche « Bientôt disponible » et le sous-texte « Visites du Hub et demandes de contact, mesurées à partir du lancement. »

Chaque carte a un petit lien « Comment ça marche ? » qui ouvre un encadré d'une phrase, sans jargon.

**3. Votre Hub, étape par étape**
Une liste de 3 étapes qui correspondent aux piliers, avec un statut (fait / en cours / à faire) :
- **Branding** : « Charte de votre Hub (couleurs, logo, cover) » — « À faire » tant que la charte n'est pas enregistrée (la route arrive dans un lot ultérieur ; affiche « À faire » par défaut).
- **Expertise** : « Épisodes analysés » — `Fait` si `status === "done"`, `En cours` si `running` ou `pending`, `À faire` sinon.
- **Diffusion** : « Hub publié » — `Fait` si `hub_urls` n'est pas vide, sinon `À faire`.

**4. Indicateurs d'activité (en bas, petits, repliés par défaut)**
Un bloc titré « Indicateurs d'activité » avec un bouton « Afficher ». Il contient les trois cartes actuelles, réduites :
- Sources connectées = `sources_connected`
- Questions découvertes = `opportunities_found`
- Ressources publiées = `resources_published`

Sous ce bloc, une phrase : « Ces chiffres mesurent le travail effectué. Les bénéfices sont en haut de la page. »

**5. Sources** : garde la liste des sources existante (type, titre, badge de statut), sous le bloc d'activité.

---

**Libellés interdits** : « créé », « généré » ou « prêt » pour une page qui n'est pas publiée. Ne jamais afficher de zéro pour une métrique non collectée : affiche « Bientôt disponible ».

**Polling** : garde le rappel toutes les 10 secondes tant que `status === "running"`, avec nettoyage au démontage.

Ne change ni la sidebar, ni les autres pages, ni les couleurs de la marque.

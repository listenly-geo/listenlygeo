# Prompt à coller dans Bolt.ai — Accueil simplifié + vue Épisodes

Colle tout le bloc ci-dessous dans le chat Bolt. Il remplace le contenu de BOLT-6 (à ne pas appliquer en plus).

**Prérequis côté API** : `/api/dashboard/{client_id}` doit renvoyer un champ `episodes` (voir la section « API » en bas de ce fichier). Tant qu'il n'est pas déployé, la vue Épisodes affiche « Données bientôt disponibles ».

---

Refonds la page Overview (`/app`) en une synthèse simple, et ajoute une vue « Épisodes ». Garde le design existant (couleurs, typographies, sidebar, cartes). Ne change que le contenu et la hiérarchie.

**Connexion** : utilise `getClientId` et `getDashboard` de `src/lib/api.ts` (voir BOLT.md). Ajoute ce type à `api.ts` pour le champ `episodes` :

```ts
export type Episode = {
  title: string;
  status: "done" | "running" | "queued" | "pending" | "error";
  questions: number; // fiches de visibilité issues de cet épisode
  podcast: string;
};
```

Dans `getDashboard`, le retour contient aussi `episodes?: Episode[]` (utilise `data.episodes ?? []`).

---

**1. Accueil `/app` : synthèse**

- Titre : « Tableau de bord ». Garde la bannière de pause existante telle quelle si `system_paused` ou `paused` est vrai.
- Une phrase d'état, construite à partir de `status` et de `resources_published` :
  - `running` : « Votre Hub est en préparation. »
  - `done` et `resources_published > 0` : « Votre Hub publie {resources_published} fiches de visibilité. »
  - `done` et `resources_published === 0` : « Votre analyse est terminée. Aucune fiche n'est encore publiée. »
  - `error` : « L'analyse n'a pas abouti. Vérifiez l'URL de votre flux RSS ou contactez-nous. »
  - `idle` sans source : « Ajoutez votre podcast pour démarrer votre Hub. »
- Bouton « Voir mon Hub » vers `hub_urls[0]` (nouvel onglet). Si `hub_urls` est vide, affiche « Votre Hub n'est pas encore publié » à la place du bouton.
- Deux cartes seulement, côte à côte :
  - **Fiches de visibilité** : valeur = `resources_published`. Sous-texte : « Vos épisodes deviennent des réponses lisibles par Google et les IA. »
  - **Leads entrants** : valeur « Bientôt disponible », sans chiffre. Sous-texte : « Les demandes de contact reçues via votre Hub. »
- Pas d'autre carte sur cette page. Pas de compteur « sources » ni « questions » ici.

**2. Vue « Épisodes »** (nouvel élément dans la sidebar, entre Overview et Sources)

- Titre : « Épisodes ». Sous-titre : « Les épisodes analysés pour votre Hub. »
- Une liste, un élément par épisode de `data.episodes`, avec :
  - le titre de l'épisode ;
  - un badge de statut : `done` → vert « Analysé », `running` → bleu « En cours », `queued` ou `pending` → gris « En attente », `error` → rouge « Erreur » ;
  - le nombre de fiches : « {questions} fiche(s) de visibilité ».
- Trier : les épisodes `done` en premier, puis `running`, puis le reste.
- Si la liste est vide : « Aucun épisode analysé pour l'instant. »
- Si `episodes` est absent de la réponse : « Données bientôt disponibles ».

**3. Polling** : sur l'accueil et sur la vue Épisodes, rappelle `getDashboard` toutes les 10 secondes tant que `status === "running"`, et nettoie l'intervalle au démontage.

**Libellés interdits** : « créé », « généré » ou « prêt » pour une fiche non publiée. Une métrique non disponible s'affiche « Bientôt disponible », jamais « 0 ».

Ne change ni les couleurs de la marque, ni les autres pages (Sources, Opportunities, AI Hub, Visibility, Settings, Abonnement, Administration).

---

## API (à faire côté `marketforge-api/main.py`, avant de coller ce prompt)

Ajouter à la réponse de `/api/dashboard/{client_id}` un champ `episodes`, rempli dans `_collect` : pour chaque Hub, les `guid_to_src` (épisodes ayant un `guid`) reçoivent leur `status` et leur nombre de `questions` mis à jour. Il faut donc collecter les épisodes **dans la boucle existante**, pas à partir de `hub["sources"]` (qui n'a pas les statuts calculés) :

```python
# dans _collect, à l'intérieur de la boucle sur les hubs, après la mise à jour des statuts :
episodes_out.extend(
    {"title": src.get("title", ""), "status": src["status"],
     "questions": src.get("questions", 0), "podcast": hub["title"]}
    for src in guid_to_src.values()
)
```

Puis déclarer `episodes_out = []` au début de `_collect`, le renvoyer dans le dictionnaire retourné, et ajouter `"episodes": state["episodes"]` dans la réponse de `dashboard()`.

Point à vérifier avant de le coder : que chaque épisode a bien un `title` dans `hub["sources"]` (stocké à l'onboarding). Si ce n'est pas le cas, il faudra le récupérer depuis le flux RSS ou le registre.

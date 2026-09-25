# Prompt Bolt n°4 : tableau de bord « Suivi data »

À coller dans le chat Bolt après les prompts n°1 à n°3.

---

Refais la page **Visibility** (/app/visibility) en vrai tableau de bord de suivi. Les données viennent de `getVisibility(clientId)`, déjà présente dans `src/lib/api.ts`. Garde le design existant (cartes blanches, bordures fines, typographie actuelle).

**1. Types** : dans `src/lib/api.ts`, complète le type de retour de `getVisibility` avec :

```ts
queries: { query: string; clicks: number; impressions: number; position: number }[]; // dans chaque page
published_by_week: { week: string; count: number }[];
top_queries: { query: string; clicks: number; impressions: number; position: number; page: string }[];
```

**2. En haut : 4 cartes KPI** sur une ligne (2×2 sur mobile)
- « Pages publiées » = nombre d'éléments de `pages`.
- « Impressions Google » = `impressions`.
- « Clics Google » = `clicks`.
- « Position moyenne » = moyenne des `position` non nulles, pondérée par les impressions, arrondie à 1 décimale, ou « — » s'il n'y en a pas.
- Sous les cartes, en petit gris : « 28 derniers jours · du {period_start} au {period_end} · mis à jour le {updated_at} ».

**3. Graphique « Pages publiées par semaine »**
Histogramme simple en barres verticales, avec `published_by_week` (axe X : semaine au format « 22 sept. », axe Y : nombre de pages). Utilise `recharts` s'il est déjà installé, sinon des barres en CSS. S'il n'y a qu'une semaine, affiche quand même la barre.

**4. Bloc « Ce que les gens cherchent sur Google pour vous trouver »**
Tableau de `top_queries` (10 lignes max), colonnes : Recherche, Page, Impressions, Clics, Position. Si la liste est vide, affiche : « Aucune recherche pour l'instant : Google met en général 1 à 3 semaines à afficher de nouvelles pages dans ses résultats. »

**5. Tableau « Vos pages »**
Une ligne par élément de `pages`, colonnes : Titre (lien vers `url`, nouvel onglet), Type (« Page hub » ou « Fiche question »), Publiée le (`published_at`), Impressions, Clics, Position (« — » si null).
- Pour les fiches avec `indexable === false`, ajoute sous le titre, en gris : « Référencée via votre page hub ».
- Clic sur une ligne qui a des `queries` : la ligne se déplie et montre ses recherches (requête, impressions, clics, position).
- Tri par défaut : impressions décroissantes.

**6. États vides**
- Si `updated_at` est null : bandeau bleu clair « Vos statistiques Google arrivent : elles sont mises à jour chaque nuit, avec environ 3 jours de décalage. »
- Si `pages` est vide : « Aucune page publiée pour l'instant. Lancez une analyse depuis la page Sources. »

**7. Overview (/app)** : sous les 3 compteurs, ajoute une carte « Visibilité Google (28 jours) » avec impressions et clics issus de `getVisibility`, et un lien « Voir le suivi détaillé → » vers /app/visibility.

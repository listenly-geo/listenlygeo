# Prompt à coller dans Bolt.ai

Colle tout le bloc ci-dessous dans le chat Bolt.

---

Connecte le dashboard à mon API backend. Ne change pas le design existant, ajoute seulement la logique décrite.

**1. Configuration**
Crée `src/lib/api.ts` :

```ts
export const API_URL = "https://listenlygeo-production.up.railway.app";

// client_id = email de l'utilisateur connecté, en minuscules
export function getClientId(userEmail: string) {
  return userEmail.trim().toLowerCase();
}

async function post(path: string, body?: unknown) {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Erreur ${res.status}`);
  return res.json();
}

export const addSource = (client_id: string, type: string, value = "") =>
  post("/api/onboarding/sources", { client_id, type, value });
export const setStrategy = (client_id: string, strategy: "hub" | "site" | "both") =>
  post("/api/onboarding/strategy", { client_id, strategy });
export const startRun = (client_id: string) => post(`/api/run/${encodeURIComponent(client_id)}`);
export async function getDashboard(client_id: string) {
  const res = await fetch(`${API_URL}/api/dashboard/${encodeURIComponent(client_id)}`);
  if (!res.ok) throw new Error(`Erreur ${res.status}`);
  return res.json();
}
export async function getOpportunities(client_id: string) {
  const res = await fetch(`${API_URL}/api/opportunities/${encodeURIComponent(client_id)}`);
  return (await res.json()).opportunities as { question: string; answer: string; episode_title: string; url: string | null; published: boolean }[];
}
```

**2. Page /start, étape « Where does your expertise live? »**
- Correspondance carte → `type` API : Website → `website`, Podcasts → `podcast`, Videos → `video`, Documents → `document`, Webinars → `webinar`, Articles → `article`.
- Sur toutes les cartes sauf Podcasts, ajoute en haut à droite un petit badge gris « Bientôt disponible ». Elles restent sélectionnables : on enregistre l'intérêt du client, mais sans traitement.
- Quand Podcasts est sélectionnée, affiche sous la grille un champ obligatoire « URL du flux RSS de votre podcast » (placeholder : `https://feeds.exemple.com/mon-podcast.xml`), avec l'aide « Vous la trouvez dans Apple Podcasts, Spotify for Creators, Ausha, Acast… ».
- Quand Website est sélectionnée, affiche un champ optionnel « URL de votre site » (les boutons des fiches publiées pointeront vers ce site).
- Bouton « Continuer » : pour chaque carte sélectionnée, appelle `addSource(clientId, type, value)` avec `value = rssUrl` pour podcast, `websiteUrl` pour website, `""` sinon. L'API vérifie le flux RSS (2 à 5 secondes) : affiche un état de chargement sur le bouton. Si un appel échoue, affiche le message d'erreur sous le bouton et ne passe pas à l'étape suivante.

**3. Nouvelle étape « Où publier vos fiches ? » (juste après)**
Trois cartes à choix unique :
- `hub` : « Hub Marketforge », vos fiches publiées sur votre page Marketforge (recommandé)
- `site` : « Sur votre site », badge « Bientôt disponible »
- `both` : « Les deux », badge « Bientôt disponible »

Au clic sur « Continuer », appelle `setStrategy(clientId, choix)`.

**4. Fin de l'onboarding**
Sur le bouton final (« Lancer l'analyse ») : si au moins une source Podcast a été ajoutée, appelle `startRun(clientId)`, puis redirige vers `/app`. S'il n'y a pas de podcast, redirige directement vers `/app` sans appeler `startRun`. Si l'API répond 429, affiche « Beaucoup de demandes aujourd'hui : votre analyse démarrera demain » et redirige quand même vers `/app`.

**5. Overview (/app) : compteurs réels**
- Au chargement, appelle `getDashboard(clientId)`.
- Tant que `status === "running"`, rappelle-le toutes les 10 secondes, puis arrête le polling (nettoie l'intervalle au démontage).
- Carte SOURCES = `sources_connected`. Carte OPPORTUNITÉS = `opportunities_found`. Carte DÉPLOIEMENTS = `resources_published`.
- Si `hub_urls` n'est pas vide, ajoute sous les cartes un bouton « Voir votre page publiée » qui ouvre `hub_urls[0]` dans un nouvel onglet.
- Au-dessus des cartes, un bandeau d'état selon `status` :
  - `running` : spinner + « Nous écoutons vos épisodes et rédigeons vos premières fiches… (10 à 20 minutes, vous pouvez fermer cette page) »
  - `done` : « ✓ {opportunities_found} questions trouvées, {resources_published} pages publiées »
  - `error` : « L'analyse n'a pas abouti. Vérifiez l'URL de votre flux RSS ou contactez-nous. »
  - `idle` sans source : garde la carte actuelle « Configurez votre AI Hub »
- Sous les compteurs, affiche la liste `sources`. Pour chaque source : son type (et `title` pour un podcast), puis un badge vert « Analysé » si `status === "done"`, bleu « En cours » si `status === "running"` ou `"pending"`, rouge « Erreur » si `status === "error"`, gris « Bientôt disponible » si `status === "coming_soon"`. Si aucune source n'est un podcast, affiche : « Seuls les podcasts sont analysés pour l'instant. Ajoutez votre flux RSS pour voir vos premières questions. »

**6. Page Opportunities**
Appelle `getOpportunities(clientId)`. Pour chaque élément : la question en titre, la réponse en dessous, « Épisode : {episode_title} ». Si `published === true`, badge vert « Publiée » + lien « Voir la page » vers `url` ; sinon badge gris « En file d'attente ».

Le `clientId` est l'email de l'utilisateur connecté (celui affiché en bas de la sidebar), passé à `getClientId()`.

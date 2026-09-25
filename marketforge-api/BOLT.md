# Prompt à coller dans Bolt.ai

Remplace `https://TON-API.up.railway.app` par l'URL Railway, puis colle tout le bloc ci-dessous dans le chat Bolt.

---

Connecte le dashboard à mon API backend. Ne change pas le design existant, ajoute seulement la logique décrite.

**1. Configuration**
Crée `src/lib/api.ts` :

```ts
export const API_URL = "https://TON-API.up.railway.app";

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
  return (await res.json()).opportunities as { question: string; answer: string; episode_title: string; episode_link: string }[];
}
```

**2. Page /start, étape « Where does your expertise live? »**
- Correspondance carte → `type` API : Website → `website`, Podcasts → `podcast`, Videos → `video`, Documents → `document`, Webinars → `webinar`, Articles → `article`.
- Sur toutes les cartes sauf Podcasts, ajoute en haut à droite un petit badge gris « Bientôt disponible ». Elles restent sélectionnables : on enregistre l'intérêt du client, mais sans traitement.
- Quand Podcasts est sélectionnée, affiche sous la grille un champ obligatoire « URL du flux RSS de votre podcast » (placeholder : `https://feeds.exemple.com/mon-podcast.xml`), avec l'aide « Vous la trouvez dans Apple Podcasts, Spotify for Creators, Ausha, Acast… ».
- Bouton « Continuer » : pour chaque carte sélectionnée, appelle `addSource(clientId, type, type === "podcast" ? rssUrl : "")`. Si un appel échoue, affiche le message d'erreur sous le bouton et ne passe pas à l'étape suivante.

**3. Nouvelle étape « Où publier vos fiches ? » (juste après)**
Trois cartes à choix unique :
- `hub` : « Hub Marketforge », vos fiches publiées sur votre page Marketforge (recommandé)
- `site` : « Sur votre site », badge « Bientôt disponible »
- `both` : « Les deux », badge « Bientôt disponible »

Au clic sur « Continuer », appelle `setStrategy(clientId, choix)`.

**4. Fin de l'onboarding**
Sur le bouton final (« Lancer l'analyse ») : si au moins une source Podcast a été ajoutée, appelle `startRun(clientId)`, puis redirige vers `/app`. S'il n'y a pas de podcast, redirige directement vers `/app` sans appeler `startRun`.

**5. Overview (/app) : compteurs réels**
- Au chargement, appelle `getDashboard(clientId)`.
- Tant que `status === "running"`, rappelle-le toutes les 5 secondes, puis arrête le polling (nettoie l'intervalle au démontage).
- Carte SOURCES = `sources_connected`. Carte OPPORTUNITÉS = `opportunities_found`. Carte DÉPLOIEMENTS = `resources_published`, avec le badge « Bientôt disponible » et le sous-texte « La publication automatique arrive prochainement ».
- Au-dessus des cartes, un bandeau d'état selon `status` :
  - `running` : spinner + « Analyse de vos épisodes en cours… (1 à 2 minutes) »
  - `done` : « ✓ {opportunities_found} questions trouvées dans vos 3 derniers épisodes » + lien vers /app/opportunities
  - `error` : « L'analyse a échoué : {last_error}. Vérifiez l'URL de votre flux RSS. »
  - `idle` sans source : garde la carte actuelle « Configurez votre AI Hub »
- Sous les compteurs, affiche la liste `sources`. Pour chaque source : son type, puis un badge vert « Analysé » si `status === "done"`, bleu « En cours » si le traitement tourne, rouge « Erreur » si `status === "error"`, gris « Bientôt disponible » si `status === "coming_soon"`. Si toutes les sources sont `coming_soon`, affiche : « Seuls les podcasts sont analysés pour l'instant. Ajoutez votre flux RSS pour voir vos premières questions. »

**6. Page Opportunities**
Appelle `getOpportunities(clientId)` et affiche chaque question en titre, sa réponse en dessous, et « Source : {episode_title} » avec un lien vers `episode_link`.

Le `clientId` est l'email de l'utilisateur connecté (celui affiché en bas de la sidebar), passé à `getClientId()`.

# Prompt à coller dans Bolt.ai — Bouton « Télécharger mon Hub » + installation

Ajoute à la page d'accueil `/app`, sous la carte « Fiches de visibilité », un bloc « Votre Hub ». Garde le design existant.

**Connexion** : ajoute dans `src/lib/api.ts` :

```ts
export async function downloadHub(client_id: string, token?: string) {
  const res = await fetch(`${API_URL}/api/hub/${encodeURIComponent(client_id)}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Erreur ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "hub-podcast.zip";
  a.click();
  URL.revokeObjectURL(url);
}
```

**Contenu du bloc** :
- Titre : « Votre Hub ». Sous-titre : « Les pages de votre podcast, prêtes à être installées sur votre site. »
- Bouton « Télécharger mon Hub » qui appelle `downloadHub(clientId, session.access_token)`.
  - Pendant l'appel : « Préparation… ».
  - Si l'API répond 404 : affiche le message reçu (« Votre Hub n'est pas encore généré »).
- Sous le bouton, une liste de 3 étapes :
  1. Décompressez le fichier téléchargé.
  2. Déposez le dossier `podcast/` à la racine de votre site (ex. `votresite.fr/podcast/`).
  3. Dans Google Search Console, soumettez l'adresse `https://votresite.fr/podcast/sitemap.xml`.
- Si `hub_urls` n'est pas vide, un lien « Voir votre Hub » vers `hub_urls[0]`.

Ne change ni la sidebar, ni les autres pages.

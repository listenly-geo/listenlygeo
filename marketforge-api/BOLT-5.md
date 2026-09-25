# Prompt Bolt n°5 : bouton Pause

À coller dans le chat Bolt après les prompts n°1 à n°4.

---

Ajoute des boutons de pause au dashboard. Garde le design existant.

**1. `src/lib/api.ts`** : ajoute

```ts
export const setPaused = (client_id: string, paused: boolean) =>
  post(`/api/pause/${encodeURIComponent(client_id)}`, { paused, client_id }) as Promise<{ paused: boolean; cancelled_runs: number }>;

export async function getSystemPause(): Promise<{ paused: boolean }> {
  const res = await fetch(`${API_URL}/api/admin/pause`);
  return res.json();
}

export async function setSystemPause(paused: boolean, adminKey: string) {
  const res = await fetch(`${API_URL}/api/admin/pause`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Admin-Key": adminKey, ...authHeaders() },
    body: JSON.stringify({ paused }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Erreur ${res.status}`);
  return res.json() as Promise<{ paused: boolean; cancelled_runs: number }>;
}
```

Si l'API répond **423** à `startRun`, affiche le message `detail` renvoyé (analyses en pause) au lieu de rediriger.

**2. Pause du client** (Overview /app, et page Sources)
- `getDashboard` renvoie maintenant `paused` (booléen) et `system_paused` (booléen).
- En haut de l'Overview, à droite du titre « Tableau de bord », ajoute un interrupteur (switch) « Analyses actives », allumé quand `paused === false`.
  - Pour l'éteindre, demande d'abord confirmation : « Mettre vos analyses en pause ? Toute analyse en cours sera arrêtée. Vos pages déjà publiées restent en ligne. » Puis appelle `setPaused(clientId, true)` et affiche un toast « Analyses en pause » (ajoute « (1 analyse arrêtée) » si `cancelled_runs > 0`).
  - Le rallumer appelle `setPaused(clientId, false)`, sans confirmation, avec le toast « Analyses réactivées ».
- Quand `paused === true` : bandeau orange au-dessus des compteurs « ⏸ Vos analyses sont en pause. Aucune nouvelle fiche ne sera créée. », avec un bouton « Réactiver ». Désactive le bouton « Lancer une nouvelle analyse » de la page Sources.
- Quand `system_paused === true` : bandeau gris « Les analyses sont momentanément suspendues pour maintenance. Vos pages publiées restent en ligne. » Désactive aussi « Lancer une nouvelle analyse ».

**3. Page Administration** (`/app/admin`)
- Lien dans la sidebar « Administration » (icône bouclier), **visible uniquement** si l'email de l'utilisateur connecté est `admin@marketforge.fr`.
- Affiche l'état de `getSystemPause()` avec un grand interrupteur « Système Marketforge actif ».
- Champ « Clé administrateur » (type password), mémorisé dans `localStorage` sous `mf_admin_key` pour ne pas la retaper.
- Éteindre l'interrupteur demande confirmation : « Mettre TOUT le système en pause ? Toutes les analyses de tous les clients seront arrêtées immédiatement. » Puis appelle `setSystemPause(true, cle)` et affiche « Système en pause — {cancelled_runs} analyse(s) arrêtée(s) ». Le rallumer appelle `setSystemPause(false, cle)`.
- En cas d'erreur 403 : « Clé administrateur incorrecte ».

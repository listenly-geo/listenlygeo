# Prompt Bolt n°2 : abonnement, factures, visibilité

À coller dans le chat Bolt **après** le prompt n°1 (`BOLT.md`), qui doit déjà être appliqué.

---

Ajoute l'abonnement, les factures et le suivi de visibilité au dashboard. Garde le design existant et réutilise les composants déjà en place (cartes, boutons, badges).

**1. `src/lib/api.ts` : connexion + nouvelles fonctions**
- Si le projet utilise Supabase Auth, ajoute à **tous** les appels vers `API_URL` (GET et POST) l'en-tête `Authorization: Bearer <access_token>`, avec le jeton de `supabase.auth.getSession()`. Crée pour ça une fonction `authHeaders()` utilisée par `post()` et par tous les `fetch` GET.
- Si l'API répond **401**, redirige vers la page de connexion. Si elle répond **402**, redirige vers `/app/billing`.
- Ajoute ces fonctions :

```ts
export type Plan = { plan: string; name: string; amount: number; currency: string; interval: string; fiches_per_run: number };
export type Billing = { enabled: boolean; plan: string | null; status: string | null; active: boolean; renews_at: string | null; cancel_at_period_end: boolean; free_runs_left: number | null; can_run: boolean };
export type Invoice = { number: string; date: string; amount: number; currency: string; status: string; pdf_url: string; url: string };
export type VisibilityPage = { url: string; title: string; kind: "hub" | "question"; indexable: boolean; clicks: number; impressions: number; position: number | null; published_at?: string };

export const getPlans = () => get<{ enabled: boolean; plans: Plan[] }>("/api/billing/plans");
export const getBilling = (id: string) => get<Billing>(`/api/billing/${encodeURIComponent(id)}`);
export const getInvoices = (id: string) => get<{ invoices: Invoice[] }>(`/api/billing/${encodeURIComponent(id)}/invoices`);
export const startCheckout = (client_id: string, plan: string) => post("/api/billing/checkout", { client_id, plan }) as Promise<{ url: string }>;
export const openPortal = (client_id: string) => post("/api/billing/portal", { client_id }) as Promise<{ url: string }>;
export const getVisibility = (id: string) => get<{ period_start: string | null; period_end: string | null; updated_at: string | null; clicks: number; impressions: number; pages: VisibilityPage[] }>(`/api/visibility/${encodeURIComponent(id)}`);
```

(`get<T>(path)` est une petite fonction qui fait `fetch(API_URL + path, { headers: authHeaders() })`, gère 401/402 comme ci-dessus et renvoie `res.json()`.)

**2. Nouvelle page `/app/billing` « Abonnement & factures »** (lien dans la sidebar, sous Settings, icône carte bancaire)
- Appelle `getBilling(clientId)` et `getPlans()`.
- Si `getPlans().enabled === false` : affiche seulement « Le paiement en ligne arrive bientôt. »
- Bloc **« Votre abonnement »** :
  - si `active` : nom du plan, badge vert « Actif », « Prochain renouvellement : {renews_at} » (ou « Se termine le {renews_at} » si `cancel_at_period_end`), bouton « Gérer mon abonnement » qui appelle `openPortal(clientId)` puis redirige vers `url` ;
  - sinon : « Aucun abonnement actif », et si `free_runs_left > 0` : « Votre première analyse est offerte ».
- Bloc **« Choisir une formule »** (seulement si pas `active`) : une carte par plan de `getPlans().plans`, avec `name`, le prix au format `{amount} € / {interval === "month" ? "mois" : "an"}` HT et « {fiches_per_run} fiches par analyse ». Le bouton « Choisir » appelle `startCheckout(clientId, plan.plan)` et redirige vers `url`, avec un état de chargement.
- Bloc **« Historique des factures »** : tableau de `getInvoices(clientId).invoices` (colonnes Date, Numéro, Montant, Statut, avec le badge « Payée » si `status === "paid"`, et un lien « Télécharger (PDF) » vers `pdf_url`). Si la liste est vide : « Aucune facture pour l'instant ». Si l'appel renvoie 401 : « Connectez-vous pour voir vos factures ».
- Si l'URL contient `?status=success` : bandeau vert « Merci ! Votre abonnement est actif. » (rappelle `getBilling` toutes les 3 s pendant 30 s maximum jusqu'à ce que `active` soit vrai). Si `?status=cancel` : bandeau gris « Paiement annulé ».

**3. Overview (/app)**
- Appelle aussi `getBilling(clientId)`. Si `enabled && !can_run`, affiche au-dessus des compteurs un bandeau : « Votre analyse offerte a été utilisée. Choisissez une formule pour publier de nouvelles fiches. », avec un bouton vers `/app/billing`.

**4. Page Visibility (/app/visibility)**
- Appelle `getVisibility(clientId)`.
- En haut, 2 cartes : « Clics Google » = `clicks` et « Impressions Google » = `impressions`, avec en sous-titre « 28 derniers jours (du {period_start} au {period_end}) ».
- Puis un tableau des `pages` : Titre (lien vers `url`), Type (« Page hub » ou « Fiche question »), Impressions, Clics, Position moyenne (`position` arrondie, « — » si null).
- Pour les fiches avec `indexable === false`, ajoute sous le titre la mention grise : « Référencée via votre page hub ».
- Si `updated_at` est null : « Les premières statistiques Google apparaissent 3 à 7 jours après la publication de vos pages. »
- Note en bas de page : « Données Google Search Console, mises à jour chaque jour avec 3 jours de décalage. »

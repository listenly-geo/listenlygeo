# Regles du depot

## MarketForge Engine : journal des optimisations (OBLIGATOIRE)
Toute optimisation du MarketForge Engine (ciblage, mots-cles, envoi, delivrabilite, mail, mesure, correction de bug)
doit etre ajoutee dans `automation/marketforge_engine/optimisations.json` dans le MEME commit :
- une ligne par optimisation : `section`, `version` (V1.0, V1.1… = lot de mise en ligne), `texte` (phrase claire, en francais, comprehensible sans contexte technique), `date` (JJ/MM/AAAA), `statut`
- statut : `en_cours` a la mise en ligne, `valide` quand Etienne l'a valide (contenu ou resultat), `a_faire` pour ce qui est decide mais pas commence
- ce fichier alimente automatiquement l'onglet "Optimisations" du Google Sheet (chaque run, via `sheet_bridge.py optimisations`)
Le proprietaire (Etienne) veut une clarte complete, chaque jour, sur ce qui a ete optimise et ou ca en est.

## Decision 15/10/2026 : SEO d'abord, Hub a la creation (remplace la regle "Hub a la reponse")
- Les fiches de moments deja rattachees a une fiche N1 gardent ce rattachement.
- Tout nouveau podcast qui apporte de nouvelles requetes recoit une fiche N1 au format Hub, creee des la decouverte (pas besoin de reponse du prospect).
- Qualite minimale obligatoire (meme seuil que les moments, sinon noindex) et quota quotidien de creation.
- PRECISION 27/10/2026 : toute fiche N1 est creee en NOINDEX (follow). Elle est indexee par le SCORING MOMENT SYSTEM en meme temps que sa premiere fiche moment (balise noindex retiree dans `sync_hubs_sitemap`, entree dans sitemap-hubs.xml). Jamais indexable des la creation.
- Les titres SEO des pages de moments sont dans `pages/podcast-btb/data/titres_seo.json` (cle `slug/id`), appliques au `<title>` par `m.php`.

## Positionnement MarketForge : PODCAST HUB (decision d'Etienne, 01/10/2026) — PRIORITAIRE
CAP : trafic de masse et autorite de masse vers Listenly, cash de masse via le moteur autorite. Le produit vendu aux podcasts B2B est un PODCAST HUB : a partir du podcast existant d'une entreprise, un Hub cle en main, brande a son image, qui transforme son catalogue audio en actif web : (1) BRANDING : une vraie vitrine du podcast (cover, description, lecteur, episodes, invites, CTA, identite visuelle, mobile) ; (2) VISIBILITE : l'expertise des episodes (questions reelles, reponses autonomes, timestamps, episodes sources, experts) devient lisible par Google et les IA ; (3) CONVERSION : transformer l'audience en prospects. Dans chaque Hub, une vraie fonctionnalite de recherche renvoie vers Listenly (ex. « Explore more expert answers ») sans « Powered by » artificiels : chaque Hub adopte est un point d'entree utile vers Listenly.
FUNNEL (on garde tout le systeme actuel, seul le mail change) : 1) le moteur trouve le podcast, cree la fiche Listenly et recupere l'email ; 2) mail 1 en anglais qui explique le Hub et propose « I can build a first version for {PODCAST} from your existing episodes, with no commitment. Shall I send it over? » (PAS de lien d'apercu dans ce mail), puis relance ; 3) si le prospect repond oui : generation de son Hub V1 brande + envoi avec lien de paiement integre ; 4) s'il paie ~500 $, installation sur son site ; maintenance/synchronisation 99 a 199 $/mois a tester (prix non figes).
REGLE : ne jamais ecrire dans un mail qu'une version « a ete creee » tant qu'elle n'existe pas : le mail propose de la construire. Le Hub V1 se genere A LA REPONSE. Les relances ne concernent jamais les prospects de l'ancien mail « listed on Listenly » (decision du 01/10).
Listenly peut rester discret dans le mail ; il est le moteur de recherche global derriere les Hubs et la base d'expertise multi-podcasts.
PRECISION 27/10/2026 (Etienne) : pour atteindre 30 prospects/jour, les createurs, coachs et experts independants identifiables sont acceptes a la qualification (plus de rejet « pas une entreprise »). Medias, celebrites et divertissement restent refuses.
PRIORITE = QUALITE, pas volume brut ni backlinks. Prospects prioritaires : B2B rattache a une entreprise, domaine proprietaire, catalogue important, actif, contenu expert, responsable marketing/content/podcast/founder identifiable ; a eviter : hobby, sans entreprise, morts, peu d'episodes, divertissement pur.
METRIQUES : emails envoyes, taux de livraison, taux de reponse, reponses positives (« send it »), V1 envoyees, paiements du setup, passage en abonnement.
QUESTION UNIQUE : une entreprise B2B paie-t-elle pour que son podcast existant devienne un Hub brande, searchable, exploitable par Google et les IA ?

## Charte graphique du moteur trafic (decision 19/10/2026)
- Les fiches N1 (hubs) et les pages de moment sur listenly.org suivent la charte sombre Listenly : fond noir (#000000), cartes grises (#1C1C1E), texte #F5F5F7, accent #2997FF, police systeme, logo Listenly en haut a gauche, barre de recherche, lecteur en bas. Reference : pages/podcast-btb/m-template.html.
- Le branding de l'entreprise (pochette, couleurs) n'est pas utilise dans cette phase : la priorite est le trafic.
- Les prospects et l'offre Hub brande sont hors perimetre tant que l'on se concentre sur le trafic.
- Toute nouvelle page N1 ou moment doit reprendre cette charte. Les hubs deja en ligne (style clair) sont a migrer, pas a refaire.

## Deploiement Apps Script : AUTOMATIQUE (decision du 13/10/2026)
La connexion clasp d'Etienne est enregistree (secret GitHub CLASPRC_JSON, compte etienne.cugnet@marketforge.fr) : ne JAMAIS lui redemander de coller le code ni de redeployer.
Pour publier une nouvelle version du script : mettre automation/apps-script/MarketForgeEngine.gs a jour, ecrire `deploy` en 1re ligne de automation/apps-script/deploy-script-now.txt (`publish` = republier sans changer le code, `dry` = lecture seule), commit + push : le workflow « Apps Script — lecture / deploiement » remplace le code, cree une version et la branche sur l'URL du pont.
Seul cas ou redemander quelque chose : le journal affiche `RefreshError` / `invalid_grant` (jeton revoque) -> refaire `npx.cmd @google/clasp login` et recoller `.clasprc.json` dans CLASPRC_JSON.

## Regle du reservoir (decision du 27/10/2026) : RIEN NE PART TANT QUE LE STOCK N'EST PAS A 30
- PRECISION 09/11/2026 (Etienne) : la PRODUCTION ne s'arrete plus a 40 prospects prets. Le reservoir se remplit tous les jours pour pouvoir augmenter progressivement le volume d'envoi ; seul un plafond de securite (MFE_STOCK_PLAFOND, 500) l'arrete.
- Chaque jour, les prospects se stockent de 6h a 14h ; l'envoi ne demarre que si au moins 30 prospects "Pret" (question reelle + fiche N1) sont disponibles (reglage `MFE_STOCK_MIN`, 30 par defaut). Une fois atteint, l'envoi reste ouvert jusqu'a minuit, de facon progressive.
- PRECISION 16/11/2026 (Etienne) : si le stock n'a pas atteint le minimum a l'ouverture de la plage d'envoi (14h), l'envoi demarre QUAND MEME avec les prospects prets disponibles, sans minimum. L'objectif de stock reste `MFE_STOCK_MIN` et la production continue de le viser. Reglage `MFE_OUVERTURE_FORCEE` (TRUE par defaut, Sheet Reglages) ; FALSE = ancienne regle stricte. Les relances restent soumises au stock atteint (priorite au 1er mail).
- Extraction ciblee (16/11/2026) : `marketforge_extract_queue.py` ne transcrit que les prospects « Pret » du Sheet (adresse + fiche N1) sans question (`extraction_seulement_contactables`), sur les `audio_minutes_max_par_episode` (20) premieres minutes, plafond `MFE_EPISODES_PAR_JOUR` (100).
- Applique dans `mfeSend_` (Apps Script, `mfeStockGate_`) et dans `envoi_secours.py`. Ne jamais remettre `MFE_ENVOI_AUTO` a TRUE pour contourner cette regle.
- Envoi de nuit (27/10/2026) : le « jour d'envoi » va de 14h a 14h le lendemain. Si le stock de 30 n'est atteint qu'apres 18h, les 30 mails sont etales jusqu'a 6h du matin (MFE_NUIT_JUSQU_A, MFE_NUIT_SI_OUVERT_APRES), sans rafale de rattrapage.

## Week-end : le stock se remplit, mais AUCUN mail ne part (decision du 08/11/2026, remplace celle du 07/11/2026)
- Samedi et dimanche : decouverte, creation de fiche N1 et recherche de contact tournent normalement pour constituer du stock bonus. Le lundi demarre avec un stock plein.
- Ne partent PAS le samedi et le dimanche (heure de Paris) : premiers mails, relances, envoi de secours. Reglage : MFE_WEEKEND_PAUSE = TRUE (Sheet, Reglages).
- Les jobs `garde` des workflows marketforge-engine-run et marketforge-contact-finder ne bloquent plus le week-end. Ne jamais remettre FALSE sur MFE_WEEKEND_PAUSE sans demande d'Etienne.
- Hors perimetre : le moteur trafic / SCORING MOMENT SYSTEM (systeme separe).

## Plan B contact : l'adresse du flux RSS verifiee suffit (decision du 09/11/2026)
- Objectif : le plus de prospects contactables possible (independants acceptes). Sans dirigeant verifie, le mail part a l'adresse du flux RSS si MyEmailVerifier la confirme `valid` (MFE_DIRIGEANT_SEUL = FALSE).
- Ordre d'envoi : dirigeants verifies d'abord, contacts du flux RSS ensuite. Les envois au flux sont reperes dans la colonne Notes du Sheet (« Envoye au contact du flux RSS ») pour comparer les taux de reponse.
- Repechage (`discover_podcasts.py`, DISCOVERY_RSS_FALLBACK / DISCOVERY_RESCUE_MAX) : les podcasts ecartes seulement par le filtre dirigeant repassent par le plan B, une fois chacun.
- Podcast Index : source de decouverte complementaire a iTunes (cle + secret dans Reglages : MFE_PODCASTINDEX_KEY / MFE_PODCASTINDEX_SECRET). Ne jamais ecrire ces valeurs dans le depot.

## Relances secondaires (decision du 15/11/2026)
- Priorite absolue au 1er mail. Les relances ne partent que dans la plage 14h-24h, une fois le stock atteint, si les 1ers mails du jour sont a l'heure, au plus `MFE_RELANCES_MAX_JOUR` (40) par jour d'envoi, etalees, R1 > R2 > R3 puis les plus anciennes d'abord (`mfeRelanceBudget_`). Week-end : aucune relance (inchange).

## Onboarding Index (decision du 15/11/2026)
- Apres paiement Stripe (297 EUR), le client arrive sur `https://app.marketforge.fr/onboarding/?session_id={CHECKOUT_SESSION_ID}` (source : `automation/onboarding/index.html`, deploiement : workflow `onboarding-deploy.yml`). Reponses -> onglet `Onboarding` du Sheet (action publique `onboarding_public` d'Apps Script, protegee par l'identifiant de session Stripe ; verification Stripe active si la propriete de script `STRIPE_SECRET_KEY` existe). Ne jamais mettre le secret du pont dans la page.

## Index (app.marketforge.fr) : indexation Google et IA (15/11/2026)
- Les pages publiees (`/docs/{site}/{page}`) embarquent cote serveur : titre, description, canonical, balises de partage, donnees structurees (Article + BreadcrumbList), texte sans JavaScript (`<noscript>`) et liens internes (`app/Support/DocsSeo.php`). Plan du site : `/sitemap.xml` et `/docs/{site}/sitemap.xml` ; `robots.txt` y renvoie. `settings_json.seo.noindex = true` retire un Index de l'indexation.
- Deploiement : workflow `index-seo-deploy.yml` (mode `deploy` puis `verifier`) ; il modifie routes/web.php, la vue racine et robots.txt A PARTIR de la version du serveur et garde une sauvegarde `.bak-seo`.
- Domaine du client (18/11/2026) : l'app sert un Index selon l'hote demande (`CustomDomainController`, routes ajoutees par `index-domains-deploy.yml` avec sauvegarde `.bak-dom` et retour arriere automatique). `index_domains.py` (workflow `index-domains.yml`, toutes les 20 min) relie le domaine, l'ajoute a l'hebergement (secrets CPANEL_HOST / CPANEL_USER / CPANEL_TOKEN), verifie DNS + HTTPS et fait passer le statut Pret > DNS a faire > En ligne (mails via Apps Script). Le canonical n'utilise le domaine du client que s'il est `active` ; sinon app.marketforge.fr. Ne jamais ecrire le jeton cPanel dans le depot.


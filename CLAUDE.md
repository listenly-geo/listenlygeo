# Regles du depot

## MarketForge Engine : journal des optimisations (OBLIGATOIRE)
Toute optimisation du MarketForge Engine (ciblage, mots-cles, envoi, delivrabilite, mail, mesure, correction de bug)
doit etre ajoutee dans `automation/marketforge_engine/optimisations.json` dans le MEME commit :
- une ligne par optimisation : `section`, `version` (V1.0, V1.1… = lot de mise en ligne), `texte` (phrase claire, en francais, comprehensible sans contexte technique), `date` (JJ/MM/AAAA), `statut`
- statut : `en_cours` a la mise en ligne, `valide` quand Etienne l'a valide (contenu ou resultat), `a_faire` pour ce qui est decide mais pas commence
- ce fichier alimente automatiquement l'onglet "Optimisations" du Google Sheet (chaque run, via `sheet_bridge.py optimisations`)
Le proprietaire (Etienne) veut une clarte complete, chaque jour, sur ce qui a ete optimise et ou ca en est.

## Positionnement MarketForge : PODCAST HUB (decision d'Etienne, 01/10/2026) — PRIORITAIRE
CAP : trafic de masse et autorite de masse vers Listenly, cash de masse via le moteur autorite. Le produit vendu aux podcasts B2B est un PODCAST HUB : a partir du podcast existant d'une entreprise, un Hub cle en main, brande a son image, qui transforme son catalogue audio en actif web : (1) BRANDING : une vraie vitrine du podcast (cover, description, lecteur, episodes, invites, CTA, identite visuelle, mobile) ; (2) VISIBILITE : l'expertise des episodes (questions reelles, reponses autonomes, timestamps, episodes sources, experts) devient lisible par Google et les IA ; (3) CONVERSION : transformer l'audience en prospects. Dans chaque Hub, une vraie fonctionnalite de recherche renvoie vers Listenly (ex. « Explore more expert answers ») sans « Powered by » artificiels : chaque Hub adopte est un point d'entree utile vers Listenly.
FUNNEL (on garde tout le systeme actuel, seul le mail change) : 1) le moteur trouve le podcast, cree la fiche Listenly et recupere l'email ; 2) mail 1 en anglais qui explique le Hub et propose « I can build a first version for {PODCAST} from your existing episodes, with no commitment. Shall I send it over? » (PAS de lien d'apercu dans ce mail), puis relance ; 3) si le prospect repond oui : generation de son Hub V1 brande + envoi avec lien de paiement integre ; 4) s'il paie ~500 $, installation sur son site ; maintenance/synchronisation 99 a 199 $/mois a tester (prix non figes).
REGLE : ne jamais ecrire dans un mail qu'une version « a ete creee » tant qu'elle n'existe pas : le mail propose de la construire. Le Hub V1 se genere A LA REPONSE. Les relances ne concernent jamais les prospects de l'ancien mail « listed on Listenly » (decision du 01/10).
Listenly peut rester discret dans le mail ; il est le moteur de recherche global derriere les Hubs et la base d'expertise multi-podcasts.
PRIORITE = QUALITE, pas volume brut ni backlinks. Prospects prioritaires : B2B rattache a une entreprise, domaine proprietaire, catalogue important, actif, contenu expert, responsable marketing/content/podcast/founder identifiable ; a eviter : hobby, sans entreprise, morts, peu d'episodes, divertissement pur.
METRIQUES : emails envoyes, taux de livraison, taux de reponse, reponses positives (« send it »), V1 envoyees, paiements du setup, passage en abonnement.
QUESTION UNIQUE : une entreprise B2B paie-t-elle pour que son podcast existant devienne un Hub brande, searchable, exploitable par Google et les IA ?

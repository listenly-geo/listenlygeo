# Reflexion du MarketForge Engine (2026-10-07T19:16 UTC)
**Statut : BLOQUE**

## Funnel
- podcasts en file : 497
- contacts prets a mailer : 340
- bloques en attente : 0
- sans email : 68
- prospects dans sheet : 300
- statut pret : 80
- mails envoyes : 227
- relances : 16
- rebonds total : 4
- reponses reelles : 1
- reponses classees : 0
- reponses positives : 0
- demos envoyees : 0
- paiements hub : 0

## Blocages
- Envois sous 50 % du plafond (80/j) alors que des prospects sont prets : Apps Script arrete ou plage horaire/quota en cause.
- Statistiques non rafraichies depuis plus de 8 h (2026-10-07T06:33) : bridge Sheet ou Apps Script a l'arret.
- Reponses non classees (positive / neutre / refus) : impossible de savoir si le funnel marche. Ajouter le champ 'classe' dans replies.json.

## Pourquoi pas encore de client
- Ordre de grandeur (hypothese, pas une mesure) : un 1er client a ~1500 $ demande souvent 500 a 3000 mails froids. Il en reste 273 a 2773, soit environ 3 a 34 jours au rythme actuel (80/j).
- Reponse 0.4 % : sous le seuil habituel (1-3 %). L'accroche ou la cible est a revoir avant d'augmenter le volume.
- 17 secteurs avec moins de 15 envois : aucun signal par niche, ne pas en tirer de conclusion.
- Test A/B CTA : trop tot pour un gagnant. Ne rien changer avant 100 envois par variante.
- Relances envoyees sans reponse positive : mesurer separement 1er mail vs relances.

## Actions proposees
- Classer chaque reponse reelle : positive (interesse par le Hub), neutre, refus.

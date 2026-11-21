# Reflexion du MarketForge Engine (2026-11-21T20:58 UTC)
**Statut : BLOQUE**

## Funnel
- podcasts en file : 2756
- contacts prets a mailer : 287
- bloques en attente : 1279
- sans email : 68
- prospects dans sheet : 300
- statut pret : 0
- mails envoyes : 1055
- relances : 224
- rebonds total : 0
- reponses reelles : 6
- reponses classees : 0
- reponses positives : 0
- demos envoyees : 0
- paiements hub : 0

## Blocages
- Aucun contact cree depuis 2 jours alors que 1279 podcasts attendent : etape 'contact' bloquee (verifier extraction_auto, doit etre false).
- extraction_auto=true : les nouveaux podcasts restent en 'en_attente' au lieu de passer en contact.
- Reponses non classees (positive / neutre / refus) : impossible de savoir si le funnel marche. Ajouter le champ 'classe' dans replies.json.

## Pourquoi pas encore de client
- Ordre de grandeur (hypothese, pas une mesure) : un 1er client a ~1500 $ demande souvent 500 a 3000 mails froids. Il en reste 0 a 1945, soit environ 0 a 27 jours au rythme actuel (70/j).
- Reponse 0.6 % : sous le seuil habituel (1-3 %). L'accroche ou la cible est a revoir avant d'augmenter le volume.
- 20 secteurs avec moins de 15 envois : aucun signal par niche, ne pas en tirer de conclusion.
- Relances envoyees sans reponse positive : mesurer separement 1er mail vs relances.

## Actions proposees
- Verifier config.json : extraction_auto=false, onboarding_auto=true, pause=false.
- Classer chaque reponse reelle : positive (interesse par le Hub), neutre, refus.

# Reflexion du MarketForge Engine (2026-11-09T21:24 UTC)
**Statut : BLOQUE**

## Funnel
- podcasts en file : 1355
- contacts prets a mailer : 287
- bloques en attente : 267
- sans email : 68
- prospects dans sheet : 300
- statut pret : 73
- mails envoyes : 708
- relances : 30
- rebonds total : 5
- reponses reelles : 2
- reponses classees : 0
- reponses positives : 0
- demos envoyees : 0
- paiements hub : 0

## Blocages
- Aucun contact cree depuis 2 jours alors que 267 podcasts attendent : etape 'contact' bloquee (verifier extraction_auto, doit etre false).
- extraction_auto=true : les nouveaux podcasts restent en 'en_attente' au lieu de passer en contact.
- Reponses non classees (positive / neutre / refus) : impossible de savoir si le funnel marche. Ajouter le champ 'classe' dans replies.json.

## Pourquoi pas encore de client
- Ordre de grandeur (hypothese, pas une mesure) : un 1er client a ~1500 $ demande souvent 500 a 3000 mails froids. Il en reste 0 a 2292, soit environ 0 a 76 jours au rythme actuel (30/j).
- Reponse 0.3 % : sous le seuil habituel (1-3 %). L'accroche ou la cible est a revoir avant d'augmenter le volume.
- 16 secteurs avec moins de 15 envois : aucun signal par niche, ne pas en tirer de conclusion.
- Test A/B CTA : trop tot pour un gagnant. Ne rien changer avant 100 envois par variante.
- Relances envoyees sans reponse positive : mesurer separement 1er mail vs relances.

## Actions proposees
- Verifier config.json : extraction_auto=false, onboarding_auto=true, pause=false.
- Classer chaque reponse reelle : positive (interesse par le Hub), neutre, refus.

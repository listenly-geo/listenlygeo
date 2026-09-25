# Prompt Bolt n°3 : toutes les sources actives

À coller dans le chat Bolt après les prompts n°1 et n°2.

---

Toutes les sources sont maintenant traitées par l'API : vidéos, webinars, articles, documents et site web, en plus des podcasts. Mets à jour l'onboarding, l'Overview et la page Sources. Garde le design existant.

**1. Page /start, étape « Where does your expertise live? »**
- Retire tous les badges « Bientôt disponible » des cartes de sources.
- Quand une carte est sélectionnée, affiche en dessous le champ correspondant. Les champs marqués « plusieurs » ont un bouton « + Ajouter un lien » pour saisir plusieurs URL.
  - Podcasts : « URL du flux RSS de votre podcast » (aide : « Apple Podcasts, Spotify for Creators, Ausha, Acast… »)
  - Website : « Adresse de votre site » (aide : « Nous lisons la page d'accueil. Les boutons de vos fiches renverront vers ce site. »)
  - Videos : « Liens de vos vidéos » (plusieurs ; aide : « YouTube, Vimeo ou fichier .mp4, 90 minutes analysées au maximum par vidéo »)
  - Webinars : « Liens de vos replays » (plusieurs ; même aide que Videos)
  - Articles : « Liens de vos articles » (plusieurs ; aide : « Une URL par article de blog »)
  - Documents : « Liens de vos PDF » (plusieurs ; aide : « Livres blancs, études, guides : lien public vers le fichier .pdf »)
- Bouton « Continuer » : appelle `addSource(clientId, type, url)` **une fois par URL saisie**, avec `type` ∈ `podcast`, `website`, `video`, `webinar`, `article`, `document`. En cas d'erreur, affiche le message renvoyé sous le champ concerné et ne passe pas à l'étape suivante.

**2. Overview (/app), liste « Vos sources »**
Pour chaque élément de `sources` renvoyé par `getDashboard` :
- Libellé : le type en français (Podcast, Site web, Vidéo, Webinar, Article, Document), puis `title` s'il existe, sinon l'URL `value` raccourcie (domaine + début du chemin).
- Badge selon `status` :
  - `running` : bleu « En cours d'analyse »
  - `done` : vert « Analysé · {questions} question(s) » ; mais si `empty === true`, orange « Aucune question exploitable » avec l'infobulle « Contenu trop court, privé ou illisible : vérifiez que le lien est public. »
  - `queued` : gris « Au prochain passage » avec l'infobulle « 2 nouvelles sources sont analysées par passage. »
  - `pending` : gris « En attente »
  - `error` : rouge « Erreur »
- Retire le message « Seuls les podcasts sont analysés pour l'instant ».
- Bandeau `running` : « Nous analysons vos contenus et rédigeons vos premières fiches… (10 à 20 minutes, vous pouvez fermer cette page) ».

**3. Page Sources (/app/sources)**
- Affiche la même liste de sources, avec les mêmes badges, et un bouton « + Ajouter une source ». Ce bouton ouvre une fenêtre avec un choix de type (les 6 types ci-dessus) et un champ URL, puis appelle `addSource`.
- Sous la liste, un bouton « Lancer une nouvelle analyse » appelle `startRun(clientId)`. Si la réponse vaut `status === "already_started"`, affiche « Une analyse a déjà été lancée récemment : la prochaine sera possible 12 h après la précédente. » ; 429 : « Beaucoup de demandes aujourd'hui, réessayez demain » ; 402 : redirige vers `/app/billing`.

**4. Page Opportunities**
- Ajoute devant chaque question une petite étiquette avec le type de source `source_type` (Podcast, Vidéo, Webinar, Article, Document, Site web).
- Remplace « Épisode : {episode_title} » par « Source : {episode_title} ».

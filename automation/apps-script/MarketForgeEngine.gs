/**
 * MarketForge Engine — branchement Google Sheet + mail (27/09/2026)
 *
 * A coller dans le projet Apps Script du Sheet de prospection podcasts (1b53cWGiz6iOuakpotw_Ck4bQBeIMJa3hfq5gP2mFiT4)
 * (Extensions > Apps Script > + > Script > nommer "MarketForgeEngine"), sans toucher aux autres fichiers.
 *
 * Ce que ca fait, toutes les heures :
 *  1. Lit la file du MarketForge Engine sur GitHub (queue.json).
 *  2. Ajoute dans l'onglet "MarketForge Engine" chaque podcast qui a un email ET une preuve
 *     (fiche N1 avec ses reponses extraites). Jamais de doublon.
 *  3. Envoie le mail "vous etes reference + preuve + RDV" (si ENVOI_AUTO = TRUE), puis 1 relance
 *     a J+RELANCE_JOURS s'il n'y a pas eu de reponse.
 *
 * Premiere utilisation : executer une fois installer() (cree l'onglet + le declencheur quotidien 9h).
 * Reglages : TOUT se pilote depuis l'onglet "Reglages" (cles MFE_*) : mails ET moteur GitHub
 * (pause, decouverte, onboarding, extraction). Le run GitHub lit ces valeurs chaque matin.
 *
 * Pont GitHub (application web) : Deployer > Nouveau deploiement > Application web
 * (Executer en tant que : Moi / Acces : Tout le monde). L'URL + ?secret=... (affiche par
 * installer() dans le journal) va dans le secret GitHub MFE_SHEET_URL.
 * GitHub y lit les reglages (GET action=config) et y ecrit son compte-rendu (POST action=report) :
 * onglet "Historique Engine" + lignes de l'onglet "MarketForge Engine".
 */

var MFE = {
  QUEUE_URL: 'https://raw.githubusercontent.com/listenly-geo/listenlygeo/main/automation/marketforge_engine/queue.json',
  AB_URL: 'https://raw.githubusercontent.com/listenly-geo/listenlygeo/main/automation/marketforge_engine/ab_test.json',
  SHEET: 'MarketForge Engine',
  FROM: 'etienne.cugnet@marketforge.fr',           // utilise si c'est un alias Gmail du compte qui execute le script
  NAME: 'Etienne Cugnet',
  BOOKING: 'https://cal.com/etienne-marketforge/podcast-distribution-strategy-call',
  HEADER_ROW: 6,                                    // ligne 6 = en-tetes (reglages : onglet Reglages)
  REGLAGES: 'Réglages',
  HISTO: 'Historique Engine',
  HISTO_COLS: ['Date', 'Decouverts', 'Onboardes (fiche Listenly + N1)', 'Dont fiches Listenly creees',
               'Podcasts onboardes', 'Episodes extraits', 'Minutes audio', 'Q/R extraites', 'Echecs onboarding', 'Run GitHub'],
  COLS: ['Slug', 'Podcast', 'Email', 'Preuve (fiche N1)', 'Q/R extraites', 'Ajoute le', 'Statut',
         'Envoye le', 'Relance le', 'Reponse', 'Thread ID', 'Notes', 'Page Listenly', 'Hote', 'Variante CTA', 'Thematique',
         'Dernier épisode Q', 'Dernier épisode Moment ID'],
};

var MFE_DEFAULTS = [
  ['MFE_PAUSE', 'FALSE', 'MarketForge Engine — TRUE = tout le moteur GitHub s\'arrete (decouverte, onboarding, extraction).'],
  ['MFE_DECOUVERTE_MAX_JOUR', '15', 'MarketForge Engine — podcasts qualifies PAR RUN (plusieurs runs/jour, cout Claude).'],
  ['MFE_ONBOARDING_AUTO', 'TRUE', 'MarketForge Engine — TRUE = fiche Listenly + N1 creees automatiquement. FALSE = validation manuelle (label approved).'],
  ['MFE_ONBOARDING_MAX_JOUR', '15', 'MarketForge Engine — fiches Listenly + N1 creees PAR RUN.'],
  ['MFE_EXTRACTION_AUTO', 'FALSE', 'MarketForge Engine — TRUE = transcrit + extrait les Q/R de chaque podcast (cher). FALSE = fiche N1 + email seulement.'],
  ['MFE_EPISODES_PAR_JOUR', '10', 'MarketForge Engine — episodes transcrits par jour (cout Whisper + Claude).'],
  ['MFE_EPISODES_PAR_PODCAST', '3', 'MarketForge Engine — profondeur d\'extraction par podcast.'],
  ['MFE_MINUTES_AUDIO_MAX_JOUR', '600', 'MarketForge Engine — garde-fou minutes audio par jour.'],
  ['MFE_ENVOI_AUTO', 'TRUE', 'MarketForge Engine — TRUE = envoie les mails automatiquement. FALSE = prepare seulement (statut "Pret").'],
  ['MFE_MAX_ENVOIS_JOUR', '1500', 'MarketForge Engine — plafond absolu de premiers mails par jour (limite Google Workspace : 1500).'],
  ['MFE_MONTEE_PROGRESSIVE', 'TRUE', 'MarketForge Engine — TRUE = 44/j la 1re semaine (1 mail / 15 min), 80, 150, 300, 500, 1000 puis plafond (protege la delivrabilite).'],
  ['MFE_HEURES_ENVOI', '8-19', 'MarketForge Engine — plage horaire d\'envoi (heure du script), mails repartis sur la plage.'],
  ['MFE_EMAIL_TEST', '', 'MarketForge Engine — MODE TEST : si une adresse est saisie ici, TOUS les mails partent vers elle (objet prefixe [TEST]) et les prospects restent "Pret". Vider la case pour passer en reel.'],
  ['MFE_MAX_REBONDS', '3', 'MarketForge Engine — au-dela de N mails bloques/rebonds sur 3 jours, l\'envoi automatique se met en pause (MFE_ENVOI_AUTO passe a FALSE).'],
  ['MFE_AB_ACTIF', 'TRUE', 'MarketForge Engine — TRUE = test A/B du CTA (chaque mail recoit une variante, la repartition suit les resultats). FALSE = toujours la variante A.'],
  ['MFE_RELANCE_JOURS', '4', 'MarketForge Engine — relance unique apres N jours sans reponse (0 = pas de relance).'],
  ['MFE_RELANCE_DEPUIS', '02/10/2026', 'MarketForge Engine — les relances ne concernent que les prospects dont le 1er mail est parti a partir de cette date (JJ/MM/AAAA). Les prospects de l\'ancien mail ne sont jamais relances. Vide = tous.'],
];

// ---------- Messages (modifiables dans l'onglet Reglages, cles MFE_MSG_*) ----------
// Style : court, a la premiere personne, une seule question, texte brut (pas de gras, pas d'emoji).
// Variables : {PODCAST} {URL} {BOOKING} {OPTOUT}
var MFE_MSG_VERSION = '19';   // incremente -> les textes MFE_MSG_* de Reglages sont remis a jour a l'installation
var MFE_FIRST_MAIL = [
  'Hello,',
  '',
  'I\'m Etienne, founder of <strong>Listenly, the first AI search engine dedicated to B2B podcasts.</strong>',
  '',
  'We currently <u>index the questions and answers contained in all B2B podcasts</u> so they can appear in responses from <strong>ChatGPT, Gemini and Claude.</strong>',
  '',
  'For example, one query from your latest episode:<br><br><em>{QUERY}</em>',
  '\u2192 <a href="{QUERY_LINK}">Now discoverable by executives searching for this topic</a>',
  '',
  'Where would you like us to redirect this traffic?',
  '<strong>Have you got a Spotify page or a dedicated Podcast Hub?</strong>',
  '',
  'Best,',
  'Etienne'
].join('\n');
// Test A/B du CTA (03/10/2026) : 5 variantes A-E, une seule par envoi. Texte brut (aucun gras / souligne dans les CTA).
var MFE_CTAS = {
  A: 'Do you already have a Podcast Hub, or should we keep Spotify as the destination?',
  B: 'Do you already have a Podcast Hub, or should we redirect it to Spotify for now?',
  C: 'Should we send it to Spotify, or do you already have a Podcast Hub?',
  D: 'Do you have a Podcast Hub where we can send this audience?',
  E: 'Do you already have a Podcast Hub to receive it?'
};
var MFE_AB_KEYS = ['A', 'B', 'C', 'D', 'E'];
var MFE_AB_DEPUIS = new Date(2026, 9, 4).getTime();   // seuls les envois a partir du 04/10/2026 (nouveau mail) comptent dans le test A-E
var MFE_MSG_RESET = ['MFE_MSG_OBJET', 'MFE_MSG_FICHE', 'MFE_MSG_REPONSES', 'MFE_MSG_RELANCE', 'MFE_MSG_RELANCE_2', 'MFE_MSG_RELANCE_3', 'MFE_CTA_A', 'MFE_CTA_B', 'MFE_CTA_C', 'MFE_CTA_D', 'MFE_CTA_E'];   // v13 : seuls ces textes sont reecrits dans Reglages (le reste est conserve)
var MFE_MSG_DEFAULTS = [
  ['MFE_MSG_OBJET', 'Regarding {PODCAST} | Listenly indexing',
   'MarketForge Engine — objet du 1er mail. {PODCAST} = nom du podcast.'],
  ['MFE_MSG_FICHE', MFE_FIRST_MAIL,
   'MarketForge Engine — 1er mail. Variables : {NAME} (hote, sinon "{PODCAST} team") {PODCAST} {URL} (fiche N1 du podcast) {BOOKING} {OPTOUT}.'],
  ['MFE_MSG_REPONSES', MFE_FIRST_MAIL,
   'MarketForge Engine — 1er mail quand des reponses ont ete extraites (meme modele par defaut).'],
  ['MFE_MSG_RELANCE', [
    '{HELLO}',
    '',
    'I contacted you a few days ago regarding {PODCAST}.',
    '',
    'We’re currently indexing <strong>your podcast on Listenly, our AI search engine for podcasts</strong>, so the questions from your episodes can be <strong>visible, cited and recommended by ChatGPT, Gemini and Claude.</strong>',
    '',
    '<a bold href="{QUERY_LINK}">→ Here’s one query from your latest episode</a>',
    '',
    'Where would you like us to redirect <strong>the people who discover you through these queries?</strong>',
    '',
    'Best,',
    'Etienne'
  ].join('\n'), 'MarketForge Engine — relance 1 (J+4, BENEFICE), dans le meme fil. Variables : {HELLO} (Hello Prenom, / Hello,) {PODCAST} {QUERY_LINK}.'],
  ['MFE_MSG_RELANCE_2', [
    '{HELLO}',
    '',
    'Just following up on my previous message regarding {PODCAST}.',
    '',
    'We’re indexing <strong>your podcast on Listenly, our AI search engine for podcasts</strong>, so its questions can be <strong>cited and recommended by AI search engines.</strong>',
    '',
    '<a bold href="{QUERY_LINK}">→ Here’s one query from your latest episode</a>',
    '',
    'Without a destination from your side, this traffic may stay on Listenly or be sent to <u>a platform you don’t control.</u>',
    '',
    '<strong>Where should we redirect it?</strong>',
    '',
    'Best,',
    'Etienne'
  ].join('\n'), 'MarketForge Engine — relance 2 (J+8, PERTE / CONTROLE), dans le meme fil. Variables : {HELLO} {PODCAST} {QUERY_LINK}.'],
  ['MFE_MSG_RELANCE_3', [
    '{HELLO}',
    '',
    'I’m following up one last time regarding {PODCAST}.',
    '',
    'We’re finalizing the indexing of <strong>your podcast on Listenly</strong>, so its content can be <strong>cited and recommended by ChatGPT, Gemini and Claude.</strong>',
    '',
    'We’re <u>finalizing this now.</u>',
    '',
    '<strong>If you want this traffic redirected somewhere specific, just send me the link.</strong>',
    '',
    'Best,',
    'Etienne'
  ].join('\n'), 'MarketForge Engine — relance 3 (J+12, URGENCE, sans lien), dans le meme fil. Variables : {HELLO} {PODCAST}.'],
  ['MFE_CTA_A', MFE_CTAS.A, 'Test A/B — CTA variante A (texte brut ; vide = variante desactivee).'],
  ['MFE_CTA_B', MFE_CTAS.B, 'Test A/B — CTA variante B (texte brut ; vide = variante desactivee).'],
  ['MFE_CTA_C', MFE_CTAS.C, 'Test A/B — CTA variante C (texte brut ; vide = variante desactivee).'],
  ['MFE_CTA_D', MFE_CTAS.D, 'Test A/B — CTA variante D (texte brut ; vide = variante desactivee).'],
  ['MFE_CTA_E', MFE_CTAS.E, 'Test A/B — CTA variante E (texte brut ; vide = variante desactivee).'],
  ['MFE_MSG_SIGNATURE', '',
   'MarketForge Engine — lignes ajoutees automatiquement a la fin du 1er mail ET de la relance (ex. lien LinkedIn). Vide = rien. Gmail n\'ajoute PAS la signature Workspace aux mails envoyes par script.'],
  ['MFE_VERIF_CLE', '', 'Cle API MyEmailVerifier (verification des boites mail avant envoi). Vide = verification desactivee.'],
  ['MFE_VERIF_RISQUES', 'FALSE', 'Verification des emails : TRUE = envoie aussi aux adresses "Catch All" (domaine qui accepte tout, non verifiable). FALSE = uniquement les adresses confirmees (plus sur).'],
  ['MFE_RAPPORT', 'QUOTIDIEN', 'Rapport par email (HTML) : QUOTIDIEN (1 par jour a MFE_RAPPORT_HEURE), HORAIRE (chaque heure de 8h a 20h) ou OFF.'],
  ['MFE_RAPPORT_HEURE', '20', 'Heure d\'envoi du rapport quotidien (0-23).'],
  ['MFE_RAPPORT_EMAIL', '', 'Destinataire du rapport. Vide = toi (compte qui execute le script).'],
  ['MFE_SIG_HTML', 'TRUE', 'Signature riche (photo + liens) en bas des mails. TRUE = activee. Garder FALSE si la delivrabilite baisse.'],
  ['MFE_SIG_PHOTO', 'https://listenly.fr/podcast-btb/assets/etienne-cugnet.jpg', 'Signature riche — URL publique de ta photo (carree, ~200x200). Vide = pas de photo.'],
  ['MFE_SIG_NOM', 'Etienne Cugnet', 'Signature riche — nom.'],
  ['MFE_SIG_TITRE', 'Founder, Listenly & Marketforge', 'Signature riche — titre / entreprise.'],
  ['MFE_SIG_ACCROCHE', 'Turning B2B podcasts into Google & AI visibility', 'Signature riche — une ligne "qui je suis". Vide = rien.'],
  ['MFE_SIG_EMAIL', 'etienne.cugnet@marketforge.fr', 'Signature riche — email affiche.'],
  ['MFE_SIG_SITE', 'Marketforge|https://marketforge.fr/', 'Signature riche — site : "Texte affiche|URL" (ou juste l\'URL). Vide = rien.'],
  ['MFE_SIG_LINKEDIN', 'https://www.linkedin.com/in/etienne-cugnet-709032399/', 'Signature riche — URL complete du profil LinkedIn. Vide = rien.'],
  ['MFE_SIG_TEL', '', 'Signature riche — telephone. Vide = rien.'],
  ['MFE_MSG_OPTOUT', "If this isn't relevant, just let me know and I won't reach out again.",
   'MarketForge Engine — phrase inseree a la place de {OPTOUT} (si utilisee dans un texte).'],
];

function mfeMsg_(key) {
  var v = mfeReadSettings_()[key];
  if (v != null && String(v).trim()) return String(v);
  for (var i = 0; i < MFE_MSG_DEFAULTS.length; i++) if (MFE_MSG_DEFAULTS[i][0] === key) return MFE_MSG_DEFAULTS[i][1];
  return '';
}

function installer() {
  var sh = mfeSheet_();
  sh.getRange(MFE.HEADER_ROW, 1, 1, MFE.COLS.length).setValues([MFE.COLS]).setFontWeight('bold').setBackground('#eef3fd');   // ajoute la colonne Variante CTA
  sh.getRange(MFE.HEADER_ROW, MFE.COLS.length + 1, 1, 5).clearContent().clearFormat();   // nettoie les en-tetes en trop (ancienne v16 a 20 colonnes)
  mfeMigrateOldSettings_(sh);
  mfeEnsureSettings_();
  mfeHisto_();
  var props = PropertiesService.getScriptProperties();
  if (!props.getProperty('MFE_SECRET')) props.setProperty('MFE_SECRET', Utilities.getUuid().replace(/-/g, ''));
  Logger.log('SECRET du pont GitHub : %s  -> ajoute "?secret=%s" a la fin de l\'URL de l\'application web.',
             props.getProperty('MFE_SECRET'), props.getProperty('MFE_SECRET'));
  ScriptApp.getProjectTriggers().forEach(function (t) {
    var f = t.getHandlerFunction();
    if (f === 'marketforgeEngineQuotidien' || f === 'marketforgeEngineEnvoi' || f === 'mfeOnOpen') ScriptApp.deleteTrigger(t);
  });
  // Menu "MarketForge Engine" : declencheur d'ouverture installable (ne remplace pas l'onOpen existant)
  ScriptApp.newTrigger('mfeOnOpen').forSpreadsheet(mfeSS_()).onOpen().create();
  mfeOnOpen();
  // Toutes les heures : les prospects arrivent dans le tableau au plus 1 h apres chaque run GitHub
  // (instantanement si le pont application web est branche). Le plafond d'envois reste journalier.
  ScriptApp.newTrigger('marketforgeEngineQuotidien').timeBased().everyHours(1).create();
  // Envoi seul, toutes les 15 min : 1 mail par creneau (au lieu d'une rafale a chaque heure pleine)
  ScriptApp.newTrigger('marketforgeEngineEnvoi').timeBased().everyMinutes(15).create();
  marketforgeEngineQuotidien();
}

// Envoi cadence : appele toutes les 15 min. Ne fait QUE l'envoi des premiers mails
// (le plafond du jour est reparti par creneaux de 15 min sur la plage horaire).
function marketforgeEngineEnvoi() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) return;   // le traitement horaire tourne : ce creneau sera rattrape au suivant
  try {
    var cfg = mfeSettings_();
    if (!cfg.ENVOI_AUTO || cfg.EMAIL_TEST) return;
    mfeSend_(mfeSheet_(), cfg);
  } finally {
    lock.releaseLock();
  }
}

function marketforgeEngineQuotidien() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(60000)) return;
  try { mfeQuotidien_(); } finally { lock.releaseLock(); }
}

function mfeQuotidien_() {
  var sh = mfeSheet_();
  var cfg = mfeSettings_();
  var added = mfeImport_(sh, null);
  if (cfg.EMAIL_TEST) {  // mode test : ne touche ni aux statuts ni au quota
    Logger.log('MODE TEST : %s mail(s) test envoye(s) a %s', mfeSendTest_(sh, cfg.EMAIL_TEST), cfg.EMAIL_TEST);
    return;
  }
  var sent = 0;   // l'envoi des premiers mails est fait par marketforgeEngineEnvoi (toutes les 15 min)
  var replies = mfeCheckReplies_(sh);
  var relances = (cfg.ENVOI_AUTO && cfg.RELANCE_JOURS > 0) ? mfeFollowUp_(sh, cfg.RELANCE_JOURS) : 0;
  Logger.log('MarketForge Engine : %s ajoute(s), %s envoye(s), %s reponse(s), %s relance(s)', added, sent, replies, relances);
  try { mfeRapportSiPrevu_(); } catch (e) { Logger.log('Rapport : %s', e); }
}

// ---------- 1. Import depuis queue.json ----------
function mfeImport_(sh, podcasts) {
  if (!podcasts) {
    var res = UrlFetchApp.fetch(MFE.QUEUE_URL + '?t=' + Date.now(), { muteHttpExceptions: true });
    if (res.getResponseCode() !== 200) throw new Error('queue.json illisible : HTTP ' + res.getResponseCode());
    podcasts = (JSON.parse(res.getContentText()).podcasts) || {};
  }
  var known = {};
  mfeRows_(sh).forEach(function (r) { known[r.values[0]] = true; });
  var rows = [];
  var prospection = mfeSS_().getSheetByName('Prospection');
  Object.keys(podcasts).forEach(function (slug) {
    var p = podcasts[slug];
    if (known[slug] || !p.email || !p.proof_url) return;
    if (mfeEmailProblem_(p.email)) return;   // anti-rebond : jamais importe si l'adresse est douteuse
    var n = p.moments_count || 0;
    // Jamais de double contact : email deja present dans l'onglet Prospection (ancienne machine)
    var dejaVu = prospection && prospection.createTextFinder(p.email).matchCase(false).findNext();
    rows.push([slug, p.podcast_name || slug, p.email, p.proof_url + (n > 0 ? '#answers' : ''), n,
               new Date(), dejaVu ? 'Deja en prospection' : 'Pret', '', '', '', '', '',
               p.listenly_url || '', p.host_name || '', '', p.thematique || '',
               p.latest_episode_question || '', p.latest_episode_moment_id || '']);
  });
  if (rows.length) sh.getRange(sh.getLastRow() + 1, 1, rows.length, MFE.COLS.length).setValues(rows);
  return rows.length;
}

// ---------- 2. Premier mail ----------
// Plafond du jour selon la montee progressive (semaines depuis le 1er envoi)
function mfeDailyCap_(cfg) {
  if (!cfg.MONTEE) return cfg.MAX_ENVOIS_JOUR;
  var props = PropertiesService.getScriptProperties();
  var start = props.getProperty('MFE_START');
  if (!start) { start = String(Date.now()); props.setProperty('MFE_START', start); }
  var week = Math.floor((Date.now() - Number(start)) / (7 * 86400000));
  var steps = [44, 80, 150, 300, 500, 1000];   // 44/j = 1 mail toutes les 15 min sur 8h-19h
  return Math.min(cfg.MAX_ENVOIS_JOUR, week < steps.length ? steps[week] : cfg.MAX_ENVOIS_JOUR);
}

function mfeSend_(sh, cfg, force, onlySlug) {   // onlySlug (optionnel) : n'envoie qu'a ce podcast
  var now = new Date(), h = now.getHours(), min = now.getMinutes();
  if (!force && (h < cfg.H_START || h >= cfg.H_END)) return 0;   // hors plage horaire
  var daily = mfeDailyCap_(cfg);
  var today = now.toDateString();
  var rows = mfeRows_(sh);
  var sentToday = rows.filter(function (r) {
    return r.values[7] && new Date(r.values[7]).toDateString() === today;
  }).length;
  // Repartition sur la plage : a l'heure h, on ne depasse pas la part proportionnelle du jour
  // (creneaux de 15 min : a 44/j, exactement 1 mail par quart d'heure)
  var slots = (cfg.H_END - cfg.H_START) * 4;
  var slot = (h - cfg.H_START) * 4 + Math.floor(min / 15) + 1;
  var allowedSoFar = Math.ceil(daily * slot / slots);
  var budget = Math.max(0, Math.min(daily, allowedSoFar) - sentToday);
  if (force) budget = force === true ? Math.max(0, daily - sentToday) : Math.min(force, Math.max(0, daily - sentToday));
  var sent = 0;
  var ab = mfeAbPlan_(rows, cfg);
  rows.forEach(function (r) {
    if (sent >= budget || r.values[6] !== 'Pret') return;
    if (onlySlug && r.values[0] !== onlySlug) return;
    if (!r.values[16]) return;   // pas de question reelle du podcast -> pas de mail (l'exemple est obligatoire)
    var why = mfeEmailProblem_(r.values[2]);   // anti-rebond : verifie l'adresse juste avant l'envoi
    if (why) {
      sh.getRange(r.row, 7).setValue('Email invalide');
      sh.getRange(r.row, 12).setValue('Non envoye (anti-rebond) : ' + why);
      return;
    }
    var verif = mfeVerifyMailbox_(r.values[2]);   // boite mail reellement existante ? (MyEmailVerifier)
    if (verif.stop) {
      sh.getRange(r.row, 7).setValue(verif.status);
      sh.getRange(r.row, 12).setValue('Non envoye (verification) : ' + verif.why);
      return;
    }
    var variant = mfeAbPick_(ab);
    var d = mfeDraft_(r.values, variant);
    try {
      var threadId = mfeMail_(r.values[2], d[0], d[1]);
      sh.getRange(r.row, 7, 1, 5).setValues([['Envoye', new Date(), '', '', threadId]]);
      sh.getRange(r.row, 15).setValue(variant);
      ab.counts[variant]++; ab.total++;
      sent++;
    } catch (e) {
      sh.getRange(r.row, 7).setValue('Erreur');
      sh.getRange(r.row, 12).setValue(String(e).slice(0, 200));
    }
  });
  return sent;
}

// Mode test : 1 exemplaire de chaque type de mail (fiche seule / avec reponses) vers l'adresse test
function mfeSendTest_(sh, to) {
  var props = PropertiesService.getScriptProperties();
  if (props.getProperty('MFE_TEST_DONE') === to + '|' + MFE_MSG_VERSION) return 0;   // une seule fois par adresse test et par version des textes
  var n = 0, done = {}, variants = ['A'];
  mfeRows_(sh).forEach(function (r) {
    var kind = Number(r.values[4]) > 0 ? 'reponses' : 'fiche';
    if (done[kind] || r.values[6] !== 'Pret') return;
    variants.forEach(function (vr) {
      if (!mfeMsg_('MFE_CTA_' + vr)) return;
      var d = mfeDraft_(r.values, vr);
      var tb = '(Mail qui partirait a : ' + r.values[2] + ' \u2014 variante CTA ' + vr + ')\n\n' + d[1];
      GmailApp.sendEmail(to, '[TEST ' + vr + '] ' + d[0], mfeWithSignature_(tb), mfeSendOpts_(tb));
      n++;
    });
    done[kind] = true;
  });
  props.setProperty('MFE_TEST_DONE', to + '|' + MFE_MSG_VERSION);
  return n;
}

// ---------- 3. Reponses + relance ----------
function mfeCheckReplies_(sh) {
  var n = 0;
  mfeRows_(sh).forEach(function (r) {
    var status = r.values[6], threadId = r.values[10];
    if (!threadId || (status !== 'Envoye' && status !== 'Relance' && status !== 'Relance 2' && status !== 'Relance 3')) return;
    var thread = GmailApp.getThreadById(threadId);
    if (!thread) return;
    var msgs = thread.getMessages();
    // Rebond = avis d'echec DEFINITIF (pas les avis "Delay" / probleme temporaire, Gmail reessaie seul)
    var bounce = msgs.some(function (m) {
      if (!/mailer-daemon|postmaster|mail delivery/i.test(m.getFrom())) return false;
      var txt = m.getSubject() + ' ' + m.getPlainBody().slice(0, 600);
      return !/\(Delay\)|delayed|temporaire|temporary|will retry|vont \u00eatre effectu/i.test(txt);
    });
    // Avis de RETARD (probleme temporaire, Gmail reessaie seul) : on n'insiste pas. Adresse marquee "Email instable",
    // jamais relancee (une relance = une tentative de plus vers une adresse qui ne repond pas).
    var delayed = msgs.some(function (m) {
      return /mailer-daemon|postmaster|mail delivery/i.test(m.getFrom());
    });
    if (!bounce && delayed) {
      sh.getRange(r.row, 7).setValue('Email instable');
      mfeRememberBounce_(r.values[2]);
      sh.getRange(r.row, 12).setValue('Avis de retard de livraison : pas de relance, adresse ecartee');
      return;
    }
    if (bounce) {  // mail bloque / adresse invalide : jamais de relance
      sh.getRange(r.row, 7).setValue('Rebond');
      mfeRememberBounce_(r.values[2]);
      sh.getRange(r.row, 12).setValue('Bloque ou refuse par le serveur du destinataire');
      mfeBounceGuard_(sh);
      return;
    }
    // Reponse HUMAINE seulement : on ignore les reponses automatiques (absence, accuse de reception)
    var firstSent = null;
    msgs.forEach(function (m) { if (!firstSent && !/mailer-daemon|postmaster/i.test(m.getFrom()) && m.getFrom().toLowerCase().indexOf(String(r.values[2]).toLowerCase()) === -1) firstSent = m; });
    var fromThem = msgs.some(function (m) {
      if (m.getFrom().toLowerCase().indexOf(String(r.values[2]).toLowerCase()) === -1) return false;
      var subj = m.getSubject() || '', head = m.getPlainBody().slice(0, 300);
      if (/automatic reply|auto-?reply|autoreply|out of office|r\u00e9ponse automatique|absence|away from/i.test(subj)) return false;
      if (/^\s*(hi there!?\s*)?(thank(s| you) (so much )?for (reaching|contacting|your (email|message))|this is an automated|this is an auto)/i.test(head)) return false;
      if (firstSent && (m.getDate().getTime() - firstSent.getDate().getTime()) < 120000) return false;   // repond en moins de 2 min = robot
      return true;
    });
    if (fromThem) { sh.getRange(r.row, 7).setValue('Repondu'); sh.getRange(r.row, 10).setValue(new Date()); n++; }
  });
  return n;
}

// ---------- Anti-rebond : verification de l'adresse avant chaque envoi ----------
var MFE_BLOCKED_DOMAINS = ['anchor.fm', 'spotify.com', 'spreaker.com', 'libsyn.com', 'megaphone.fm', 'buzzsprout.com',
  'podbean.com', 'simplecast.com', 'transistor.fm', 'captivate.fm', 'acast.com', 'omny.fm', 'omnystudio.com',
  'soundcloud.com', 'iheart.com', 'iheartmedia.com', 'audioboom.com', 'redcircle.com', 'art19.com', 'pinecast.com',
  'blubrry.com', 'podcastics.com', 'ausha.co', 'podomatic.com', 'castos.com', 'fireside.fm', 'podigee.com',
  'riverside.fm', 'zencast.fm', 'whooshkaa.com', 'appbind.com', 'rss.com', 'podcastpage.io', 'example.com', 'example.org', 'test.com', 'domain.com', 'email.com'];
var MFE_BLOCKED_LOCAL = /^(no-?reply|do-?not-?reply|noreply\d*|feeds?|rss|bounces?|postmaster|mailer-daemon|abuse|dmca|copyright|unsubscribe|privacy|legal|billing|invoices?|accounting|applepodcasts?|itunes|podcasts?\d+(\+.*)?)$/;

// '' si l'adresse est envoyable, sinon la raison
function mfeEmailProblem_(email) {
  email = String(email || '').trim().toLowerCase();
  if (!/^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$/.test(email)) return 'format invalide';
  var local = email.split('@')[0], domain = email.split('@')[1];
  for (var i = 0; i < MFE_BLOCKED_DOMAINS.length; i++) {
    var d = MFE_BLOCKED_DOMAINS[i];
    if (domain === d || domain.slice(-d.length - 1) === '.' + d) return 'adresse d\'hebergeur (' + domain + ')';
  }
  if (MFE_BLOCKED_LOCAL.test(local.split('+')[0]) || MFE_BLOCKED_LOCAL.test(local)) return 'boite technique (' + local + '@)';
  if (/(anchor|libsyn|audioboom|spreaker|megaphone|buzzsprout|podbean|simplecast|soundcloud|acast|omny|redcircle)/.test(local)) return 'adresse de plateforme (' + local + '@)';
  var bounced = JSON.parse(PropertiesService.getScriptProperties().getProperty('MFE_BOUNCED_DOMAINS') || '{}');
  var perso = /^(gmail|googlemail|yahoo|outlook|hotmail|live|icloud|me|aol|proton|protonmail)\./;
  if (bounced[domain] && !perso.test(domain)) return 'domaine deja en rebond (' + domain + ')';
  if (!mfeDomainAcceptsMail_(domain)) return 'domaine sans serveur mail (' + domain + ')';
  return '';
}

// ---------- Verification de la boite mail (MyEmailVerifier, API temps reel, 100 gratuites / jour) ----------
// Cle stockee dans le script (menu > Enregistrer la cle MyEmailVerifier), jamais dans le tableau.
// Status : Valid -> envoi | Invalid ou domaine jetable -> "Email invalide" | Catch All / Unknown / Grey-listed
// -> "Email risque" (Catch All envoye seulement si MFE_VERIF_RISQUES = TRUE).
// Sans cle, quota epuise ou API indisponible : regles seules (aucun blocage de l'envoi).
function mfeVerifyMailbox_(email) {
  var key = PropertiesService.getScriptProperties().getProperty('MFE_MEV_KEY') ||
            String(mfeReadSettings_().MFE_VERIF_CLE || '').trim();   // menu (prioritaire) ou onglet Reglages
  if (!key) return { stop: false };
  email = String(email).trim().toLowerCase();
  var cache = CacheService.getScriptCache(), ck = 'mev_' + Utilities.base64EncodeWebSafe(email).slice(0, 200);
  var st = cache.get(ck);
  if (!st) {
    try {
      var r = UrlFetchApp.fetch('https://api.myemailverifier.com/api/validate_single.php?apikey=' + encodeURIComponent(key) +
        '&email=' + encodeURIComponent(email), { muteHttpExceptions: true });
      var d = JSON.parse(r.getContentText() || '{}');
      if (!d.Status) { Logger.log('MyEmailVerifier : %s', r.getContentText().slice(0, 200)); return { stop: false }; }
      st = String(d.Status).toLowerCase().replace(/[\s_-]+/g, '');
      if (String(d.Disposable_Domain).toLowerCase() === 'true') st = 'disposable';
      cache.put(ck, st, 21600);
    } catch (e) { Logger.log('MyEmailVerifier indisponible : %s', e); return { stop: false }; }
  }
  if (st === 'valid') return { stop: false };
  if (st === 'invalid' || st === 'disposable') return { stop: true, status: 'Email invalide', why: 'boite inexistante (' + st + ')' };
  var risques = String(mfeReadSettings_().MFE_VERIF_RISQUES).toUpperCase() === 'TRUE';
  if (risques && st === 'catchall') return { stop: false };
  return { stop: true, status: 'Email risque', why: 'non verifiable (' + st + ')' };
}

function mfeMenuVerifKey() {
  var ui = mfeUi_();
  var r = ui.prompt('Cle API MyEmailVerifier', 'Colle ta cle API (myemailverifier.com > API). Stockee dans le script, jamais dans le tableau. Laisser vide + OK = desactiver la verification.', ui.ButtonSet.OK_CANCEL);
  if (r.getSelectedButton() !== ui.Button.OK) return;
  var k = r.getResponseText().trim(), props = PropertiesService.getScriptProperties();
  if (!k) { props.deleteProperty('MFE_MEV_KEY'); mfeAlert_('Verification des emails desactivee.'); return; }
  props.setProperty('MFE_MEV_KEY', k);
  var test = UrlFetchApp.fetch('https://client.myemailverifier.com/verifier/getcredits/' + encodeURIComponent(k), { muteHttpExceptions: true }).getContentText();
  mfeAlert_('Cle enregistree. Credits MyEmailVerifier : ' + test.slice(0, 200) + '\nChaque adresse est desormais verifiee juste avant l\'envoi.');
}

// Le domaine a-t-il un serveur mail (MX, a defaut une IP) ? DNS-over-HTTPS Google, cache 6 h. Doute -> oui.
function mfeDomainAcceptsMail_(domain) {
  var cache = CacheService.getScriptCache(), key = 'mx_' + domain, hit = cache.get(key);
  if (hit) return hit === '1';
  var ok = true;
  try {
    var types = ['MX', 'A'];
    for (var i = 0; i < types.length; i++) {
      var res = UrlFetchApp.fetch('https://dns.google/resolve?name=' + encodeURIComponent(domain) + '&type=' + types[i], { muteHttpExceptions: true });
      if (res.getResponseCode() !== 200) { ok = true; break; }
      var d = JSON.parse(res.getContentText());
      if (d.Status === 3) { ok = false; break; }                       // le domaine n'existe pas
      if ((d.Answer || []).some(function (a) { return a.type === 15 || a.type === 1; })) { ok = true; break; }
      ok = false;
    }
  } catch (e) { ok = true; }
  cache.put(key, ok ? '1' : '0', 21600);
  return ok;
}

// Memorise les domaines qui ont rebondi (on n'y renvoie plus rien, sauf messageries perso)
function mfeRememberBounce_(email) {
  var domain = String(email || '').toLowerCase().split('@')[1];
  if (!domain) return;
  var props = PropertiesService.getScriptProperties();
  var bounced = JSON.parse(props.getProperty('MFE_BOUNCED_DOMAINS') || '{}');
  bounced[domain] = new Date().toISOString().slice(0, 10);
  props.setProperty('MFE_BOUNCED_DOMAINS', JSON.stringify(bounced));
}

// Trop de rebonds recents -> pause de l'envoi (protege la reputation du domaine).
// Regle : sur 3 jours, pause si rebonds >= MFE_MAX_REBONDS ET taux de rebond > 3 % des envois.
function mfeBounceGuard_(sh) {
  var max = parseInt(mfeReadSettings_().MFE_MAX_REBONDS, 10) || 3;
  var since = Date.now() - 3 * 86400000;
  var recent = mfeRows_(sh).filter(function (r) { return r.values[7] && new Date(r.values[7]).getTime() > since; });
  var n = recent.filter(function (r) { return r.values[6] === 'Rebond'; }).length;
  var rate = recent.length ? n / recent.length : 0;
  Logger.log('Rebonds 3 jours : %s / %s envois (%s %)', n, recent.length, Math.round(rate * 1000) / 10);
  if (n < max || rate <= 0.03) return;
  var reg = mfeReglagesSheet_(), vals = reg.getRange(1, 1, reg.getLastRow(), 1).getValues();
  for (var i = 0; i < vals.length; i++) if (String(vals[i][0]).trim() === 'MFE_ENVOI_AUTO') reg.getRange(i + 1, 2).setValue('FALSE');
  Logger.log('PAUSE AUTO : %s rebonds en 3 jours -> MFE_ENVOI_AUTO = FALSE', n);
}

// 3 relances dans le meme fil : J+N, J+2N, J+3N apres le 1er mail (N = MFE_RELANCE_JOURS = 4 -> J+4, J+8, J+12).
// Statut : Envoye -> Relance (R1) -> Relance 2 (R2) -> Relance 3 (R3). Colonnes inchangees ("Relance le" = date de la derniere relance).
// Un prospect Repondu / Rebond / Email instable n'est plus relance (detecte par mfeCheckReplies_ + garde-fou ci-dessous).
function mfeFollowUp_(sh, days) {
  var n = 0, now = Date.now(), DAY = 86400000;
  var stages = { 'Envoye': ['MFE_MSG_RELANCE', 'Relance', 1], 'Relance': ['MFE_MSG_RELANCE_2', 'Relance 2', 2], 'Relance 2': ['MFE_MSG_RELANCE_3', 'Relance 3', 3] };
  // Relances reservees aux prospects dont le 1er mail est parti a partir de MFE_RELANCE_DEPUIS (JJ/MM/AAAA)
  var since = null, depuis = mfeReadSettings_().MFE_RELANCE_DEPUIS;
  if (depuis instanceof Date) since = new Date(depuis.getFullYear(), depuis.getMonth(), depuis.getDate()).getTime();
  else {
    var m = String(depuis || '').trim().match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (m) since = new Date(+m[3], +m[2] - 1, +m[1]).getTime();
  }
  mfeRows_(sh).forEach(function (r) {
    var st = stages[r.values[6]];
    if (!st || !r.values[7] || !r.values[10]) return;
    var sentAt = new Date(r.values[7]).getTime();
    if (sentAt > now - st[2] * days * DAY) return;                                            // pas encore l'heure de cette relance
    if (r.values[8] && now - new Date(r.values[8]).getTime() < days * DAY) return;           // jamais 2 relances rapprochees
    if (since && sentAt < since) return;
    var thread = GmailApp.getThreadById(r.values[10]);
    if (!thread) return;
    // Securite : jamais de relance si un avis d'echec ou de retard est deja arrive dans le fil
    if (thread.getMessages().some(function (m) { return /mailer-daemon|postmaster|mail delivery/i.test(m.getFrom()); })) {
      sh.getRange(r.row, 7).setValue('Email instable');
      sh.getRange(r.row, 12).setValue('Avis de livraison recu : pas de relance');
      return;
    }
    if (st[2] < 3 && !(r.values[16] && r.values[17])) return;   // relances 1 et 2 : jamais sans vraie question + moment horodate (pas de lien generique)
    var rel = mfeFill_(mfeMsg_(st[0]), mfeVars_(r.values));
    thread.replyAll(mfeWithSignature_(rel), mfeSendOpts_(rel));
    sh.getRange(r.row, 7).setValue(st[1]);
    sh.getRange(r.row, 9).setValue(new Date());
    n++;
  });
  return n;
}

// ---------- Utilitaires ----------
function mfeMail_(to, subject, body) {
  GmailApp.sendEmail(to, subject, mfeWithSignature_(body), mfeSendOpts_(body));
  Utilities.sleep(1500);
  var threads = GmailApp.search('to:' + to + ' subject:"' + subject.replace(/"/g, '') + '" in:sent', 0, 1);
  return threads.length ? threads[0].getId() : '';
}

function mfeFromOpts_() {
  var opts = { name: MFE.NAME, replyTo: MFE.FROM };
  if (GmailApp.getAliases().indexOf(MFE.FROM) !== -1) opts.from = MFE.FROM;
  return opts;
}

// "Hi Tom Bevington" si l'hote ressemble a une personne, sinon "Hi a16z crypto team" / "Hi {PODCAST} team"
function mfeName_(host, podcast) {
  host = String(host || '').trim();
  var corporate = /\b(podcast|media|inc|llc|ltd|team|studio|studios|network|group|the|and|co|company|agency|productions?|radio|news|show|hq|talks?|air|county|city|welle|horowitz|capital|partners|ventures|digital|labs?|consulting|training|institute|association|foundation|university|college|club|collective|academy|leadership|magazine|journal|press|publishing|tv|fm|live|daily|weekly|global|international|solutions|systems|advisors?|associates|editorial|reporters|producers|business|marketing|finance|energy|real|estate|insider|brief|review|books?|stories|world|america|europe|asia|japan|africa|official|channel|pod|cast|hub|lab|works|works)\b|&|\d/i;
  var words = host.split(/\s+/);
  if (host && words.length >= 2 && words.length <= 3 && !corporate.test(host) &&
      words.every(function (w) { return /^[A-ZÀ-Ý][a-zà-ÿ'’.-]+$/.test(w); })) return words[0];  // prenom seul : "Hi Greg,"
  if (host && /\bteam\b/i.test(host)) return host;
  return (podcast || 'there') + ' team';
}

// Prenom valide de l'hote, sinon '' (jamais de nom de podcast, jamais d'espace / undefined / null / N/A / placeholder)
function mfeFirstName_(host) {
  host = String(host == null ? '' : host).trim();
  if (!host || /^(undefined|null|n\/?a|none|nan|unknown|tbd|-+|\?+)$/i.test(host) || /undefined|null|n\/a|[{}@]|http/i.test(host)) return '';
  var words = host.split(/\s+/), first = mfeName_(host, '');   // mfeName_ renvoie le prenom seul si l'hote ressemble a une personne
  return (words.length >= 2 && first === words[0]) ? first : '';
}
function mfeHello_(host) { var n = mfeFirstName_(host); return n ? 'Hello ' + n + ',' : 'Hello,'; }

// "BriteVibe Podcast: Live Brite, Live Bold..." -> "BriteVibe Podcast"
function mfeShortName_(name) {
  var full = String(name || '').trim();
  var cut = full.split(/\s*[:|–—]\s*|\s+-\s+|\s*\(/)[0].trim();
  if (cut.length < 3) cut = full;
  return cut.length > 60 ? cut.slice(0, 60).replace(/\s+\S*$/, '') : cut;
}

function mfeVars_(values) {
  // QUERY_LINK : lien Listenly avec moment ID si disponible (dernier épisode question + moment ID aux colonnes 16, 17)
  // Sinon : lien générique vers la page Listenly du podcast
  var queryLink = 'https://listenly.fr/podcast/show/' + values[0];  // par défaut : page du podcast
  if (values[16] && values[17]) {  // si question + moment_id disponibles
    queryLink = 'https://listenly.fr/?p=' + values[0] + '&m=' + values[17];
  }
  // QUERY_BLOCK : la question reelle juste au-dessus du lien Listenly horodate ("question \n-> lien"); sans question, le lien seul
  var question = String(values[16] || '').trim();
  var queryBlock = (question && values[17]) ? question + '\n→ ' + queryLink : queryLink;
  return { PODCAST: mfeShortName_(values[1]), URL: values[3], LINK: values[3], LISTENLY: values[12] || values[3],
           QUERY_LINK: queryLink, QUERY_BLOCK: queryBlock, QUERY: question, THEMATIQUE: String(values[15] || '').trim() || 'your industry',
           NAME: mfeName_(values[13], mfeShortName_(values[1])), HELLO: mfeHello_(values[13]), BOOKING: MFE.BOOKING, OPTOUT: mfeMsg_('MFE_MSG_OPTOUT') };
}

function mfeFill_(tpl, v) {
  return String(tpl).replace(/\{(\w+)\}/g, function (m, k) { return v[k] != null ? v[k] : m; })
    .replace(/\n{3,}/g, '\n\n').trim();
}

// ---------- Signature ----------
// Gmail n'ajoute PAS la signature Workspace aux mails envoyes par script : elle est geree ici.
function mfeSigCfg_() {
  var r = mfeReadSettings_();
  var g = function (k) { return String(r[k] == null ? '' : r[k]).trim(); };
  return { html: g('MFE_SIG_HTML').toUpperCase() === 'TRUE', photo: g('MFE_SIG_PHOTO'), nom: g('MFE_SIG_NOM'),
           titre: g('MFE_SIG_TITRE'), accroche: g('MFE_SIG_ACCROCHE'), email: g('MFE_SIG_EMAIL'),
           site: g('MFE_SIG_SITE'), linkedin: g('MFE_SIG_LINKEDIN'), tel: g('MFE_SIG_TEL'), texte: g('MFE_MSG_SIGNATURE') };
}

// Version texte (toujours envoyee : c'est ce que lisent les filtres anti-spam et certains clients mail)
function mfeWithSignature_(body) {
  body = String(body).replace(/\*\*(.+?)\*\*/g, '$1').replace(/__(.+?)__/g, '$1')   // version texte : sans les ** / __ ni les balises <strong> <u> <em> <b>
    .replace(/<a\s+(?:bold\s+)?href="([^"]+)"[^>]*>(.+?)<\/a>/g, '$2 : $1').replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/?(strong|b|u|em)>/gi, '');
  var c = mfeSigCfg_(), lines = [];
  if (c.texte) lines.push(c.texte);
  else if (c.html) {
    lines.push('--', c.nom + (c.titre ? ' | ' + c.titre : ''));
    if (c.accroche) lines.push(c.accroche);
    lines.push([c.email, c.site.split('|').pop().trim(), c.tel].filter(String).join(' | '));
    if (c.linkedin) lines.push(c.linkedin);
  }
  return lines.length ? body + '\n\n' + lines.join('\n') : body;
}

function mfeEsc_(t) { return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

// **texte** = gras ; les URL deviennent des liens cliquables
function mfeTextToHtml_(body) {
  // Un paragraphe (<p>) par bloc separe d'une ligne vide ; lien affiche sans https:// ni #ancre ; **gras** ; __souligne__
  // Balises acceptees dans les textes (le texte est echappe avant) : <strong> <b> <u> <em> <br> et <a href="URL">texte</a>
  return mfeEsc_(body).split(/\n{2,}/).map(function (p) {
    var anchors = [];   // les <a href> des textes sont mis de cote : l'URL n'est jamais affichee, le texte du lien est cliquable
    p = p.replace(/&lt;a bold href=&quot;(https?:\/\/.+?)&quot;&gt;(.+?)&lt;\/a&gt;/g, function (m, u, t) {   // lien des relances : bleu #1155CC, sans souligne, gras 600
      anchors.push('<a href="' + u + '" style="color:#1155CC;text-decoration:none;font-weight:600;">' + t + '</a>');
      return '\u0001' + (anchors.length - 1) + '\u0001';
    });
    p = p.replace(/&lt;a href=&quot;(https?:\/\/.+?)&quot;&gt;(.+?)&lt;\/a&gt;/g, function (m, u, t) {
      anchors.push('<a href="' + u + '" style="color:#1155CC;text-decoration:none;">' + t + '</a>');
      return '\u0001' + (anchors.length - 1) + '\u0001';
    });
    p = p.replace(/(https?:\/\/[^\s<]+)/g, function (u) {
      return '<a href="' + u + '" style="color:#1a56db">' + u.replace(/^https?:\/\//, '').replace(/#.*$/, '') + '</a>';
    }).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
      .replace(/__(.+?)__/g, '<u>$1</u>')
      .replace(/&lt;(strong|b)&gt;(.+?)&lt;\/(strong|b)&gt;/g, '<strong>$2</strong>')   // <strong> / <u> / <em> ecrits dans les textes
      .replace(/&lt;u&gt;(.+?)&lt;\/u&gt;/g, '<u>$1</u>')
      .replace(/&lt;em&gt;(.+?)&lt;\/em&gt;/g, '<em>$1</em>')
      .replace(/&lt;br&gt;/g, '<br>')
      .replace(/\n/g, '<br>')
      .replace(/\u0001(\d+)\u0001/g, function (m, k) { return anchors[Number(k)]; });
    return '<p style="margin:0 0 14px">' + p + '</p>';
  }).join('');
}

function mfeSignatureHtml_() {
  // Signature B2B premium (05/10/2026) : photo | 1 trait bleu vertical | nom, role, promesse, fin trait gris, email, LinkedIn.
  // Photo, nom, role, promesse, email et LinkedIn viennent des reglages MFE_SIG_* (aucune URL en dur). Tableau = compatible Gmail.
  var c = mfeSigCfg_();
  var promesse = c.accroche || 'We Turn Your Podcast Into Growth';
  var photo = c.photo ? '<td style="vertical-align:middle;padding-right:18px;">' +
      '<img src="' + mfeEsc_(c.photo) + '" alt="' + mfeEsc_(c.nom) + '" width="105" height="105" ' +
      'style="display:block;width:105px;height:105px;border-radius:50%;object-fit:cover;border:0;"></td>' : '';
  var email = c.email ? '<div style="font-size:13px;line-height:20px;"><a href="mailto:' + mfeEsc_(c.email) +
      '" style="color:#555555;text-decoration:none;">' + mfeEsc_(c.email) + '</a></div>' : '';
  var linkedin = c.linkedin ? '<div style="font-size:13px;line-height:20px;margin-top:1px;"><a href="' + mfeEsc_(c.linkedin) +
      '" style="color:#1155CC;text-decoration:none;font-weight:600;">\u2192 Connect on LinkedIn</a></div>' : '';
  return '<table cellpadding="0" cellspacing="0" border="0" style="margin-top:18px;font-family:Arial,Helvetica,sans-serif;color:#222222;"><tr>' +
    photo +
    '<td style="width:2px;background:#1a73e8;font-size:1px;line-height:1px;">&nbsp;</td>' +
    '<td style="vertical-align:middle;padding-left:18px;">' +
    '<div style="font-size:17px;line-height:22px;font-weight:700;color:#111111;">' + mfeEsc_(c.nom) + '</div>' +
    (c.titre ? '<div style="font-size:14px;line-height:20px;color:#555555;margin-top:2px;">' + mfeEsc_(c.titre) + '</div>' : '') +
    '<div style="font-size:13px;line-height:19px;font-weight:600;color:#333333;margin-top:7px;">' + mfeEsc_(promesse) + '</div>' +
    '<div style="width:34px;border-top:1px solid #d8d8d8;margin:8px 0 6px 0;"></div>' +
    email + linkedin +
    '</td></tr></table>';
}

// Options d'envoi : expediteur + version HTML avec signature riche si MFE_SIG_HTML = TRUE
function mfeSendOpts_(bodySansSignature) {
  // Toujours une version HTML (gras + liens) ; signature riche si MFE_SIG_HTML = TRUE, sinon signature texte
  var opts = mfeFromOpts_(), c = mfeSigCfg_();
  var sig = c.html ? mfeSignatureHtml_() : (c.texte ? '<br><br>' + mfeTextToHtml_(c.texte) : '');
  opts.htmlBody = '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.6;color:#202124">' +
    mfeTextToHtml_(bodySansSignature) + '</div>' + sig;
  return opts;
}

function mfeDraft_(values, variant) {  // [objet, corps, variante] du 1er mail
  var v = mfeVars_(values);
  variant = variant || 'A';
  v.CTA = mfeFill_(mfeMsg_('MFE_CTA_' + variant) || mfeMsg_('MFE_CTA_A'), v);
  var body = Number(values[4]) > 0 ? mfeMsg_('MFE_MSG_REPONSES') : mfeMsg_('MFE_MSG_FICHE');
  return [mfeFill_(mfeMsg_('MFE_MSG_OBJET'), v), mfeFill_(body, v), variant];
}

// ---------- Test A/B du CTA ----------
// Variantes actives = cles MFE_CTA_A, _B, _C, _D non vides. Repartition : poids publies par ab_optimizer.py
// (ab_test.json sur GitHub) ; sans poids, repartition egale. Choix = variante la plus en retard sur sa part.
function mfeAbPlan_(rows, cfg) {
  var variants = ['A'];
  if (cfg.AB_ACTIF) {
    var st = mfeReadSettings_();
    variants = MFE_AB_KEYS.filter(function (k) { return ('MFE_CTA_' + k) in st ? String(st['MFE_CTA_' + k]).trim() !== '' : k === 'A'; });
    if (!variants.length) variants = ['A'];
  }
  var weights = {};
  try {
    var cache = CacheService.getScriptCache(), raw = cache.get('MFE_AB');
    if (!raw) {
      var res = UrlFetchApp.fetch(MFE.AB_URL + '?t=' + Date.now(), { muteHttpExceptions: true });
      if (res.getResponseCode() === 200) { raw = res.getContentText(); cache.put('MFE_AB', raw, 600); }
    }
    if (raw) weights = JSON.parse(raw).weights || {};
  } catch (e) { Logger.log('ab_test.json illisible : %s', e); }
  var sum = 0;
  var complete = variants.every(function (k) { return weights[k] > 0; });   // poids publies pour TOUTES les variantes actives, sinon repartition egale
  variants.forEach(function (k) { sum += (complete ? weights[k] : 0); });
  var w = {};
  variants.forEach(function (k) { w[k] = complete && sum > 0 ? weights[k] / sum : 1 / variants.length; });
  var counts = {}, total = 0;
  variants.forEach(function (k) { counts[k] = 0; });
  rows.forEach(function (r) {
    var vr = String(r.values[14] || '');
    if (!r.values[7] || new Date(r.values[7]).getTime() < MFE_AB_DEPUIS) return;   // ancien mail : hors test A-E
    if (vr && counts[vr] != null) { counts[vr]++; total++; }
  });
  return { variants: variants, weights: w, counts: counts, total: total };
}

function mfeAbPick_(ab) {
  var best = ab.variants[0], bestGap = -1e9;
  ab.variants.forEach(function (k) {
    var gap = ab.weights[k] * (ab.total + 1) - ab.counts[k];
    if (gap > bestGap) { bestGap = gap; best = k; }
  });
  return best;
}

function mfeRows_(sh) {
  var last = sh.getLastRow();
  if (last <= MFE.HEADER_ROW) return [];
  return sh.getRange(MFE.HEADER_ROW + 1, 1, last - MFE.HEADER_ROW, MFE.COLS.length).getValues()
    .map(function (values, i) { return { row: MFE.HEADER_ROW + 1 + i, values: values }; })
    .filter(function (r) { return r.values[0]; });
}

// ---------- Reglages (onglet Reglages, cles MFE_*) ----------
function mfeReglagesSheet_() {
  var ss = mfeSS_();
  return ss.getSheetByName(MFE.REGLAGES) || ss.getSheetByName('Reglages') || ss.insertSheet(MFE.REGLAGES);
}

function mfeReadSettings_() {
  var sh = mfeReglagesSheet_();
  var out = {};
  if (sh.getLastRow() < 1) return out;
  sh.getRange(1, 1, sh.getLastRow(), 2).getValues().forEach(function (r) {
    var k = String(r[0]).trim();
    if (k.indexOf('MFE_') === 0) out[k] = r[1];
  });
  return out;
}

function mfeEnsureSettings_() {
  var sh = mfeReglagesSheet_();
  var have = mfeReadSettings_();
  var missing = MFE_DEFAULTS.concat(MFE_MSG_DEFAULTS).filter(function (d) { return !(d[0] in have); });
  if (missing.length) sh.getRange(sh.getLastRow() + 1, 1, missing.length, 3).setValues(missing);
  var props = PropertiesService.getScriptProperties();
  if (props.getProperty('MFE_MSG_V') !== MFE_MSG_VERSION) {   // nouveaux textes par defaut -> Reglages
    var vals = sh.getRange(1, 1, sh.getLastRow(), 1).getValues();
    MFE_MSG_DEFAULTS.forEach(function (d) {
      if (MFE_MSG_RESET.indexOf(d[0]) === -1) return;
      for (var i = 0; i < vals.length; i++) if (String(vals[i][0]).trim() === d[0]) sh.getRange(i + 1, 2, 1, 2).setValues([[d[1], d[2]]]);
    });
    props.setProperty('MFE_MSG_V', MFE_MSG_VERSION);
  }
}

function mfeMigrateOldSettings_(sh) {
  // v1 : reglages en haut de l'onglet MarketForge Engine -> deplaces dans Reglages
  if (String(sh.getRange(2, 1).getValue()) !== 'ENVOI_AUTO') return;
  var old = {};
  sh.getRange(2, 1, 3, 2).getValues().forEach(function (r) { old['MFE_' + r[0]] = String(r[1]); });
  MFE_DEFAULTS.forEach(function (d) { if (old[d[0]] != null) d[1] = old[d[0]]; });
  sh.getRange(1, 1, 4, 3).clearContent();
  sh.getRange(1, 1).setValue('Reglages : onglet "Réglages", cles MFE_*').setFontWeight('bold');
}

function mfeSettings_() {
  var cfg = mfeReadSettings_();
  return {
    ENVOI_AUTO: String(cfg.MFE_ENVOI_AUTO).toUpperCase() === 'TRUE',
    MAX_ENVOIS_JOUR: Math.min(parseInt(cfg.MFE_MAX_ENVOIS_JOUR, 10) || 30, 1500),
    MONTEE: String(cfg.MFE_MONTEE_PROGRESSIVE).toUpperCase() !== 'FALSE',
    H_START: parseInt(String(cfg.MFE_HEURES_ENVOI || '8-19').split('-')[0], 10) || 8,
    H_END: parseInt(String(cfg.MFE_HEURES_ENVOI || '8-19').split('-')[1], 10) || 19,
    RELANCE_JOURS: parseInt(cfg.MFE_RELANCE_JOURS, 10) || 0,
    EMAIL_TEST: String(cfg.MFE_EMAIL_TEST || '').trim(),
    AB_ACTIF: String(cfg.MFE_AB_ACTIF).toUpperCase() !== 'FALSE',
  };
}

// ---------- Pont GitHub (application web) ----------
function mfeAuth_(secret) {
  var s = PropertiesService.getScriptProperties().getProperty('MFE_SECRET');
  return s && secret === s;
}

function mfeJson_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  var p = (e && e.parameter) || {};
  if (!mfeAuth_(p.secret)) return mfeJson_({ ok: false, error: 'secret invalide' });
  if (p.action === 'config') return mfeJson_({ ok: true, reglages: mfeReadSettings_() });
  if (p.action === 'status') {
    var sh = mfeSheet_();
    var rows = mfeRows_(sh).map(function (r) {
      var o = {}; MFE.COLS.forEach(function (c, i) { o[c] = r.values[i]; }); return o;
    });
    var histo = mfeHisto_();
    var last = histo.getLastRow() > 1 ? histo.getRange(2, 1, Math.min(histo.getLastRow() - 1, 14), MFE.HISTO_COLS.length).getValues() : [];
    // Expose le plafond du jour (montee progressive) et le nombre deja envoye aujourd'hui,
    // pour que le tableau de bord puisse estimer l'heure d'envoi des prospects "Pret".
    var cfg = mfeSettings_();
    var today = new Date().toDateString();
    var sentToday = mfeRows_(sh).filter(function (r) {
      return r.values[7] && new Date(r.values[7]).toDateString() === today;
    }).length;
    return mfeJson_({ ok: true, reglages: mfeReadSettings_(), prospects: rows, historique: last,
                       cap_jour_effectif: mfeDailyCap_(cfg), envoyes_aujourdhui: sentToday, script_version: 12 });
  }
  return mfeJson_({ ok: false, error: 'action inconnue (config | status)' });
}

function doPost(e) {
  var body = {};
  try { body = JSON.parse(e.postData.contents); } catch (err) { return mfeJson_({ ok: false, error: 'JSON invalide' }); }
  var p = (e && e.parameter) || {};
  if (!mfeAuth_(p.secret || body.secret)) return mfeJson_({ ok: false, error: 'secret invalide' });
  if (body.action === 'tendances') return mfeTendances_(body);
  if (body.action === 'optimisations') return mfeOptimisations_(body);
  if (body.action === 'cmd') return mfeCmd_(body);
  if (body.action !== 'report') return mfeJson_({ ok: false, error: 'action inconnue (report, tendances)' });

  var lock = LockService.getScriptLock(); lock.waitLock(30000);
  try {
    var ob = body.onboarded || [], ex = body.extraction_jour || {};
    mfeHisto_().insertRowBefore(2);
    mfeHisto_().getRange(2, 1, 1, MFE.HISTO_COLS.length).setValues([[
      body.date || new Date(), body.decouverts || 0, ob.length,
      ob.filter(function (o) { return o.listenly_created; }).length,
      ob.map(function (o) { return o.podcast_name; }).join(', '),
      ex.episodes || 0, ex.minutes || 0, ex.moments || 0,
      (body.onboard_echecs || []).join(', '), body.run_url || '']]);
    var podcasts = {};
    (body.podcasts || []).forEach(function (x) { podcasts[x.slug] = x; });
    var sh = mfeSheet_();
    var added = mfeImport_(sh, podcasts);
    // met a jour le nombre de Q/R des lignes deja presentes
    mfeRows_(sh).forEach(function (r) {
      var x = podcasts[r.values[0]];
      if (x && x.moments_count !== r.values[4]) sh.getRange(r.row, 5).setValue(x.moments_count);
      if (x && x.thematique && !r.values[15]) sh.getRange(r.row, 16).setValue(x.thematique);
      // preuve du mail : question + moment exact (colonnes 17-18), seulement si le 1er mail n'est pas encore parti
      if (x && x.latest_episode_question && x.latest_episode_moment_id && !r.values[7] && !r.values[16]) {
        sh.getRange(r.row, 17, 1, 2).setValues([[x.latest_episode_question, x.latest_episode_moment_id]]);
      }
    });
    return mfeJson_({ ok: true, lignes_ajoutees: added });
  } finally { lock.releaseLock(); }
}

// Classement des secteurs (ciblage adaptatif) -> section a droite de l'onglet Synthese (colonnes I a S)
function mfeTendances_(body) {
  var ss = mfeSS_();
  var sh = ss.getSheetByName('Synthèse') || ss.getSheetByName('Synthese');
  if (!sh) return mfeJson_({ ok: false, error: 'onglet Synthese introuvable' });
  var rows = body.rows || [];
  var head = ['#', 'Secteur', 'Poids ciblage %', 'Variation (pts)', 'Tendance', 'Podcasts onboardes',
              'Joignables (email)', 'Envoyes', 'Rebonds', 'Reponses', 'Taux reponse %'];
  var col = 9, top = 3, width = head.length;   // colonne I, ligne 3
  sh.getRange(top, col, 40, width).clearContent().clearFormat();
  sh.getRange(top, col).setValue('Ranking des tendances — secteurs ciblés (mis à jour ' + (body.updated || '') + ')')
    .setFontWeight('bold').setFontSize(12);
  sh.getRange(top + 1, col, 1, width).setValues([head]).setFontWeight('bold').setFontColor('#ffffff')
    .setBackground('#0e7c86').setWrap(true).setVerticalAlignment('middle');
  if (rows.length) {
    sh.getRange(top + 2, col, rows.length, width).setValues(rows);
    sh.getRange(top + 2, col + 2, rows.length, 1).setNumberFormat('0.0');
    sh.getRange(top + 2, col + 3, rows.length, 1).setNumberFormat('+0.0;-0.0;0.0');
  }
  var note = top + 3 + rows.length;
  sh.getRange(note, col).setValue('Envois : ' + (body.envois_total || 0) + ' · Réponses réelles : ' + (body.reponses_total || 0) +
    ' · Le poids répartit le budget de découverte : plus un secteur répond, plus il est ciblé (plancher d\'exploration conservé).')
    .setFontStyle('italic').setFontColor('#666666');
  sh.setColumnWidth(col + 1, 210);
  // Bloc "Test A/B du CTA" sous le classement des secteurs (ligne 46)
  var ab = body.ab;
  if (ab && ab.rows) {
    var t2 = 46, h2 = ['Variante', 'Type de CTA', 'Envoyes', 'Rebonds', 'Reponses', 'Taux reponse %', 'Chance d\'etre la meilleure %', 'Part des envois %'];
    sh.getRange(t2, col, 20, width).clearContent().clearFormat();
    sh.getRange(t2, col).setValue('Test A/B du CTA (appel \u00e0 l\'action du mail)').setFontWeight('bold').setFontSize(12);
    sh.getRange(t2 + 1, col, 1, h2.length).setValues([h2]).setFontWeight('bold').setFontColor('#ffffff')
      .setBackground('#0e7c86').setWrap(true).setVerticalAlignment('middle');
    if (ab.rows.length) sh.getRange(t2 + 2, col, ab.rows.length, h2.length).setValues(ab.rows);
    sh.getRange(t2 + 3 + ab.rows.length, col).setValue('Verdict : ' + (ab.verdict || '')).setFontWeight('bold');
    sh.getRange(t2 + 4 + ab.rows.length, col).setValue('Mis \u00e0 jour ' + (ab.updated || '') + ' \u00b7 La part des envois suit les r\u00e9sultats une fois 30 envois atteints par variante.')
      .setFontStyle('italic').setFontColor('#666666');
  }
  return mfeJson_({ ok: true, lignes: rows.length });
}

// Journal des optimisations -> onglet 'Optimisations' (colonnes A a D : Version, Optimisation, Date, Statut ; a partir de la ligne 5).
// La liste deroulante / les couleurs de la colonne Statut sont conservees (seuls contenu + mise en forme des lignes sont reecrits).
function mfeOptimisations_(body) {
  var sh = mfeSS_().getSheetByName('Optimisations');
  if (!sh) return mfeJson_({ ok: false, error: 'onglet Optimisations introuvable' });
  var rows = body.rows || [];
  var first = 5;
  sh.getRange(first, 1, 80, 4).clearContent().clearFormat();
  sh.getRange(2, 2).setValue('\u2705 Valid\u00e9   \u00b7   \u26a0\ufe0f En cours / \u00e0 surveiller   \u00b7   \u274c Pas encore fait   \u2014   derni\u00e8re mise \u00e0 jour : ' + (body.updated || ''));
  var values = rows.map(function (r) { return r.section ? ['', String(r.section).toUpperCase(), '', ''] : [r.version || '\u2014', r.texte, r.date, r.statut]; });
  if (values.length) {
    var rng = sh.getRange(first, 1, values.length, 4);
    rng.setValues(values).setWrap(true).setVerticalAlignment('middle').setFontSize(11);
    sh.getRange(first, 1, values.length, 1).setHorizontalAlignment('center').setFontWeight('bold').setFontColor('#0e5966');
    sh.getRange(first, 3, values.length, 2).setHorizontalAlignment('center');
    rng.setBorder(null, null, true, null, null, true, '#e0e0e0', SpreadsheetApp.BorderStyle.SOLID);
    rows.forEach(function (r, i) {
      if (r.section) sh.getRange(first + i, 1, 1, 4).setBackground('#e6f2f5').setFontWeight('bold').setFontColor('#0e5966');
    });
    sh.getRange(first, 4, values.length, 1).setDataValidation(SpreadsheetApp.newDataValidation()
      .requireValueInList(['\u2705 Valid\u00e9', '\u26a0\ufe0f En cours', '\u274c Pas encore fait'], true).setAllowInvalid(true).build());
  }
  return mfeJson_({ ok: true, lignes: rows.length });
}

function mfeHisto_() {
  var ss = mfeSS_();
  var sh = ss.getSheetByName(MFE.HISTO);
  if (sh) return sh;
  sh = ss.insertSheet(MFE.HISTO);
  sh.getRange(1, 1, 1, MFE.HISTO_COLS.length).setValues([MFE.HISTO_COLS]).setFontWeight('bold').setBackground('#eef3fd');
  sh.setFrozenRows(1);
  return sh;
}

function mfeSS_() {
  return SpreadsheetApp.getActiveSpreadsheet() || SpreadsheetApp.openById('1b53cWGiz6iOuakpotw_Ck4bQBeIMJa3hfq5gP2mFiT4');
}

function mfeSheet_() {
  var ss = mfeSS_();
  var sh = ss.getSheetByName(MFE.SHEET);
  if (sh) return sh;
  sh = ss.insertSheet(MFE.SHEET);
  sh.getRange(1, 1).setValue('Reglages : onglet "Réglages", cles MFE_*').setFontWeight('bold');
  sh.getRange(MFE.HEADER_ROW, 1, 1, MFE.COLS.length).setValues([MFE.COLS]).setFontWeight('bold').setBackground('#eef3fd');
  sh.setFrozenRows(MFE.HEADER_ROW);
  return sh;
}


// =====================================================================
// MENU "MarketForge Engine" — pilotage manuel (comme la machine SaaS)
// =====================================================================
var MFE_REPO = 'listenly-geo/listenlygeo';
var MFE_WORKFLOW = 'marketforge-engine-run.yml';

function mfeOnOpen() {
  var ui = mfeUi_();
  if (!ui) return;
  ui.createMenu('MarketForge Engine')
    .addItem('🚀 Lancer le moteur maintenant (podcasts + fiches + emails)', 'mfeMenuLancerMoteur')
    .addItem('📊 Voir l’état du moteur (dernier run)', 'mfeMenuEtatMoteur')
    .addSeparator()
    .addItem('Importer les nouveaux contacts maintenant', 'mfeMenuImporter')
    .addItem('📊 Recevoir le rapport maintenant', 'mfeMenuRapport')
    .addItem('Envoyer un test (à moi)', 'mfeMenuTest')
    .addItem('Test limité (1 vrai e-mail maintenant)', 'mfeMenuTest1')
    .addItem('Test limité (3 vrais e-mails maintenant)', 'mfeMenuTestLimite')
    .addItem('Traiter la file maintenant (envoi hors horaires)', 'mfeMenuTraiter')
    .addItem('Vérifier réponses + relances maintenant', 'mfeMenuRelances')
    .addSeparator()
    .addItem('Activer l’automatique (envoi toutes les 15 min)', 'installer')
    .addItem('Créer / réparer les réglages MFE_*', 'mfeMenuReglages')
    .addItem('Enregistrer le token GitHub', 'mfeMenuToken')
    .addItem('Enregistrer la clé MyEmailVerifier (vérification des emails)', 'mfeMenuVerifKey')
    .addSeparator()
    .addItem('Désactiver l’envoi automatique', 'mfeMenuDesactiver')
    .addToUi();
}

function mfeUi_() { try { return SpreadsheetApp.getUi(); } catch (e) { return null; } }
function mfeAlert_(msg) { var ui = mfeUi_(); if (ui) ui.alert('MarketForge Engine', msg, ui.ButtonSet.OK); Logger.log(msg); }
function mfeConfirm_(msg) {
  var ui = mfeUi_();
  return !ui || ui.alert('MarketForge Engine', msg, ui.ButtonSet.YES_NO) === ui.Button.YES;
}

function mfeMenuToken() {
  var ui = mfeUi_();
  var r = ui.prompt('Token GitHub', 'Colle un token GitHub (fine-grained, repo listenly-geo/listenlygeo, permission Actions : Read and write). Stocke dans le script, jamais dans le tableau.', ui.ButtonSet.OK_CANCEL);
  if (r.getSelectedButton() !== ui.Button.OK || !r.getResponseText().trim()) return;
  PropertiesService.getScriptProperties().setProperty('MFE_GH_TOKEN', r.getResponseText().trim());
  mfeAlert_('Token enregistre. Le bouton "Lancer le moteur maintenant" est actif.');
}

function mfeMenuLancerMoteur() {
  var token = PropertiesService.getScriptProperties().getProperty('MFE_GH_TOKEN');
  if (!token) { mfeAlert_('Enregistre d’abord le token GitHub (menu MarketForge Engine > Enregistrer le token GitHub).'); return; }
  if (!mfeConfirm_('Lancer maintenant un run complet : decouverte de podcasts, fiches Listenly + N1, emails. ~15-30 min. Les contacts arriveront ensuite ici automatiquement. Continuer ?')) return;
  var res = UrlFetchApp.fetch('https://api.github.com/repos/' + MFE_REPO + '/actions/workflows/' + MFE_WORKFLOW + '/dispatches', {
    method: 'post', contentType: 'application/json', muteHttpExceptions: true,
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json' },
    payload: JSON.stringify({ ref: 'main' })
  });
  var ok = res.getResponseCode() === 204;
  mfeAlert_(ok ? '🚀 Moteur lance. Suis-le avec "Voir l’etat du moteur".' : 'Echec du lancement (HTTP ' + res.getResponseCode() + ') : ' + res.getContentText().slice(0, 200));
}

function mfeMenuEtatMoteur() {
  var get = function (url) { return JSON.parse(UrlFetchApp.fetch(url, { muteHttpExceptions: true }).getContentText()); };
  var run = (get('https://api.github.com/repos/' + MFE_REPO + '/actions/workflows/' + MFE_WORKFLOW + '/runs?per_page=1').workflow_runs || [])[0];
  if (!run) { mfeAlert_('Aucun run trouve.'); return; }
  var etat = run.status === 'completed' ? (run.conclusion === 'success' ? '✅ termine' : '❌ ' + run.conclusion) : '⏳ en cours';
  var lignes = ['Dernier run : ' + etat + ' (' + Utilities.formatDate(new Date(run.created_at), Session.getScriptTimeZone(), 'dd/MM HH:mm') + ')'];
  if (run.status === 'completed') {
    var job = (get(run.jobs_url).jobs || [])[0];
    if (job) (get('https://api.github.com/repos/' + MFE_REPO + '/check-runs/' + job.id + '/annotations') || []).forEach(function (a) {
      if (a.title) lignes.push('• ' + a.title + ' : ' + a.message.slice(0, 400));
    });
  }
  var sh = mfeSheet_(), st = {};
  mfeRows_(sh).forEach(function (r) { st[r.values[6]] = (st[r.values[6]] || 0) + 1; });
  lignes.push('', 'Contacts dans l’onglet : ' + JSON.stringify(st));
  mfeAlert_(lignes.join('\n'));
}

function mfeMenuImporter() {
  var n = mfeImport_(mfeSheet_(), null);
  mfeAlert_(n + ' nouveau(x) contact(s) importe(s).');
}

function mfeMenuTest() {
  var moi = Session.getEffectiveUser().getEmail();
  var sh = mfeSheet_(), rows = mfeRows_(sh);
  var exemple = rows.length ? rows[0].values : ['', 'Test Podcast', '', 'https://listenly.fr/podcast-btb/a16z-crypto-show-podcast.html', 0];
  mfeEnsureSettings_();
  var n = 0;
  ['A'].forEach(function (vr) {
    var d = mfeDraft_(exemple, vr);
    GmailApp.sendEmail(moi, '[TEST ' + vr + ' - premier mail] ' + d[0], mfeWithSignature_(d[1]), mfeSendOpts_(d[1]));
    n++;
  });
  var v = mfeVars_(exemple), objet = mfeFill_(mfeMsg_('MFE_MSG_OBJET'), v);
  var rel = mfeFill_(mfeMsg_('MFE_MSG_RELANCE'), v);
  GmailApp.sendEmail(moi, '[TEST relance] Re: ' + objet, mfeWithSignature_(rel), mfeSendOpts_(rel));
  n++;
  mfeAlert_(n + ' mails test envoyes a ' + moi + ' (1 par variante de CTA + la relance). Textes modifiables dans Reglages (MFE_MSG_*, MFE_CTA_*). Expediteur : ' + (mfeFromOpts_().from || moi));
}


// ---------- Commandes de test pilotables a distance (GitHub -> web app, protegees par le secret) ----------
// test_me   : envoie a TOI le mail 1 + les 3 relances (exemple = podcast "slug" ou 1re ligne Pret avec question)
// test_real : envoie de VRAIS mails (n = 1 a 3, optionnel slug = un seul podcast), seulement si confirm = true
function mfeCmd_(body) {
  var lock = LockService.getScriptLock(); lock.waitLock(30000);
  try {
    var sh = mfeSheet_(), cmd = String(body.cmd || ''), slug = String(body.slug || '');
    if (cmd === 'test_me') {
      var moi = Session.getEffectiveUser().getEmail(), ex = null;
      mfeEnsureSettings_();
      mfeRows_(sh).forEach(function (r) {
        if (ex) return;
        if (slug ? r.values[0] === slug : (r.values[6] === 'Pret' && r.values[16] && r.values[17])) ex = r.values;
      });
      if (!ex) return mfeJson_({ ok: false, error: 'aucune ligne trouvee (Pret avec question)' });
      var d = mfeDraft_(ex, 'A');
      GmailApp.sendEmail(moi, '[TEST mail 1] ' + d[0], mfeWithSignature_(d[1]), mfeSendOpts_(d[1]));
      var v = mfeVars_(ex), objet = mfeFill_(mfeMsg_('MFE_MSG_OBJET'), v), n = 1;
      ['MFE_MSG_RELANCE', 'MFE_MSG_RELANCE_2', 'MFE_MSG_RELANCE_3'].forEach(function (k, i) {
        var t = mfeFill_(mfeMsg_(k), v);
        GmailApp.sendEmail(moi, '[TEST relance ' + (i + 1) + '] Re: ' + objet, mfeWithSignature_(t), mfeSendOpts_(t));
        n++;
      });
      return mfeJson_({ ok: true, cmd: cmd, mails_envoyes_a_toi: n, podcast: ex[1], slug: ex[0], question: ex[16] || '', moment_id: ex[17] || '' });
    }
    if (cmd === 'test_real') {
      if (body.confirm !== true) return mfeJson_({ ok: false, error: 'confirm=true requis (envoi de vrais mails)' });
      var nb = Math.max(1, Math.min(Number(body.n) || 1, 3));
      var sent = mfeSend_(sh, mfeSettings_(), nb, slug);
      return mfeJson_({ ok: true, cmd: cmd, demandes: nb, envoyes: sent, slug: slug });
    }
    return mfeJson_({ ok: false, error: 'cmd inconnue (test_me | test_real)' });
  } finally { lock.releaseLock(); }
}

// Menu : 1 seul vrai e-mail
function mfeMenuTest1() {
  if (!mfeConfirm_('Envoyer MAINTENANT 1 VRAI e-mail au premier contact "Pret" (hors horaires) ?')) return;
  var sh = mfeSheet_();
  var n = mfeSend_(sh, mfeSettings_(), 1);
  mfeAlert_(n + ' e-mail reel envoye. Verifie la colonne Statut et tes "Envoyes".');
}

function mfeMenuTestLimite() {
  if (!mfeConfirm_('Envoyer MAINTENANT jusqu’a 3 VRAIS e-mails aux premiers contacts "Pret" (hors horaires) ?')) return;
  var sh = mfeSheet_();
  mfeImport_(sh, null);
  var n = mfeSend_(sh, mfeSettings_(), 3);
  mfeAlert_(n + ' e-mail(s) reel(s) envoye(s). Verifie la colonne Statut et tes "Envoyes".');
}

function mfeMenuTraiter() {
  var cfg = mfeSettings_();
  if (!mfeConfirm_('Importer les contacts puis envoyer maintenant, dans la limite du jour (' + mfeDailyCap_(cfg) + ' mails), meme hors horaires ?')) return;
  var sh = mfeSheet_();
  var added = mfeImport_(sh, null);
  var sent = mfeSend_(sh, cfg, true);
  mfeAlert_(added + ' contact(s) importe(s), ' + sent + ' e-mail(s) envoye(s).');
}

function mfeMenuRelances() {
  var sh = mfeSheet_(), cfg = mfeSettings_();
  var rep = mfeCheckReplies_(sh);
  var rel = cfg.RELANCE_JOURS > 0 ? mfeFollowUp_(sh, cfg.RELANCE_JOURS) : 0;
  mfeAlert_(rep + ' nouvelle(s) reponse(s), ' + rel + ' relance(s) envoyee(s).');
}

function mfeMenuReglages() {
  mfeEnsureSettings_();
  mfeAlert_('Reglages MFE_* verifies dans l’onglet Reglages.');
}

function mfeMenuDesactiver() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'marketforgeEngineQuotidien' || t.getHandlerFunction() === 'marketforgeEngineEnvoi') ScriptApp.deleteTrigger(t);
  });
  mfeAlert_('Envoi automatique desactive (le menu reste disponible). Pour reactiver : "Activer l’automatique".');
}

// ======================================================================
// RAPPORT EMAIL (HTML, style epure) : referencement + nouvelles fiches + prospection
// Declenche par le passage horaire (aucun declencheur a installer). Reglages : MFE_RAPPORT*.
// ======================================================================
var MFE_RAW = 'https://raw.githubusercontent.com/listenly-geo/listenlygeo/main/';

function mfeRapportSiPrevu_() {
  var r = mfeReadSettings_(), mode = String(r.MFE_RAPPORT || 'QUOTIDIEN').toUpperCase().trim();
  if (mode === 'OFF') return;
  var now = new Date(), h = now.getHours(), props = PropertiesService.getScriptProperties();
  var dayKey = Utilities.formatDate(now, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  if (mode === 'HORAIRE') {
    if (h < 8 || h > 20) return;
    var hourKey = dayKey + ' ' + h;
    if (props.getProperty('MFE_RAPPORT_LAST') === hourKey) return;
    mfeEnvoyerRapport_('horaire');
    props.setProperty('MFE_RAPPORT_LAST', hourKey);
  } else {
    var heure = parseInt(r.MFE_RAPPORT_HEURE, 10); if (isNaN(heure)) heure = 20;
    if (h < heure || props.getProperty('MFE_RAPPORT_LAST') === dayKey) return;
    mfeEnvoyerRapport_('quotidien');
    props.setProperty('MFE_RAPPORT_LAST', dayKey);
  }
}

function mfeMenuRapport() {
  var to = mfeEnvoyerRapport_('manuel');
  mfeAlert_('Rapport envoye a ' + to + '.');
}

function mfeFetchJson_(path, fallback) {
  try {
    var res = UrlFetchApp.fetch(MFE_RAW + path + '?t=' + Date.now(), { muteHttpExceptions: true });
    return res.getResponseCode() === 200 ? JSON.parse(res.getContentText()) : fallback;
  } catch (e) { return fallback; }
}

function mfeEnvoyerRapport_(mode) {
  var tz = Session.getScriptTimeZone(), now = new Date();
  var today = Utilities.formatDate(now, tz, 'yyyy-MM-dd');
  var d7 = Utilities.formatDate(new Date(now.getTime() - 6 * 86400000), tz, 'yyyy-MM-dd');
  var props = PropertiesService.getScriptProperties();

  // ---- Donnees GitHub (fiches, Google) ----
  var podcasts = mfeFetchJson_('pages/podcast-btb/data/podcasts.json', []);
  var cons = mfeFetchJson_('pages/podcast-btb/data/consolidated_questions.json', { paths: [] });
  var idx = mfeFetchJson_('pages/podcast-btb/data/gsc_index_status.json', { urls: {}, impressions: {} });
  var gp = (mfeFetchJson_('pages/podcast-btb/data/gsc_pages.json', { pages: {} }).pages) || {};
  var total = podcasts.length;
  var todayList = podcasts.filter(function (p) { return String(p.date || '').slice(0, 10) === today; });
  var week = podcasts.filter(function (p) { return String(p.date || '').slice(0, 10) >= d7; }).length;
  var nouvelles;
  if (mode === 'horaire') {   // depuis le dernier rapport
    var prev = parseInt(props.getProperty('MFE_RAPPORT_COUNT') || String(total), 10);
    nouvelles = podcasts.slice(Math.min(prev, total));
  } else nouvelles = todayList;
  props.setProperty('MFE_RAPPORT_COUNT', String(total));

  var urls = idx.urls || {}, inspected = 0, indexed = 0;
  Object.keys(urls).forEach(function (k) { inspected++; if (urls[k].verdict === 'PASS') indexed++; });
  var regroup = (cons.paths || []).length;
  var hubs = Object.keys(gp).filter(function (u) { return /-podcast\.html$/.test(u) && u.indexOf('/questions/') === -1; })
    .map(function (u) { return { url: u, imp: gp[u].impressions || 0, clicks: gp[u].clicks || 0 }; })
    .sort(function (a, b) { return b.imp - a.imp; });
  var hubImp = hubs.reduce(function (a, x) { return a + x.imp; }, 0);
  var names = {}; podcasts.forEach(function (p) { names[p.fiche_url] = p.podcast_name; });

  // ---- Prospection (onglet MarketForge Engine) ----
  var rows = mfeRows_(mfeSheet_()), st = {}, sentToday = 0, sentTotal = 0, relToday = 0, repList = [], repToday = [];
  var isToday = function (v) { return v && Utilities.formatDate(new Date(v), tz, 'yyyy-MM-dd') === today; };
  rows.forEach(function (r) {
    var s = String(r.values[6] || '?'); st[s] = (st[s] || 0) + 1;
    if (r.values[7]) { sentTotal++; if (isToday(r.values[7])) sentToday++; }
    if (isToday(r.values[8])) relToday++;
    if (s === 'Repondu') { repList.push(r.values[1]); if (isToday(r.values[9])) repToday.push(r.values[1]); }
  });
  var cfg = mfeSettings_(), cap = mfeDailyCap_(cfg), bounces = st['Rebond'] || 0;

  // ---- Succes (motivation) ----
  var wins = [];
  if (repToday.length) wins.push('💬 <b>' + repToday.length + ' nouvelle' + (repToday.length > 1 ? 's' : '') + ' réponse' + (repToday.length > 1 ? 's' : '') + '</b> aujourd\'hui : ' + mfeEsc_(repToday.join(', ')) + ' — va vite répondre !');
  if (todayList.length) wins.push('🚀 <b>' + todayList.length + ' nouvelles fiches</b> mises en ligne aujourd\'hui, visibles par Google et les IA.');
  if (sentToday) wins.push('📬 <b>' + sentToday + ' podcasts</b> ont découvert leur fiche dans leur boîte mail aujourd\'hui.');
  if (hubs.length && hubs[0].imp) wins.push('🏆 Ton hub le plus vu : <b>' + mfeEsc_(names[hubs[0].url] || hubs[0].url) + '</b> (' + hubs[0].imp + ' impressions Google).');
  if (regroup) wins.push('🧹 <b>' + regroup + ' anciennes fiches</b> regroupées dans leur hub — le site gagne en force.');
  if (repList.length) wins.push('🔥 <b>' + repList.length + ' podcast' + (repList.length > 1 ? 's' : '') + ' en conversation</b> au total. Chaque réponse = une vente possible à 1 500 € + 500 €/mois.');
  if (!wins.length) wins.push('⚙️ La machine tourne : découverte, fiches et envois se font tout seuls.');

  // ---- HTML ----
  var C = 'font-family:-apple-system,BlinkMacSystemFont,\'Helvetica Neue\',Arial,sans-serif;';
  var card = function (inner) { return '<div style="background:#fff;border-radius:18px;padding:22px 24px;margin:0 0 16px;border:1px solid #e5e5ea">' + inner + '</div>'; };
  var h2 = function (t) { return '<div style="font-size:19px;font-weight:700;color:#1d1d1f;margin:0 0 14px">' + t + '</div>'; };
  var kpis = function (arr) {
    return '<table width="100%" cellpadding="0" cellspacing="0"><tr>' + arr.map(function (k) {
      return '<td style="padding:4px 6px 4px 0;vertical-align:top"><div style="background:#f5f5f7;border-radius:14px;padding:12px 14px">' +
        '<div style="font-size:12px;color:#6e6e73">' + k[0] + '</div><div style="font-size:26px;font-weight:700;color:#1d1d1f;letter-spacing:-.5px">' + k[1] + '</div>' +
        (k[2] ? '<div style="font-size:11px;color:#86868b">' + k[2] + '</div>' : '') + '</div></td>';
    }).join('') + '</tr></table>';
  };
  var line = function (a, b) { return '<tr><td style="padding:8px 0;border-bottom:1px solid #f0f0f3;color:#6e6e73;font-size:14px">' + a + '</td><td style="padding:8px 0;border-bottom:1px solid #f0f0f3;text-align:right;font-weight:600;font-size:14px;color:#1d1d1f">' + b + '</td></tr>'; };

  var ficheItems = nouvelles.slice(0, 40).map(function (p) {
    return '<tr><td style="padding:7px 0;border-bottom:1px solid #f0f0f3;font-size:14px"><a href="' + mfeEsc_(p.fiche_url) + '" style="color:#0071e3;text-decoration:none;font-weight:600">' +
      mfeEsc_(p.podcast_name) + '</a><div style="font-size:12px;color:#86868b">' + mfeEsc_(p.categorie || '') + '</div></td></tr>';
  }).join('');
  if (nouvelles.length > 40) ficheItems += '<tr><td style="padding:8px 0;font-size:13px;color:#86868b">… et ' + (nouvelles.length - 40) + ' autres (voir le tableau de bord)</td></tr>';
  if (!ficheItems) ficheItems = '<tr><td style="padding:8px 0;font-size:14px;color:#86868b">Pas de nouvelle fiche ' + (mode === 'horaire' ? 'depuis le dernier rapport' : 'aujourd\'hui') + ' pour l\'instant.</td></tr>';

  var jourFr = Utilities.formatDate(now, tz, 'dd/MM/yyyy');
  var html = '<div style="background:#f5f5f7;padding:28px 12px;' + C + '"><div style="max-width:620px;margin:0 auto">' +
    '<div style="font-size:12px;font-weight:600;color:#86868b;margin:0 0 4px">MarketForge Engine · Listenly</div>' +
    '<div style="font-size:30px;font-weight:700;color:#1d1d1f;letter-spacing:-.6px;margin:0 0 4px">Ton rapport ' + (mode === 'horaire' ? 'de ' + Utilities.formatDate(now, tz, "HH'h'") : 'du jour') + ' ✨</div>' +
    '<div style="font-size:15px;color:#6e6e73;margin:0 0 20px">' + jourFr + '</div>' +
    card(h2('🎉 Les succès') + wins.map(function (w) { return '<div style="font-size:15px;line-height:1.5;color:#1d1d1f;margin:0 0 10px">' + w + '</div>'; }).join('')) +
    card(h2('📈 Le référencement avance') +
      kpis([['Fiches hub', total, 'au total'], ['Aujourd\'hui', '+' + todayList.length, 'nouvelles'], ['Rythme', Math.round(week / 7), 'fiches / jour']]) +
      '<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px">' +
      line('Hubs visibles dans Google', hubs.length) + line('Impressions des hubs (Search Console)', hubImp) +
      line('Anciennes fiches regroupées dans les hubs', regroup) + line('Fiches question vérifiées / indexées (protégées)', inspected + ' / ' + indexed) + '</table>') +
    card(h2('🆕 Nouvelles fiches' + (nouvelles.length ? ' (' + nouvelles.length + ')' : '')) + '<table width="100%" cellpadding="0" cellspacing="0">' + ficheItems + '</table>') +
    card(h2('📬 La prospection') +
      kpis([['Envoyés aujourd\'hui', sentToday, 'sur ' + cap + ' prévus'], ['Réponses', repList.length, 'au total'], ['Prêts', st['Pret'] || 0, 'à contacter']]) +
      '<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px">' +
      line('Envoi automatique', cfg.ENVOI_AUTO ? '🟢 actif' : '⏸️ en pause') + line('Emails envoyés au total', sentTotal) +
      line('Relances envoyées aujourd\'hui', relToday) +
      line('Rebonds', bounces + (sentTotal ? ' (' + (Math.round(bounces / sentTotal * 1000) / 10) + ' %)' : '')) +
      line('Adresses écartées (anti-rebond)', (st['Email invalide'] || 0) + (st['Email risque'] || 0)) +
      (repList.length ? line('En conversation', mfeEsc_(repList.join(', '))) : '') + '</table>') +
    '<div style="text-align:center;margin:22px 0 8px">' +
    '<a href="https://listenly.fr/podcast-btb/moteur.html" style="display:inline-block;background:#0071e3;color:#fff;text-decoration:none;font-weight:600;font-size:14px;padding:11px 20px;border-radius:999px;margin:4px">Tableau de bord</a> ' +
    '<a href="' + mfeSS_().getUrl() + '" style="display:inline-block;background:#1d1d1f;color:#fff;text-decoration:none;font-weight:600;font-size:14px;padding:11px 20px;border-radius:999px;margin:4px">Google Sheet</a></div>' +
    '<div style="text-align:center;font-size:11px;color:#86868b;margin-top:10px">Rapport ' + mode + ' · réglages MFE_RAPPORT dans l\'onglet Réglages</div>' +
    '</div></div>';

  var to = String(mfeReadSettings_().MFE_RAPPORT_EMAIL || '').trim() || Session.getEffectiveUser().getEmail();
  var subject = (repToday.length ? '💬 ' : '📊 ') + 'MarketForge — ' + (mode === 'horaire' ? Utilities.formatDate(now, tz, "HH'h'") : jourFr) +
    ' · +' + todayList.length + ' fiches · ' + sentToday + ' envois' + (repList.length ? ' · ' + repList.length + ' réponse' + (repList.length > 1 ? 's' : '') : '');
  var plain = 'Rapport MarketForge Engine ' + jourFr + '\nFiches hub : ' + total + ' (+' + todayList.length + ')\nEnvoyes aujourd\'hui : ' + sentToday + '\nReponses : ' + repList.length +
    '\nTableau de bord : https://listenly.fr/podcast-btb/moteur.html';
  GmailApp.sendEmail(to, subject, plain, { htmlBody: html, name: 'MarketForge Engine' });
  return to;
}

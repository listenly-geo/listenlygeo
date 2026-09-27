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
         'Envoye le', 'Relance le', 'Reponse', 'Thread ID', 'Notes'],
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
  ['MFE_MONTEE_PROGRESSIVE', 'TRUE', 'MarketForge Engine — TRUE = 30/j la 1re semaine, 80, 150, 300, 500, 1000 puis plafond (protege la delivrabilite).'],
  ['MFE_HEURES_ENVOI', '8-19', 'MarketForge Engine — plage horaire d\'envoi (heure du script), mails repartis sur la plage.'],
  ['MFE_EMAIL_TEST', '', 'MarketForge Engine — MODE TEST : si une adresse est saisie ici, TOUS les mails partent vers elle (objet prefixe [TEST]) et les prospects restent "Pret". Vider la case pour passer en reel.'],
  ['MFE_RELANCE_JOURS', '4', 'MarketForge Engine — relance unique apres N jours sans reponse (0 = pas de relance).'],
];

// ---------- Messages (modifiables dans l'onglet Reglages, cles MFE_MSG_*) ----------
// Style : court, a la premiere personne, une seule question, texte brut (pas de gras, pas d'emoji).
// Variables : {PODCAST} {URL} {BOOKING} {OPTOUT}
var MFE_MSG_DEFAULTS = [
  ['MFE_MSG_OBJET', 'Quick question about {PODCAST}',
   'MarketForge Engine — objet du 1er mail. {PODCAST} = nom du podcast.'],
  ['MFE_MSG_FICHE', [
    'Hi {PODCAST} team,',
    '',
    "I'm Etienne, I run Listenly, a directory of B2B podcasts built for the way people now find shows: by asking ChatGPT, Perplexity or Google's AI for expert advice.",
    '',
    "I've just added {PODCAST} and put together a page for the show: {URL}",
    '',
    "It's free and it stays up. I'm curious though: is getting discovered through AI search something you're thinking about for the show?",
    '',
    '{OPTOUT}',
    '',
    'Best,',
    'Etienne Cugnet',
    'Listenly'
  ].join('\n'), 'MarketForge Engine — 1er mail (fiche du podcast). Variables : {PODCAST} {URL} {BOOKING} {OPTOUT}.'],
  ['MFE_MSG_REPONSES', [
    'Hi {PODCAST} team,',
    '',
    "I'm Etienne, I run Listenly, a directory of B2B podcasts built for the way people now find shows: by asking ChatGPT, Perplexity or Google's AI for expert advice.",
    '',
    "I've just added {PODCAST}, and I also indexed a few answers from your recent episodes, each linked to the exact minute it's said, so AI tools can quote your guests: {URL}",
    '',
    "It's free and it stays up. I'm curious though: is getting discovered through AI search something you're thinking about for the show?",
    '',
    '{OPTOUT}',
    '',
    'Best,',
    'Etienne Cugnet',
    'Listenly'
  ].join('\n'), 'MarketForge Engine — 1er mail quand des reponses ont ete extraites.'],
  ['MFE_MSG_RELANCE', [
    'Hi {PODCAST} team,',
    '',
    'Just floating this back up. Your Listenly page is live here: {URL}',
    '',
    "If AI search is on your radar, I'd be happy to show you in 15 minutes what's already bringing new listeners to similar shows: {BOOKING}",
    '',
    'If not, no worries at all.',
    '',
    'Best,',
    'Etienne'
  ].join('\n'), 'MarketForge Engine — relance (J+MFE_RELANCE_JOURS), dans le meme fil.'],
  ['MFE_MSG_OPTOUT', "If this isn't relevant, just let me know and I won't reach out again.",
   'MarketForge Engine — phrase de desinscription inseree a la place de {OPTOUT}.'],
];

function mfeMsg_(key) {
  var v = mfeReadSettings_()[key];
  if (v != null && String(v).trim()) return String(v);
  for (var i = 0; i < MFE_MSG_DEFAULTS.length; i++) if (MFE_MSG_DEFAULTS[i][0] === key) return MFE_MSG_DEFAULTS[i][1];
  return '';
}

function installer() {
  var sh = mfeSheet_();
  mfeMigrateOldSettings_(sh);
  mfeEnsureSettings_();
  mfeHisto_();
  var props = PropertiesService.getScriptProperties();
  if (!props.getProperty('MFE_SECRET')) props.setProperty('MFE_SECRET', Utilities.getUuid().replace(/-/g, ''));
  Logger.log('SECRET du pont GitHub : %s  -> ajoute "?secret=%s" a la fin de l\'URL de l\'application web.',
             props.getProperty('MFE_SECRET'), props.getProperty('MFE_SECRET'));
  ScriptApp.getProjectTriggers().forEach(function (t) {
    var f = t.getHandlerFunction();
    if (f === 'marketforgeEngineQuotidien' || f === 'mfeOnOpen') ScriptApp.deleteTrigger(t);
  });
  // Menu "MarketForge Engine" : declencheur d'ouverture installable (ne remplace pas l'onOpen existant)
  ScriptApp.newTrigger('mfeOnOpen').forSpreadsheet(mfeSS_()).onOpen().create();
  mfeOnOpen();
  // Toutes les heures : les prospects arrivent dans le tableau au plus 1 h apres chaque run GitHub
  // (instantanement si le pont application web est branche). Le plafond d'envois reste journalier.
  ScriptApp.newTrigger('marketforgeEngineQuotidien').timeBased().everyHours(1).create();
  marketforgeEngineQuotidien();
}

function marketforgeEngineQuotidien() {
  var sh = mfeSheet_();
  var cfg = mfeSettings_();
  var added = mfeImport_(sh, null);
  if (cfg.EMAIL_TEST) {  // mode test : ne touche ni aux statuts ni au quota
    Logger.log('MODE TEST : %s mail(s) test envoye(s) a %s', mfeSendTest_(sh, cfg.EMAIL_TEST), cfg.EMAIL_TEST);
    return;
  }
  var sent = cfg.ENVOI_AUTO ? mfeSend_(sh, cfg) : 0;
  var replies = mfeCheckReplies_(sh);
  var relances = (cfg.ENVOI_AUTO && cfg.RELANCE_JOURS > 0) ? mfeFollowUp_(sh, cfg.RELANCE_JOURS) : 0;
  Logger.log('MarketForge Engine : %s ajoute(s), %s envoye(s), %s reponse(s), %s relance(s)', added, sent, replies, relances);
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
    var n = p.moments_count || 0;
    // Jamais de double contact : email deja present dans l'onglet Prospection (ancienne machine)
    var dejaVu = prospection && prospection.createTextFinder(p.email).matchCase(false).findNext();
    rows.push([slug, p.podcast_name || slug, p.email, p.proof_url + (n > 0 ? '#answers' : ''), n,
               new Date(), dejaVu ? 'Deja en prospection' : 'Pret', '', '', '', '', '']);
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
  var steps = [30, 80, 150, 300, 500, 1000];
  return Math.min(cfg.MAX_ENVOIS_JOUR, week < steps.length ? steps[week] : cfg.MAX_ENVOIS_JOUR);
}

function mfeSend_(sh, cfg, force) {
  var now = new Date(), h = now.getHours();
  if (!force && (h < cfg.H_START || h >= cfg.H_END)) return 0;   // hors plage horaire
  var daily = mfeDailyCap_(cfg);
  var today = now.toDateString();
  var rows = mfeRows_(sh);
  var sentToday = rows.filter(function (r) {
    return r.values[7] && new Date(r.values[7]).toDateString() === today;
  }).length;
  // Repartition sur la plage : a l'heure h, on ne depasse pas la part proportionnelle du jour
  var span = cfg.H_END - cfg.H_START;
  var allowedSoFar = Math.ceil(daily * (h - cfg.H_START + 1) / span);
  var budget = Math.max(0, Math.min(daily, allowedSoFar) - sentToday);
  if (force) budget = force === true ? Math.max(0, daily - sentToday) : Math.min(force, Math.max(0, daily - sentToday));
  var sent = 0;
  rows.forEach(function (r) {
    if (sent >= budget || r.values[6] !== 'Pret') return;
    var d = mfeDraft_(r.values);
    try {
      var threadId = mfeMail_(r.values[2], d[0], d[1]);
      sh.getRange(r.row, 7, 1, 5).setValues([['Envoye', new Date(), '', '', threadId]]);
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
  if (props.getProperty('MFE_TEST_DONE') === to) return 0;   // une seule fois par adresse test
  var n = 0, done = {};
  mfeRows_(sh).forEach(function (r) {
    var kind = Number(r.values[4]) > 0 ? 'reponses' : 'fiche';
    if (done[kind] || r.values[6] !== 'Pret') return;
    var d = mfeDraft_(r.values);
    GmailApp.sendEmail(to, '[TEST] ' + d[0], '(Mail qui partirait a : ' + r.values[2] + ')\n\n' + d[1], mfeFromOpts_());
    done[kind] = true; n++;
  });
  props.setProperty('MFE_TEST_DONE', to);
  return n;
}

// ---------- 3. Reponses + relance ----------
function mfeCheckReplies_(sh) {
  var n = 0;
  mfeRows_(sh).forEach(function (r) {
    var status = r.values[6], threadId = r.values[10];
    if (!threadId || (status !== 'Envoye' && status !== 'Relance')) return;
    var thread = GmailApp.getThreadById(threadId);
    if (!thread) return;
    var fromThem = thread.getMessages().some(function (m) {
      return m.getFrom().toLowerCase().indexOf(String(r.values[2]).toLowerCase()) !== -1;
    });
    if (fromThem) { sh.getRange(r.row, 7).setValue('Repondu'); sh.getRange(r.row, 10).setValue(new Date()); n++; }
  });
  return n;
}

function mfeFollowUp_(sh, days) {
  var n = 0, limit = Date.now() - days * 86400000;
  mfeRows_(sh).forEach(function (r) {
    if (r.values[6] !== 'Envoye' || !r.values[7] || new Date(r.values[7]).getTime() > limit || !r.values[10]) return;
    var thread = GmailApp.getThreadById(r.values[10]);
    if (!thread) return;
    thread.replyAll(mfeFill_(mfeMsg_('MFE_MSG_RELANCE'), mfeVars_(r.values)), mfeFromOpts_());
    sh.getRange(r.row, 7).setValue('Relance');
    sh.getRange(r.row, 9).setValue(new Date());
    n++;
  });
  return n;
}

// ---------- Utilitaires ----------
function mfeMail_(to, subject, body) {
  var opts = mfeFromOpts_();
  GmailApp.sendEmail(to, subject, body, opts);
  Utilities.sleep(1500);
  var threads = GmailApp.search('to:' + to + ' subject:"' + subject.replace(/"/g, '') + '" in:sent', 0, 1);
  return threads.length ? threads[0].getId() : '';
}

function mfeFromOpts_() {
  var opts = { name: MFE.NAME, replyTo: MFE.FROM };
  if (GmailApp.getAliases().indexOf(MFE.FROM) !== -1) opts.from = MFE.FROM;
  return opts;
}

function mfeVars_(values) {
  return { PODCAST: values[1], URL: values[3], BOOKING: MFE.BOOKING, OPTOUT: mfeMsg_('MFE_MSG_OPTOUT') };
}

function mfeFill_(tpl, v) {
  return String(tpl).replace(/\{(\w+)\}/g, function (m, k) { return v[k] != null ? v[k] : m; })
    .replace(/\n{3,}/g, '\n\n').trim();
}

function mfeDraft_(values) {  // [objet, corps] du 1er mail
  var v = mfeVars_(values);
  var body = Number(values[4]) > 0 ? mfeMsg_('MFE_MSG_REPONSES') : mfeMsg_('MFE_MSG_FICHE');
  return [mfeFill_(mfeMsg_('MFE_MSG_OBJET'), v), mfeFill_(body, v)];
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
    return mfeJson_({ ok: true, reglages: mfeReadSettings_(), prospects: rows, historique: last });
  }
  return mfeJson_({ ok: false, error: 'action inconnue (config | status)' });
}

function doPost(e) {
  var body = {};
  try { body = JSON.parse(e.postData.contents); } catch (err) { return mfeJson_({ ok: false, error: 'JSON invalide' }); }
  var p = (e && e.parameter) || {};
  if (!mfeAuth_(p.secret || body.secret)) return mfeJson_({ ok: false, error: 'secret invalide' });
  if (body.action !== 'report') return mfeJson_({ ok: false, error: 'action inconnue (report)' });

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
    });
    return mfeJson_({ ok: true, lignes_ajoutees: added });
  } finally { lock.releaseLock(); }
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
    .addItem('Envoyer un test (à moi)', 'mfeMenuTest')
    .addItem('Test limité (3 vrais e-mails maintenant)', 'mfeMenuTestLimite')
    .addItem('Traiter la file maintenant (envoi hors horaires)', 'mfeMenuTraiter')
    .addItem('Vérifier réponses + relances maintenant', 'mfeMenuRelances')
    .addSeparator()
    .addItem('Activer l’automatique (toutes les heures)', 'installer')
    .addItem('Créer / réparer les réglages MFE_*', 'mfeMenuReglages')
    .addItem('Enregistrer le token GitHub', 'mfeMenuToken')
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
  var v = mfeVars_(exemple), objet = mfeFill_(mfeMsg_('MFE_MSG_OBJET'), v);
  GmailApp.sendEmail(moi, '[TEST 1/3 - premier mail] ' + objet, mfeFill_(mfeMsg_('MFE_MSG_FICHE'), v), mfeFromOpts_());
  GmailApp.sendEmail(moi, '[TEST 2/3 - avec reponses] ' + objet, mfeFill_(mfeMsg_('MFE_MSG_REPONSES'), v), mfeFromOpts_());
  GmailApp.sendEmail(moi, '[TEST 3/3 - relance] Re: ' + objet, mfeFill_(mfeMsg_('MFE_MSG_RELANCE'), v), mfeFromOpts_());
  mfeAlert_('3 mails test envoyes a ' + moi + '. Textes modifiables dans Reglages (lignes MFE_MSG_*). Expediteur : ' + (mfeFromOpts_().from || moi));
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
    if (t.getHandlerFunction() === 'marketforgeEngineQuotidien') ScriptApp.deleteTrigger(t);
  });
  mfeAlert_('Envoi automatique desactive (le menu reste disponible). Pour reactiver : "Activer l’automatique".');
}

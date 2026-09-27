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
  NAME: 'Etienne | MarketForge',
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
  ['MFE_RELANCE_JOURS', '4', 'MarketForge Engine — relance unique apres N jours sans reponse (0 = pas de relance).'],
];

var MFE_SUBJECT = '{{podcast}} is now listed on Listenly';
// Mail sans extraction : la preuve = la fiche du podcast sur Listenly
var MFE_BODY_FICHE =
  'Hi,\n\n' +
  'Quick heads-up: {{podcast}} has just been added to Listenly, a B2B podcast directory built so AI assistants ' +
  '(ChatGPT, Perplexity, Google AI Overviews) can find and recommend expert podcasts.\n\n' +
  'Your page is already live:\n{{proof}}\n\n' +
  "It's free. If you'd like to see how {{podcast}} can get more listeners and inbound from AI search, " +
  'happy to walk you through it in 15 minutes: {{booking}}\n\n' +
  'Best,\nEtienne\nMarketForge';
// Mail avec extraction (reponses indexees)
var MFE_BODY =
  'Hi,\n\n' +
  'Quick heads-up: {{podcast}} has just been added to Listenly, a podcast directory built so AI assistants ' +
  '(ChatGPT, Perplexity, Google AI Overviews) can find and cite real podcast expertise.\n\n' +
  'We went one step further and indexed actual answers from your recent episodes, each linked to the exact ' +
  'moment it is said:\n{{proof}}\n\n' +
  "It's free and already live. If you'd like to see how this can bring {{podcast}} more listeners and inbound " +
  'from AI search, happy to walk you through it in 15 minutes: {{booking}}\n\n' +
  'Best,\nEtienne\nMarketForge';
var MFE_FOLLOWUP =
  'Hi,\n\nJust bumping this in case it got buried. The {{podcast}} page is live here: {{proof}}\n\n' +
  'Worth a quick 15-min call? {{booking}}\n\nBest,\nEtienne';

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
    if (t.getHandlerFunction() === 'marketforgeEngineQuotidien') ScriptApp.deleteTrigger(t);
  });
  // Toutes les heures : les prospects arrivent dans le tableau au plus 1 h apres chaque run GitHub
  // (instantanement si le pont application web est branche). Le plafond d'envois reste journalier.
  ScriptApp.newTrigger('marketforgeEngineQuotidien').timeBased().everyHours(1).create();
  marketforgeEngineQuotidien();
}

function marketforgeEngineQuotidien() {
  var sh = mfeSheet_();
  var cfg = mfeSettings_();
  var added = mfeImport_(sh, null);
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

function mfeSend_(sh, cfg) {
  var now = new Date(), h = now.getHours();
  if (h < cfg.H_START || h >= cfg.H_END) return 0;          // hors plage horaire
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
  var sent = 0;
  rows.forEach(function (r) {
    if (sent >= budget || r.values[6] !== 'Pret') return;
    var v = mfeVars_(r.values);
    var body = Number(r.values[4]) > 0 ? MFE_BODY : MFE_BODY_FICHE;
    try {
      var threadId = mfeMail_(r.values[2], mfeFill_(MFE_SUBJECT, v), mfeFill_(body, v));
      sh.getRange(r.row, 7, 1, 5).setValues([['Envoye', new Date(), '', '', threadId]]);
      sent++;
    } catch (e) {
      sh.getRange(r.row, 7).setValue('Erreur');
      sh.getRange(r.row, 12).setValue(String(e).slice(0, 200));
    }
  });
  return sent;
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
    thread.replyAll(mfeFill_(MFE_FOLLOWUP, mfeVars_(r.values)), mfeFromOpts_());
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
  var opts = { name: MFE.NAME };
  if (GmailApp.getAliases().indexOf(MFE.FROM) !== -1) opts.from = MFE.FROM;
  return opts;
}

function mfeVars_(values) {
  return { podcast: values[1], proof: values[3], booking: MFE.BOOKING };
}

function mfeFill_(tpl, v) {
  return tpl.replace(/\{\{(\w+)\}\}/g, function (_, k) { return v[k] != null ? v[k] : ''; });
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
  var missing = MFE_DEFAULTS.filter(function (d) { return !(d[0] in have); });
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

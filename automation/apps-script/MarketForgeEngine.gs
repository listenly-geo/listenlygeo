/**
 * MarketForge Engine — branchement Google Sheet + mail (27/09/2026)
 *
 * A coller dans le projet Apps Script du Sheet de prospection podcasts (1b53cWGiz6iOuakpotw_Ck4bQBeIMJa3hfq5gP2mFiT4)
 * (Extensions > Apps Script > + > Script > nommer "MarketForgeEngine"), sans toucher aux autres fichiers.
 *
 * Ce que ca fait, chaque jour :
 *  1. Lit la file du MarketForge Engine sur GitHub (queue.json).
 *  2. Ajoute dans l'onglet "MarketForge Engine" chaque podcast qui a un email ET une preuve
 *     (fiche N1 avec ses reponses extraites). Jamais de doublon.
 *  3. Envoie le mail "vous etes reference + preuve + RDV" (si ENVOI_AUTO = TRUE), puis 1 relance
 *     a J+RELANCE_JOURS s'il n'y a pas eu de reponse.
 *
 * Premiere utilisation : executer une fois installer() (cree l'onglet + le declencheur quotidien 9h).
 * Reglages : en haut de l'onglet "MarketForge Engine" (ENVOI_AUTO, MAX_ENVOIS_JOUR...).
 */

var MFE = {
  QUEUE_URL: 'https://raw.githubusercontent.com/listenly-geo/listenlygeo/main/automation/marketforge_engine/queue.json',
  SHEET: 'MarketForge Engine',
  FROM: 'etienne.cugnet@marketforge.fr',           // utilise si c'est un alias Gmail du compte qui execute le script
  NAME: 'Etienne | MarketForge',
  BOOKING: 'https://cal.com/etienne-marketforge/podcast-distribution-strategy-call',
  HEADER_ROW: 6,                                    // lignes 1-4 = reglages, ligne 6 = en-tetes
  COLS: ['Slug', 'Podcast', 'Email', 'Preuve (fiche N1)', 'Q/R extraites', 'Ajoute le', 'Statut',
         'Envoye le', 'Relance le', 'Reponse', 'Thread ID', 'Notes'],
};

var MFE_DEFAULTS = [
  ['ENVOI_AUTO', 'FALSE', 'TRUE = envoie les mails automatiquement. FALSE = prepare seulement (statut "Pret").'],
  ['MAX_ENVOIS_JOUR', '20', 'Plafond de premiers mails par jour.'],
  ['RELANCE_JOURS', '4', 'Relance unique apres N jours sans reponse (0 = pas de relance).'],
];

var MFE_SUBJECT = '{{podcast}} is now indexed on Listenly';
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
  'Hi,\n\nJust bumping this in case it got buried. The {{podcast}} answers page is live here: {{proof}}\n\n' +
  'Worth a quick 15-min call? {{booking}}\n\nBest,\nEtienne';

function installer() {
  mfeSheet_();
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'marketforgeEngineQuotidien') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('marketforgeEngineQuotidien').timeBased().everyDays(1).atHour(9).create();
  marketforgeEngineQuotidien();
}

function marketforgeEngineQuotidien() {
  var sh = mfeSheet_();
  var cfg = mfeSettings_(sh);
  var added = mfeImport_(sh);
  var sent = cfg.ENVOI_AUTO ? mfeSend_(sh, cfg.MAX_ENVOIS_JOUR) : 0;
  var replies = mfeCheckReplies_(sh);
  var relances = (cfg.ENVOI_AUTO && cfg.RELANCE_JOURS > 0) ? mfeFollowUp_(sh, cfg.RELANCE_JOURS) : 0;
  Logger.log('MarketForge Engine : %s ajoute(s), %s envoye(s), %s reponse(s), %s relance(s)', added, sent, replies, relances);
}

// ---------- 1. Import depuis queue.json ----------
function mfeImport_(sh) {
  var res = UrlFetchApp.fetch(MFE.QUEUE_URL + '?t=' + Date.now(), { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) throw new Error('queue.json illisible : HTTP ' + res.getResponseCode());
  var podcasts = (JSON.parse(res.getContentText()).podcasts) || {};
  var known = {};
  mfeRows_(sh).forEach(function (r) { known[r.values[0]] = true; });
  var rows = [];
  Object.keys(podcasts).forEach(function (slug) {
    var p = podcasts[slug];
    if (known[slug] || !p.email || !p.proof_url || !(p.moments_count > 0)) return;
    rows.push([slug, p.podcast_name || slug, p.email, p.proof_url + '#answers', p.moments_count,
               new Date(), 'Pret', '', '', '', '', '']);
  });
  if (rows.length) sh.getRange(sh.getLastRow() + 1, 1, rows.length, MFE.COLS.length).setValues(rows);
  return rows.length;
}

// ---------- 2. Premier mail ----------
function mfeSend_(sh, max) {
  var sent = 0;
  mfeRows_(sh).forEach(function (r) {
    if (sent >= max || r.values[6] !== 'Pret') return;
    var v = mfeVars_(r.values);
    try {
      var threadId = mfeMail_(r.values[2], mfeFill_(MFE_SUBJECT, v), mfeFill_(MFE_BODY, v));
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

function mfeSettings_(sh) {
  var vals = sh.getRange(2, 1, MFE_DEFAULTS.length, 2).getValues();
  var cfg = {};
  vals.forEach(function (r) { cfg[r[0]] = r[1]; });
  return {
    ENVOI_AUTO: String(cfg.ENVOI_AUTO).toUpperCase() === 'TRUE',
    MAX_ENVOIS_JOUR: parseInt(cfg.MAX_ENVOIS_JOUR, 10) || 20,
    RELANCE_JOURS: parseInt(cfg.RELANCE_JOURS, 10) || 0,
  };
}

function mfeSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet() || SpreadsheetApp.openById('1b53cWGiz6iOuakpotw_Ck4bQBeIMJa3hfq5gP2mFiT4');
  var sh = ss.getSheetByName(MFE.SHEET);
  if (sh) return sh;
  sh = ss.insertSheet(MFE.SHEET);
  sh.getRange(1, 1).setValue('REGLAGES MarketForge Engine').setFontWeight('bold');
  sh.getRange(2, 1, MFE_DEFAULTS.length, 3).setValues(MFE_DEFAULTS);
  sh.getRange(MFE.HEADER_ROW, 1, 1, MFE.COLS.length).setValues([MFE.COLS]).setFontWeight('bold').setBackground('#eef3fd');
  sh.setFrozenRows(MFE.HEADER_ROW);
  return sh;
}

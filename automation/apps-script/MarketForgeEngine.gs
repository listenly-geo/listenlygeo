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
         'Envoye le', 'Relance le', 'Reponse', 'Thread ID', 'Notes', 'Page Listenly', 'Hote'],
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
  ['MFE_MAX_REBONDS', '3', 'MarketForge Engine — au-dela de N mails bloques/rebonds sur 3 jours, l\'envoi automatique se met en pause (MFE_ENVOI_AUTO passe a FALSE).'],
  ['MFE_RELANCE_JOURS', '4', 'MarketForge Engine — relance unique apres N jours sans reponse (0 = pas de relance).'],
];

// ---------- Messages (modifiables dans l'onglet Reglages, cles MFE_MSG_*) ----------
// Style : court, a la premiere personne, une seule question, texte brut (pas de gras, pas d'emoji).
// Variables : {PODCAST} {URL} {BOOKING} {OPTOUT}
var MFE_MSG_VERSION = '7';   // incremente -> les textes MFE_MSG_* de Reglages sont remis a jour a l'installation
var MFE_FIRST_MAIL = [
  'Hi {NAME},',
  '',
  'I\u2019m Etienne, founder of Marketforge, a content repurposing agency.',
  '',
  'I\u2019m reaching out because I referenced your podcast {PODCAST} on Listenly, our directory designed to help podcasts gain visibility across Google and AI search engines.',
  '',
  'Here is your profile to review:',
  '{URL}',
  '',
  'On average, a podcast episode contains 15+ answers your prospects are already searching for on Google and AI \u2014 content that can be turned into ongoing visibility without producing anything new or changing your current strategy.',
  '',
  'I\u2019d be curious to know: is your content flow already helping grow your company\u2019s visibility on Google and AI?',
  '',
  'Best,',
  'Etienne Cugnet',
  'Founder, Listenly / Marketforge'
].join('\n');
var MFE_MSG_DEFAULTS = [
  ['MFE_MSG_OBJET', 'Regarding {PODCAST} – Listenly AI directory',
   'MarketForge Engine — objet du 1er mail. {PODCAST} = nom du podcast.'],
  ['MFE_MSG_FICHE', MFE_FIRST_MAIL,
   'MarketForge Engine — 1er mail. Variables : {NAME} (hote, sinon "{PODCAST} team") {PODCAST} {URL} (fiche N1 du podcast) {BOOKING} {OPTOUT}.'],
  ['MFE_MSG_REPONSES', MFE_FIRST_MAIL,
   'MarketForge Engine — 1er mail quand des reponses ont ete extraites (meme modele par defaut).'],
  ['MFE_MSG_RELANCE', [
    'Hi {NAME},',
    '',
    'Just following up regarding {PODCAST} \u2014 we recently added it to Listenly to help improve its visibility across Google and AI search.',
    '',
    'Could you confirm that everything on the profile looks correct?',
    '{URL}',
    '',
    'Best,',
    'Etienne'
  ].join('\n'), 'MarketForge Engine — relance (J+MFE_RELANCE_JOURS), dans le meme fil.'],
  ['MFE_MSG_SIGNATURE', '',
   'MarketForge Engine — lignes ajoutees automatiquement a la fin du 1er mail ET de la relance (ex. lien LinkedIn). Vide = rien. Gmail n\'ajoute PAS la signature Workspace aux mails envoyes par script.'],
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
    if (mfeEmailProblem_(p.email)) return;   // anti-rebond : jamais importe si l'adresse est douteuse
    var n = p.moments_count || 0;
    // Jamais de double contact : email deja present dans l'onglet Prospection (ancienne machine)
    var dejaVu = prospection && prospection.createTextFinder(p.email).matchCase(false).findNext();
    rows.push([slug, p.podcast_name || slug, p.email, p.proof_url + (n > 0 ? '#answers' : ''), n,
               new Date(), dejaVu ? 'Deja en prospection' : 'Pret', '', '', '', '', '',
               p.listenly_url || '', p.host_name || '']);
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
    var why = mfeEmailProblem_(r.values[2]);   // anti-rebond : verifie l'adresse juste avant l'envoi
    if (why) {
      sh.getRange(r.row, 7).setValue('Email invalide');
      sh.getRange(r.row, 12).setValue('Non envoye (anti-rebond) : ' + why);
      return;
    }
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
    var msgs = thread.getMessages();
    var bounce = msgs.some(function (m) { return /mailer-daemon|postmaster/i.test(m.getFrom()); });
    if (bounce) {  // mail bloque / adresse invalide : jamais de relance
      sh.getRange(r.row, 7).setValue('Rebond');
      mfeRememberBounce_(r.values[2]);
      sh.getRange(r.row, 12).setValue('Bloque ou refuse par le serveur du destinataire');
      mfeBounceGuard_(sh);
      return;
    }
    var fromThem = msgs.some(function (m) {
      return m.getFrom().toLowerCase().indexOf(String(r.values[2]).toLowerCase()) !== -1;
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
  'riverside.fm', 'zencast.fm', 'whooshkaa.com', 'example.com', 'example.org', 'test.com', 'domain.com', 'email.com'];
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
  var bounced = JSON.parse(PropertiesService.getScriptProperties().getProperty('MFE_BOUNCED_DOMAINS') || '{}');
  var perso = /^(gmail|googlemail|yahoo|outlook|hotmail|live|icloud|me|aol|proton|protonmail)\./;
  if (bounced[domain] && !perso.test(domain)) return 'domaine deja en rebond (' + domain + ')';
  if (!mfeDomainAcceptsMail_(domain)) return 'domaine sans serveur mail (' + domain + ')';
  return '';
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

function mfeFollowUp_(sh, days) {
  var n = 0, limit = Date.now() - days * 86400000;
  mfeRows_(sh).forEach(function (r) {
    if (r.values[6] !== 'Envoye' || !r.values[7] || new Date(r.values[7]).getTime() > limit || !r.values[10]) return;
    var thread = GmailApp.getThreadById(r.values[10]);
    if (!thread) return;
    thread.replyAll(mfeWithSignature_(mfeFill_(mfeMsg_('MFE_MSG_RELANCE'), mfeVars_(r.values))), mfeFromOpts_());
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

// "BriteVibe Podcast: Live Brite, Live Bold..." -> "BriteVibe Podcast"
function mfeShortName_(name) {
  var full = String(name || '').trim();
  var cut = full.split(/\s*[:|–—]\s*|\s+-\s+|\s*\(/)[0].trim();
  if (cut.length < 3) cut = full;
  return cut.length > 60 ? cut.slice(0, 60).replace(/\s+\S*$/, '') : cut;
}

function mfeVars_(values) {
  return { PODCAST: mfeShortName_(values[1]), URL: values[3], LINK: values[3], LISTENLY: values[12] || values[3],
           NAME: mfeName_(values[13], mfeShortName_(values[1])), BOOKING: MFE.BOOKING, OPTOUT: mfeMsg_('MFE_MSG_OPTOUT') };
}

function mfeFill_(tpl, v) {
  return String(tpl).replace(/\{(\w+)\}/g, function (m, k) { return v[k] != null ? v[k] : m; })
    .replace(/\n{3,}/g, '\n\n').trim();
}

// Signature (onglet Reglages, MFE_MSG_SIGNATURE) ajoutee en bas du mail, texte brut (meilleure delivrabilite)
function mfeWithSignature_(body) {
  var sig = String(mfeReadSettings_().MFE_MSG_SIGNATURE || '').trim();
  return sig ? body + '\n' + sig : body;
}

function mfeDraft_(values) {  // [objet, corps] du 1er mail
  var v = mfeVars_(values);
  var body = Number(values[4]) > 0 ? mfeMsg_('MFE_MSG_REPONSES') : mfeMsg_('MFE_MSG_FICHE');
  return [mfeFill_(mfeMsg_('MFE_MSG_OBJET'), v), mfeWithSignature_(mfeFill_(body, v))];
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
  GmailApp.sendEmail(moi, '[TEST 1/3 - premier mail] ' + objet, mfeWithSignature_(mfeFill_(mfeMsg_('MFE_MSG_FICHE'), v)), mfeFromOpts_());
  GmailApp.sendEmail(moi, '[TEST 2/3 - avec reponses] ' + objet, mfeWithSignature_(mfeFill_(mfeMsg_('MFE_MSG_REPONSES'), v)), mfeFromOpts_());
  GmailApp.sendEmail(moi, '[TEST 3/3 - relance] Re: ' + objet, mfeWithSignature_(mfeFill_(mfeMsg_('MFE_MSG_RELANCE'), v)), mfeFromOpts_());
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

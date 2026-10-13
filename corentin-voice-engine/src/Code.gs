/**
 * MACHINE DE PROSPECTION AUTONOME — CORENTIN AI VOICE
 *
 * Cycle quotidien (tout est automatique) :
 *  06h  Découverte : Claude (API + recherche web) trouve de nouveaux SaaS,
 *       le script vérifie chaque prospect (site, preuve, e-mail affiché sur
 *       une page officielle, doublons) puis l'ajoute à l'onglet Prospection.
 *  09h-17h (lun-ven)  Envoi du 1er mail aux prospects vérifiés (limite/jour).
 *  Relances J+4 et J+9, arrêt si réponse ou rebond.
 *  08h  Rapport quotidien envoyé par e-mail.
 *
 * Tout se règle dans l'onglet « Réglages » (messages, segments, limites).
 * La clé API se saisit via le menu Prospection (jamais dans le code).
 */

const CONFIG = Object.freeze({
  SPREADSHEET_ID: '1M5bSX3-Iq2Om8UXkOw3rAZUgKrnVrkwFAmnfzZOBHkY',
  SHEET_NAME: 'Prospection',
  SETTINGS_SHEET: 'Réglages',
  HEADER_ROW: 5,
  FIRST_DATA_ROW: 6,
  SENDER_ALIAS: 'partnership.voiceover@corentin-cugnet.fr',
  SENDER_NAME: 'Corentin Cugnet',
  IMAGE_FILE_ID: '1nIpD4SHvursmVmFHxvRrwApkOF7sQKOz',
  SAMPLES_URL: 'https://corentinvoice.live/',
  DAILY_LIMIT: 10,
  FOLLOW_UP_1_DAYS: 4,
  FOLLOW_UP_2_DAYS: 9,
  TIME_ZONE: 'Europe/Paris',
  API_URL: 'https://api.anthropic.com/v1/messages',
  API_VERSION: '2023-06-01',
  // À incrémenter à chaque collage d'une nouvelle version du code dans
  // l'éditeur Apps Script. Le rapport quotidien compare cette valeur à la
  // dernière vue pour signaler qu'une mise à jour a eu lieu (et donc vérifier
  // que le comportement correspond bien à ce qui était attendu).
  CODE_VERSION: '2026-10-13-report-daily-planned-count'
});

const VOICE_ID = 'IHngRooVccHyPqB4uQkG';

const MACHINE_HANDLERS = [
  'processProspectionMachine',
  'discoverProspectsDaily',
  'sendDailyReport'
];

// ---------------------------------------------------------------
// RÉGLAGES PAR DÉFAUT (recopiés dans l'onglet « Réglages »)
// ---------------------------------------------------------------

const DEFAULT_SETTINGS = [
  ['MASTER_PAUSE', 'TRUE',
    '⏸ INTERRUPTEUR GÉNÉRAL. TRUE = AUCUN envoi n’est fait par ce moteur, ni premier mail ni relance, même si des lignes sont cochées « Envoyer » ou « À relancer » (la détection des réponses/rebonds continue, sans danger). FALSE = fonctionnement normal selon les autres réglages ci-dessous.'],
  ['AUTO_SEND', 'TRUE',
    'TRUE = les prospects vérifiés sont envoyés sans validation. FALSE = ils sont ajoutés mais non cochés (validation manuelle).'],
  ['DAILY_LIMIT', '100', 'Nombre maximum de premiers e-mails par jour (~100 = quota Gmail personnel via Apps Script).'],
  ['FOLLOWUP_2_ENABLED', 'FALSE', 'TRUE = envoie la relance 2 (J+9). FALSE = une seule relance (J+4), puis arrêt du suivi.'],
  ['MAX_SENDS_PER_RUN', '15', 'Premiers e-mails envoyés au maximum par passage horaire automatique (étale les envois sur la journée au lieu de tout envoyer d’un coup).'],
  ['MAX_FOLLOWUPS_PER_RUN', '10', 'Relances (classiques + intégration) envoyées au maximum par passage horaire automatique. Évite qu’un gros lot de lignes arrivant au même seuil J+X ne parte toutes en rafale le même jour.'],
  ['SEND_DELAY_MS', '18000', 'Délai en millisecondes entre deux envois consécutifs dans un même passage (évite un pattern de rafale/spam). 18000 = 18 secondes.'],
  ['WEEKDAYS_ONLY', 'TRUE', 'TRUE = envois et relances du lundi au vendredi uniquement.'],
  ['SEND_START_HOUR', '9', 'Heure de début des envois (heure de Paris).'],
  ['SEND_END_HOUR', '17', 'Heure de fin des envois (heure de Paris, exclue).'],
  ['MAX_BOUNCES_PAUSE', '3', "Nombre de rebonds sur 3 jours qui met les nouveaux envois en pause."],
  ['EMAIL_VERIFY_ENABLED', 'FALSE',
    'TRUE = chaque e-mail est vérifié via l’API MyEmailVerifier juste avant le premier envoi ; s’il est invalide, aucun envoi n’est fait (évite le rebond). FALSE = aucune vérification, comportement d’avant.'],
  ['EMAIL_VERIFY_API_KEY', '',
    'Clé API MyEmailVerifier (https://client.myemailverifier.com). Laisser vide pour désactiver même si EMAIL_VERIFY_ENABLED = TRUE.'],
  ['REPLY_AGENT_AUTO_SEND', 'TRUE',
    'TRUE = l’IA envoie elle-même les réponses à confiance élevée (après le délai aléatoire), seules les réponses incertaines passent en validation manuelle. FALSE = TOUTE réponse générée par l’IA reste en brouillon « À valider manuellement », jamais envoyée automatiquement.'],
  ['INTEGRATION_REMINDER_ENABLED', 'TRUE',
    'TRUE = relance automatiquement (à J+7 puis J+14 après leur réponse) les prospects qui ont répondu mais n’ont jamais coché « Voix ajoutée (confirmée) ». FALSE = aucune relance de ce type.'],
  ['INTEGRATION_REMINDER_J1', '7', 'Jours après leur réponse avant le 1er rappel « où en êtes-vous ? ».'],
  ['INTEGRATION_REMINDER_J2', '14', 'Jours après leur réponse avant le rappel final.'],
  ['TPL_INTEGRATION_FU1',
    'Hi {SAAS} team,\n\nJust checking in — has the integration of my French voice moved ' +
    'forward on your side? Happy to help with anything needed (Voice ID, samples, ' +
    'technical details).\n\nBest,',
    'Relance J+7 après une réponse sans confirmation d’intégration.'],
  ['TPL_INTEGRATION_FU2',
    'Hi {SAAS} team,\n\nFollowing up one last time — is the French voice live yet, or is ' +
    'something blocking the integration on your side? A quick update either way would ' +
    'be great.\n\nBest,',
    'Relance finale J+14 après une réponse sans confirmation d’intégration.'],
  ['TEST_MAX_SENDS', '3', 'Nombre maximum d e-mails réels envoyés par le bouton TEST COMPLET.'],
  ['DISCOVERY_PER_CALL', '3', 'Prospects demandés à Claude par appel.'],
  ['DISCOVERY_MAX_CALLS', '3', 'Nombre d appels de découverte par jour (un segment par appel).'],
  ['MODEL', 'claude-sonnet-5', 'Modèle utilisé pour la découverte.'],
  ['FORMAT_ENABLED', 'TRUE',
    'TRUE = les premiers e-mails reçoivent des mots en gras et 2 émojis. FALSE = texte simple.'],
  ['FORMAT_BOLD', 'French voice-over artist|ElevenLabs Voice ID|technical sheet with audio samples',
    'Expressions mises en gras (première apparition), séparées par |. Doivent exister dans le message.'],
  ['FORMAT_EMOJI_1', '🎙️', 'Émoji placé devant « Corentin AI Voice » dans la signature.'],
  ['FORMAT_EMOJI_2', '🎧', 'Émoji placé devant le premier lien corentinvoice.live du texte.'],
  ['SUBJECT_MAIN', 'Question concerning my voice on your library',
    'Objet des premiers e-mails (Corentin présent, catalogue, import). {SAAS} = nom du SaaS.'],
  ['SUBJECT_NEWSTACK', 'Question concerning my voice on your platform',
    'Objet quand rien n est prouvé sur le SaaS.'],
  ['REPORT_TO', '', 'Adresse du rapport quotidien (vide = compte Google du script).'],
  ['BLOCKLIST_DOMAINS', '', 'Domaines à ne jamais contacter, séparés par des virgules.'],
  ['OPTOUT_LINE', "Looking forward to your reply. Feel free to let me know if you need any more information.",
    'Phrase de clôture insérée à la place de {OPTOUT}.'],
  ['SEGMENT_1', 'API de génération vidéo automatisée (création et rendu programmatique, templates) | English, French', 'Segment | langues/marchés. Un segment par appel, en rotation.'],
  ['SEGMENT_2', 'API vidéo automatisée | German, Dutch, Norwegian, Italian, Spanish', ''],
  ['SEGMENT_3', 'Générateurs de vidéos UGC et publicités avec avatars | English, French, Spanish', ''],
  ['SEGMENT_4', 'Vidéos faceless, Shorts, Reels et TikTok automatisés | English, Turkish, Vietnamese', ''],
  ['SEGMENT_5', 'Texte, article, URL, RSS ou catalogue produit vers vidéo avec voix off | Romanian, Croatian, Malay', ''],
  ['SEGMENT_6', 'Vidéos e-commerce et démonstrations produit avec voix off | Arabic, Hindi, Tamil, Korean', ''],
  ['SEGMENT_7', 'Plateformes avec catalogue de voix TTS ou voice_id ElevenLabs externe | English, French, German', ''],
  // Les 4 modèles ci-dessous sont recopiés mot pour mot depuis la version
  // validée et actuellement live dans l'onglet Réglages (celle testée et
  // approuvée le 11/10). L'ancienne formulation via makeTemplate_() (« I
  // record French voice-overs... in a natural, young and dynamic style »)
  // a été retirée le 12/10 : elle laissait penser au destinataire que
  // Corentin demandait un ajout de sa voix à titre personnel plutôt qu'un
  // partenariat, ce qui créait de la confusion dans les réponses reçues.
  ['TPL_PRESENT',
    'Subject: French voice for {SAAS}\n\nHi {SAAS} team,\n\nI\'m Corentin Cugnet, a French voice-over artist. I noticed my voice is already in your voice library, thank you. I would like to make it easier for your French-speaking users to find it.\n\nCould I send a short sample script or listing assets to help users discover it? I\'ve put a technical sheet with audio samples and my ElevenLabs Voice ID ({VOICE_ID}) at your disposal: {URL}\n\nWho looks after your voice library on your side?\n\n{OPTOUT}\n\nBest,',
    '⚠️ NON UTILISÉ : tout SaaS "Exact confirmé" est banni de tout envoi (voir isPresentBanned_). Conservé pour référence uniquement, ne demande plus de mise en avant. Variables : {SAAS} {VOICE_ID} {URL} {OPTOUT}. Première ligne = Subject:'],
  ['TPL_CATALOG',
    'Subject: Partnership opportunity: French voice for {SAAS}\'s catalog\n\nHi {SAAS} team,\n\nI\'m Corentin Cugnet, a French voice-over artist specialized in social content, ads and short-form videos.\n\nI noticed my voice isn\'t in your voice catalog yet.\nDoes your platform support external or custom voices, such as an ElevenLabs Voice ID?\n\nMy voice, "Corentin, Young & Dynamic," has already been used across 10,000+ projects and SaaS platforms, is available in 15+ languages, and is built to perform at scale. You can find examples, performance highlights and my Voice ID here: {URL}\n\n{OPTOUT}\n\nBest,',
    'Message si le SaaS a un catalogue de voix / ElevenLabs et que Corentin est absent.'],
  ['TPL_IMPORTABLE',
    'Subject: Partnership opportunity: listing my French voice on {SAAS}\n\nHi {SAAS} team,\n\nI\'m Corentin Cugnet, a French voice-over artist specialized in social content, ads and short-form videos.\n\nI saw that your platform accepts external ElevenLabs voices — would it be possible to list mine as a preset for your French-speaking users?\n\nMy voice, "Corentin, Young & Dynamic," has already been used across 10,000+ projects and SaaS platforms, is available in 15+ languages, and is built to perform at scale. You can find examples, performance highlights and my Voice ID here: {URL}\n\n{OPTOUT}\n\nBest,',
    'Message si le SaaS accepte un voice_id externe.'],
  ['TPL_NEWSTACK',
    'Subject: Partnership opportunity: French voice for {SAAS}\n\nHi {SAAS} team,\n\nI\'m Corentin Cugnet, a French voice-over artist specialized in social content, ads and short-form videos.\n\nI didn\'t find my voice available on your platform yet. Does your platform support external or custom voices, such as an ElevenLabs Voice ID?\n\nMy voice, "Corentin, Young & Dynamic," has already been used across 10,000+ projects and SaaS platforms, is available in 15+ languages, and is built to perform at scale. You can find examples, performance highlights and my Voice ID here: {URL}\n\n{OPTOUT}\n\nBest,',
    'Message si rien n est prouvé sur le SaaS.'],
  ['FU1_LIBRARY',
    [
      'Hi {SAAS} team,',
      '',
      'I contacted you a few days ago regarding my French voice in {SAAS}\'s voice library. It\'s still not available there.',
      '',
      'Is it possible to integrate it on your side? It\'s already used in several SaaS voice libraries. The technical sheet with audio samples is here: {URL}',
      '',
      'Best,'
    ].join('\n'),
    'Relance 1 (J+4) : catalogue confirmé ou import possible.'],
  ['FU1_PLATFORM',
    [
      'Hi {SAAS} team,',
      '',
      'I contacted you a few days ago regarding the use of my French voice on {SAAS}.',
      '',
      'Is it possible to add an external voice on your side, such as an ElevenLabs Voice ID? The technical sheet with audio samples is here: {URL}',
      '',
      'Best,'
    ].join('\n'),
    'Relance 1 (J+4) : rien n est prouvé sur le SaaS.'],
  ['FU1_PRESENT',
    [
      'Hi {SAAS} team,',
      '',
      'Just a quick follow-up on my previous message.',
      '',
      'Best,'
    ].join('\n'),
    '⚠️ NON UTILISÉ : tout SaaS "Exact confirmé" est banni de toute relance (voir isPresentBanned_). Conservé pour référence uniquement.'],
  ['FU2_LIBRARY',
    [
      'Hi {SAAS} team,',
      '',
      'I haven\'t had a reply to my previous messages regarding my French voice in your library.',
      '',
      'Is integration possible, or is something blocking it on your side? A one-line answer is enough. If it\'s not a fit, just let me know and I won\'t write again.',
      '',
      'Best,'
    ].join('\n'),
    'Relance 2 (J+9) : catalogue confirmé ou import possible.'],
  ['FU2_PLATFORM',
    [
      'Hi {SAAS} team,',
      '',
      'I haven\'t had a reply to my previous messages regarding the use of my French voice on {SAAS}.',
      '',
      'Is integration possible, or is something blocking it on your side? A one-line answer is enough. If it\'s not a fit, just let me know and I won\'t write again.',
      '',
      'Best,'
    ].join('\n'),
    'Relance 2 (J+9) : rien n est prouvé sur le SaaS.'],
  ['FU2_PRESENT',
    [
      'Hi {SAAS} team,',
      '',
      'Last follow-up from me.',
      '',
      'Best,'
    ].join('\n'),
    '⚠️ NON UTILISÉ : tout SaaS "Exact confirmé" est banni de toute relance (voir isPresentBanned_). Conservé pour référence uniquement.']
];

let SETTINGS_CACHE_ = null;
let LAST_RAW_ = '';

function getSettingsMap_() {
  // Pas de cache entre exécutions : Apps Script peut parfois réutiliser une
  // instance "chaude" d'un passage à l'autre, ce qui faisait relire une
  // ancienne valeur de réglage (ex. un ancien texte de mail ou MASTER_PAUSE
  // resté sur l'ancienne valeur). On relit systématiquement la feuille pour
  // être toujours à jour — le coût est négligeable face à la fiabilité.
  const map = {};

  DEFAULT_SETTINGS.forEach(function (item) {
    map[item[0]] = String(item[1]);
  });

  try {
    const sheet = SpreadsheetApp
      .openById(CONFIG.SPREADSHEET_ID)
      .getSheetByName(CONFIG.SETTINGS_SHEET);

    if (sheet && sheet.getLastRow() > 1) {
      sheet
        .getRange(2, 1, sheet.getLastRow() - 1, 2)
        .getValues()
        .forEach(function (line) {
          const key = String(line[0] || '').trim();
          const value = line[1];

          if (key && value !== '' && value !== null) {
            map[key] = String(value);
          }
        });
    }
  } catch (error) {
    console.log('Réglages illisibles, valeurs par défaut : ' + safeError_(error));
  }

  SETTINGS_CACHE_ = map;
  return map;
}

function getSetting_(key) {
  const value = getSettingsMap_()[key];
  return value === undefined ? '' : value;
}

function getNumberSetting_(key, fallback) {
  const number = Number(String(getSetting_(key)).replace(',', '.'));
  return isFinite(number) && String(getSetting_(key)).trim() !== ''
    ? number
    : fallback;
}

function getBoolSetting_(key) {
  return /^(true|vrai|oui|yes|1)$/i.test(String(getSetting_(key)).trim());
}

function getSegments_() {
  const map = getSettingsMap_();

  return Object.keys(map)
    .filter(function (key) { return /^SEGMENT_\d+$/.test(key) && map[key]; })
    .sort(function (a, b) {
      return Number(a.split('_')[1]) - Number(b.split('_')[1]);
    })
    .map(function (key) {
      const parts = String(map[key]).split('|');
      return {
        label: parts[0].trim(),
        languages: (parts[1] || 'English').trim()
      };
    });
}

function setupSettingsSheet() {
  const ss = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
  let sheet = ss.getSheetByName(CONFIG.SETTINGS_SHEET);

  if (!sheet) {
    sheet = ss.insertSheet(CONFIG.SETTINGS_SHEET);
    sheet.getRange(1, 1, 1, 3)
      .setValues([['Clé', 'Valeur', 'Aide']])
      .setFontWeight('bold');
    sheet.setColumnWidth(1, 200);
    sheet.setColumnWidth(2, 700);
    sheet.setColumnWidth(3, 420);
  }

  const existing = {};

  if (sheet.getLastRow() > 1) {
    sheet
      .getRange(2, 1, sheet.getLastRow() - 1, 1)
      .getValues()
      .forEach(function (line) {
        existing[String(line[0]).trim()] = true;
      });
  }

  const missing = DEFAULT_SETTINGS.filter(function (item) {
    return !existing[item[0]];
  });

  if (missing.length) {
    const start = Math.max(sheet.getLastRow(), 1) + 1;

    sheet
      .getRange(start, 1, missing.length, 3)
      .setValues(missing.map(function (item) {
        return [item[0], item[1], item[2]];
      }));
  }

  sheet.getRange('B:B').setWrap(true).setVerticalAlignment('top');
  sheet.getRange('A:A').setVerticalAlignment('top');
  sheet.setFrozenRows(1);

  SETTINGS_CACHE_ = null;

  return missing.length;
}

// ---------------------------------------------------------------
// MENU ET ACTIVATION
// ---------------------------------------------------------------

function onOpen() {
  const ui = getUiSafely_();

  if (!ui) {
    console.log(
      'Ouvrez ou actualisez le Google Sheets pour afficher le menu Prospection.'
    );
    return;
  }

  ui.createMenu('Prospection')
    .addItem('🚀 LANCER LA MACHINE (recherche + mails + envoi)', 'launchMachine')
    .addItem('Actualiser l’onglet Rapport (data complète)', 'refreshReportTab')
    .addItem('Test limité (quelques e-mails)', 'runFullTest')
    .addSeparator()
    .addItem('Vérifier et activer', 'setupProspectionMachine')
    .addItem('Enregistrer la clé API Claude', 'saveApiKey')
    .addItem('Créer / réparer l’onglet Réglages', 'setupSettingsMenu')
    .addSeparator()
    .addItem('Découvrir des prospects maintenant', 'discoverProspectsNow')
    .addItem('Envoyer le rapport maintenant', 'sendDailyReportNow')
    .addItem(
      'Mettre en file les « À contacter » avec e-mail valide',
      'queueValidRows'
    )
    .addSeparator()
    .addItem('Compléter les messages courts', 'prepareMissingMessages')
    .addItem(
      'Actualiser les messages non envoyés',
      'refreshUnsentMessages'
    )
    .addItem('Envoyer un test', 'sendTestEmail')
    .addItem('Traiter la file maintenant', 'processProspectionMachineNow')
    .addItem(
      '🤝 Déplacer les partenaires confirmés maintenant',
      'migratePartnersNow'
    )
    .addSeparator()
    .addItem('Désactiver la machine', 'disableProspectionMachine')
    .addSeparator()
    .addItem('— Opportunités (moteur indépendant) —', 'noopOppMenuLabel_')
    .addItem('🧭 Activer le moteur Opportunités', 'setupOpportunitesMachine')
    .addItem(
      'Mettre en file les « À contacter » (Opportunités)',
      'queueOppValidRows'
    )
    .addItem('Envoyer un test (Opportunités)', 'sendTestEmailOpp')
    .addItem(
      'Traiter la file Opportunités maintenant',
      'processOpportunitesMachineNow'
    )
    .addItem('Désactiver le moteur Opportunités', 'disableOpportunitesMachine')
    .addSeparator()
    .addItem('— Réponse automatique IA (SaaS) —', 'noopReplyAgentMenuLabel_')
    .addItem(
      '1️⃣ Ignorer les réponses déjà reçues (à faire AVANT activation)',
      'skipExistingRepliesNow_'
    )
    .addItem('2️⃣ Activer la réponse automatique IA', 'setupReplyAgentMachine')
    .addItem('🧪 Tester une réponse IA (sans envoi)', 'testReplyAgent')
    .addItem('Traiter les réponses maintenant', 'processReplyAgentMachineNow')
    .addItem('Désactiver la réponse automatique IA', 'disableReplyAgentMachine')
    .addToUi();
}

// Élément de menu purement visuel (séparateur de section) : ne fait rien.
function noopReplyAgentMenuLabel_() {
  notify_(
    'Ceci est un séparateur de menu. Utilisez les éléments juste en dessous ' +
    'pour piloter la réponse automatique IA aux prospects SaaS qui ont répondu.'
  );
}

// Élément de menu purement visuel (séparateur de section) : ne fait rien.
function noopOppMenuLabel_() {
  notify_(
    'Ceci est un séparateur de menu. Utilisez les éléments juste en dessous ' +
    'pour piloter le moteur Opportunités (séparé du moteur SaaS principal).'
  );
}

function setupSettingsMenu() {
  const added = setupSettingsSheet();

  notify_(
    added
      ? 'Onglet Réglages prêt (' + added + ' réglage(s) ajouté(s)).'
      : 'Onglet Réglages déjà complet.'
  );
}

function saveApiKey() {
  const ui = getUiSafely_();

  if (!ui) {
    throw new Error('Utilisez le menu Prospection du Google Sheets.');
  }

  const answer = ui.prompt(
    'Clé API Claude',
    'Collez votre clé API Anthropic. Elle est stockée dans les propriétés ' +
    'du script, pas dans le Sheet.',
    ui.ButtonSet.OK_CANCEL
  );

  if (answer.getSelectedButton() !== ui.Button.OK) return;

  const key = String(answer.getResponseText() || '').trim();

  if (!/^sk-ant-/.test(key)) {
    ui.alert('Clé non reconnue (elle doit commencer par sk-ant-). Rien enregistré.');
    return;
  }

  PropertiesService.getScriptProperties().setProperty('ANTHROPIC_API_KEY', key);
  ui.alert('Clé API enregistrée.');
}

function installTriggers_() {
  removeMachineTriggers_();

  ScriptApp.newTrigger('processProspectionMachine')
    .timeBased()
    .everyHours(1)
    .create();

  ScriptApp.newTrigger('discoverProspectsDaily')
    .timeBased()
    .atHour(6)
    .everyDays(1)
    .inTimezone(CONFIG.TIME_ZONE)
    .create();

  ScriptApp.newTrigger('sendDailyReport')
    .timeBased()
    .atHour(8)
    .everyDays(1)
    .inTimezone(CONFIG.TIME_ZONE)
    .create();
}

function setupProspectionMachine() {
  assertSenderAlias_();
  setupSettingsSheet();
  assertRequiredHeaders_();
  installTriggers_();

  const hasKey = !!PropertiesService
    .getScriptProperties()
    .getProperty('ANTHROPIC_API_KEY');

  const weekdaysOnly = getBoolSetting_('WEEKDAYS_ONLY');
  const startHour = getNumberSetting_('SEND_START_HOUR', 9);
  const endHour = getNumberSetting_('SEND_END_HOUR', 17);

  notify_(
    'Machine activée : découverte à 6h, rapport à 8h, envois et relances ' +
    'chaque heure (' + (weekdaysOnly ? 'lun-ven' : '7j/7') + ', ' +
    startHour + 'h-' + endHour + 'h). ' +
    'Envoi automatique : ' + (getBoolSetting_('AUTO_SEND') ? 'OUI' : 'NON') + '. ' +
    'Limite : ' + getNumberSetting_('DAILY_LIMIT', CONFIG.DAILY_LIMIT) +
    ' premiers e-mails par jour.' +
    (hasKey
      ? ''
      : ' ATTENTION : clé API Claude absente, la découverte ne fonctionnera pas ' +
        '(menu Prospection > Enregistrer la clé API Claude).')
  );
}

function disableProspectionMachine() {
  removeMachineTriggers_();

  notify_(
    'Machine désactivée. Aucun traitement automatique ne sera lancé.'
  );
}

function removeMachineTriggers_() {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (MACHINE_HANDLERS.indexOf(trigger.getHandlerFunction()) !== -1) {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

// ---------------------------------------------------------------
// OUTILS MANUELS
// ---------------------------------------------------------------

function sendTestEmail() {
  assertSenderAlias_();

  const recipient = Session.getEffectiveUser().getEmail();

  if (!isValidEmail_(recipient)) {
    throw new Error(
      "Impossible d'identifier votre adresse Google pour le test."
    );
  }

  const draft = parseDraft_(
    buildInitialDraft_({
      'Nom du SaaS': 'Test SaaS',
      'Corentin': 'Catalogue ElevenLabs',
      'Preuve ElevenLabs': 'Voice ID ElevenLabs accepté'
    })
  );

  GmailApp.sendEmail(
    recipient,
    '[TEST] ' + draft.subject,
    draft.body,
    initialMailOptions_(draft.body)
  );

  notify_(
    'Test envoyé à ' + recipient +
    '. Vérifiez aussi le dossier spam.'
  );
}

function prepareMissingMessages() {
  assertRequiredHeaders_();

  const context = getContext_();
  let prepared = 0;

  context.rows.forEach(function (row, index) {
    if (
      !row['Nom du SaaS'] ||
      row['Date envoi'] ||
      row['Message de contact']
    ) {
      return;
    }

    writeFields_(
      context,
      CONFIG.FIRST_DATA_ROW + index,
      {
        'Message de contact': buildInitialDraft_(row)
      }
    );

    prepared++;
  });

  notify_(
    prepared
      ? prepared + ' message(s) court(s) ajouté(s).'
      : 'Aucun message manquant.'
  );
}

// Remplace les messages non envoyés après confirmation.
// Cette fonction ne lance aucun envoi.
function refreshUnsentMessages() {
  const ui = getUiSafely_();

  if (!ui) {
    throw new Error(
      'Pour remplacer les anciens messages avec confirmation, ' +
      'utilisez le menu Prospection du Google Sheets. ' +
      'Aucun message modifié.'
    );
  }

  const auto = getBoolSetting_('AUTO_SEND');

  const answer = ui.alert(
    'Actualiser les messages',
    'Remplacer tous les messages non envoyés, ' +
    'y compris vos textes personnalisés ? ' +
    (auto
      ? 'Les cases Envoyer ne sont pas modifiées (envoi automatique actif).'
      : 'Les cases Envoyer seront décochées pour permettre une relecture.'),
    ui.ButtonSet.YES_NO
  );

  if (answer !== ui.Button.YES) return;

  const lock = LockService.getScriptLock();

  if (!lock.tryLock(30000)) {
    throw new Error(
      'Traitement en cours. Réessayez ensuite.'
    );
  }

  let count = 0;

  try {
    assertRequiredHeaders_();

    const context = getContext_();

    context.rows.forEach(function (row, index) {
      if (!row['Nom du SaaS'] || row['Date envoi']) {
        return;
      }

      if (isPresentBanned_(row)) {
        writeFields_(context, CONFIG.FIRST_DATA_ROW + index, {
          'Envoyer': false,
          'Statut prospection': 'Banni — voix déjà présente',
          'État envoi': 'Banni — voix déjà présente chez ce SaaS, aucun contact autorisé'
        });
        return;
      }

      const fields = {
        'Message de contact': buildInitialDraft_(row)
      };

      if (!auto) fields['Envoyer'] = false;

      writeFields_(context, CONFIG.FIRST_DATA_ROW + index, fields);

      count++;
    });
  } finally {
    lock.releaseLock();
  }

  ui.alert(count + ' messages actualisés.');
}

// Coche « Envoyer » sur les lignes « À contacter » qui ont un vrai e-mail.
function queueValidRows() {
  const ui = getUiSafely_();

  assertRequiredHeaders_();

  const context = getContext_();
  const candidates = [];

  context.rows.forEach(function (row, index) {
    if (
      row['Nom du SaaS'] &&
      !row['Date envoi'] &&
      row['Envoyer'] !== true &&
      String(row['Statut prospection']).trim() === 'À contacter' &&
      isValidEmail_(String(row['Email public'] || '').trim()) &&
      !isPresentBanned_(row)
    ) {
      candidates.push(index);
    }
  });

  if (!candidates.length) {
    notify_('Aucune ligne « À contacter » avec e-mail valide.');
    return;
  }

  if (ui) {
    const answer = ui.alert(
      'Mettre en file',
      candidates.length + ' ligne(s) seront cochées « Envoyer » et ' +
      'traitées dans la limite quotidienne. Ces adresses viennent de ' +
      'recherches précédentes : vérifiez-les si besoin. Continuer ?',
      ui.ButtonSet.YES_NO
    );

    if (answer !== ui.Button.YES) return;
  }

  candidates.forEach(function (index) {
    writeFields_(context, CONFIG.FIRST_DATA_ROW + index, {
      'Envoyer': true
    });
  });

  notify_(candidates.length + ' ligne(s) mises en file.');
}

// ---------------------------------------------------------------
// HISTORIQUE (une ligne par lancement, recherche auto ou envoi auto)
// ---------------------------------------------------------------

const HISTORY_HEADERS = ['Date', 'Type', 'Durée (s)', 'Candidats proposés', 'Ajoutés',
  'Écartés', 'E-mails trouvés', 'Messages remplacés', 'Mis en file', 'Envoyés',
  'Relances envoyées', 'Nouvelles réponses', 'Rebonds (3 j)', 'Notes / erreurs'];

function logHistory_(type, f) {
  try {
    const ss = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
    let sheet = ss.getSheetByName('Historique');

    if (!sheet) {
      sheet = ss.insertSheet('Historique');
      sheet.getRange(1, 1, 1, HISTORY_HEADERS.length)
        .setValues([HISTORY_HEADERS])
        .setFontWeight('bold');
      sheet.setFrozenRows(1);
    }

    const line = [
      fmtDate_(new Date()), type, f.seconds || 0, f.proposed || 0, f.added || 0,
      f.rejected || 0, f.enriched || 0, f.refreshed || 0, f.queued || 0, f.sent || 0,
      f.followUps || 0, f.replies || 0, f.bounces || 0,
      reportCell_(String(f.notes || '').slice(0, 500))
    ];

    sheet.getRange(Math.max(sheet.getLastRow(), 1) + 1, 1, 1, line.length).setValues([line]);
  } catch (error) {
    console.log('Historique impossible : ' + safeError_(error));
  }
}

function counters_(context) {
  const c = { sent: 0, fu: 0, replies: 0 };

  context.rows.forEach(function (row) {
    if (row['Date envoi']) c.sent++;
    if (row['Relance 1 envoyée']) c.fu++;
    if (row['Relance 2 envoyée']) c.fu++;
    if (row['Dernière réponse']) c.replies++;
  });

  return c;
}

function saveLastTest_(run) {
  let json = JSON.stringify(run);

  if (json.length > 8500) {
    (run.phases || []).forEach(function (phase) {
      phase.detail = String(phase.detail || '').slice(0, 80);
    });
    json = JSON.stringify(run);
  }

  if (json.length > 8500) {
    run.sent = run.sent.slice(0, 10);
    run.queued = run.queued.slice(0, 10);
    json = JSON.stringify(run);
  }

  PropertiesService.getScriptProperties().setProperty('LAST_TEST', json);
}

// ---------------------------------------------------------------
// BOUTON UNIQUE : LANCER LA MACHINE
// ---------------------------------------------------------------

function setSetting_(key, value) {
  const sheet = SpreadsheetApp
    .openById(CONFIG.SPREADSHEET_ID)
    .getSheetByName(CONFIG.SETTINGS_SHEET);

  if (!sheet || sheet.getLastRow() < 2) return;

  const keys = sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).getValues();

  for (let i = 0; i < keys.length; i++) {
    if (String(keys[i][0]).trim() === key) {
      sheet.getRange(i + 2, 2).setValue(value);
      break;
    }
  }

  SETTINGS_CACHE_ = null;
}

// Cherche l'e-mail public sur le site des prospects « À contacter » qui n'en ont pas.
function enrichEmails_(context, budgetMs) {
  const started = Date.now();
  const result = { found: [], missing: [], tried: 0 };
  const props = PropertiesService.getScriptProperties();

  // Mémoire des sites déjà essayés (7 jours) pour ne pas retester toujours les mêmes.
  let tried = {};

  try {
    tried = JSON.parse(props.getProperty('ENRICH_TRIED') || '{}');
  } catch (error) {
    tried = {};
  }

  const weekAgo = Date.now() - 7 * 86400000;

  for (let i = 0; i < context.rows.length; i++) {
    if (Date.now() - started > budgetMs) break;

    const row = context.rows[i];

    if (!row['Nom du SaaS'] || row['Date envoi']) continue;
    if (String(row['Statut prospection']).trim() !== 'À contacter') continue;
    if (isValidEmail_(String(row['Email public'] || '').trim())) continue;

    const site = String(row['Site'] || '').trim();

    if (!hostOf_(site)) continue;

    const memoryKey = normalizeName_(row['Nom du SaaS']);

    if (tried[memoryKey] && tried[memoryKey] > weekAgo) continue;

    tried[memoryKey] = Date.now();
    result.tried++;

    const contact = String(row['Page de contact'] || '').trim();
    const email = findEmailOnSite_(site, /^https?:\/\//i.test(contact) ? contact : '');

    if (!email) {
      result.missing.push(String(row['Nom du SaaS']));
      continue;
    }

    writeFields_(context, CONFIG.FIRST_DATA_ROW + i, { 'Email public': email });
    result.found.push({ name: String(row['Nom du SaaS']), email: email });
  }

  Object.keys(tried).forEach(function (key) {
    if (tried[key] < Date.now() - 14 * 86400000) delete tried[key];
  });

  props.setProperty('ENRICH_TRIED', JSON.stringify(tried));

  return result;
}

// Routine du matin : compléter les e-mails, remplacer les anciens messages,
// mettre en file (si envoi automatique actif).
function prepareBaseDaily_() {
  assertRequiredHeaders_();

  const context = getContext_();
  const enriched = enrichEmails_(context, 50000);

  refreshOldMessages_(context);

  if (getBoolSetting_('AUTO_SEND')) queueEligibleRows_(context, false);

  return enriched;
}

// Remplace les anciens messages (signés Etienne, chiffres non validés) avant envoi.
function refreshOldMessages_(context) {
  let count = 0;

  context.rows.forEach(function (row, index) {
    if (!row['Nom du SaaS'] || row['Date envoi']) return;

    const currentMessage = String(row['Message de contact'] || '');

    if (
      /French voice-over artist/i.test(currentMessage) &&
      !/^Subject:\s*French voice for/i.test(currentMessage)
    ) {
      return;
    }

    writeFields_(context, CONFIG.FIRST_DATA_ROW + index, {
      'Message de contact': buildInitialDraft_(row)
    });

    count++;
  });

  return count;
}

function sendQueued_(context, run) {
  // Pause automatique sur rebonds retirée (2026-10-11) : la vérification
  // MyEmailVerifier avant envoi (verifyEmailAddress_) protège désormais
  // contre les rebonds. Le compteur reste informatif dans le rapport.
  if (recentBounceCount_(context) >= getNumberSetting_('MAX_BOUNCES_PAUSE', 3)) {
    run.notes.push(
      'ℹ ' + recentBounceCount_(context) + ' rebond(s) récent(s) — envois non suspendus ' +
      '(vérification d’adresse active).'
    );
  }

  const before = context.rows.map(function (row) { return !!row['Date envoi']; });

  processInitialQueue_(context);

  context.rows.forEach(function (row, index) {
    if (!before[index] && row['Date envoi']) {
      run.sent.push({
        name: String(row['Nom du SaaS']),
        email: String(row['Email public']),
        state: String(row['État envoi'] || '')
      });
    }
  });
}

function launchMachine() {
  const ui = getUiSafely_();
  const limit = getNumberSetting_('DAILY_LIMIT', CONFIG.DAILY_LIMIT);

  if (getBoolSetting_('MASTER_PAUSE')) {
    notify_(
      '⏸ Pause générale active (MASTER_PAUSE = TRUE dans Réglages) : aucun ' +
      'mail ne sera envoyé, ni premier contact ni relance. Repassez ' +
      'MASTER_PAUSE à FALSE dans l’onglet Réglages pour relancer les envois.'
    );
    return;
  }

  if (ui) {
    const answer = ui.alert(
      '🚀 LANCER LA MACHINE',
      'La machine va maintenant : 1) chercher les e-mails manquants et remplacer ' +
      'les anciens messages non envoyés par le nouveau modèle, 2) ENVOYER jusqu’à ' +
      limit + ' e-mails réels aujourd’hui (même hors horaires), 3) chercher de ' +
      'nouveaux prospects et envoyer pour compléter, 4) s’activer en automatique ' +
      '(recherche à 6h, envois lun-ven 9h-17h, relances J+4 et J+9, rapport à 8h). ' +
      'Continuer ?',
      ui.ButtonSet.YES_NO
    );

    if (answer !== ui.Button.YES) return;
  }

  const lock = LockService.getScriptLock();

  if (!lock.tryLock(30000)) {
    throw new Error('Traitement en cours. Réessayez ensuite.');
  }

  const started = Date.now();

  const run = {
    date: new Date().toISOString(),
    queued: [],
    sent: [],
    notes: [],
    phases: [],
    seconds: 0
  };

  function mark(name, t0, result, detail) {
    run.phases.push({
      name: name,
      seconds: Math.round((Date.now() - t0) / 1000),
      result: String(result || ''),
      detail: String(detail || '').slice(0, 300)
    });
  }

  function sentNames(from) {
    return run.sent.slice(from).map(function (item) { return item.name; }).join(', ');
  }

  const history = { proposed: 0, added: 0, rejected: 0, enriched: 0, refreshed: 0,
    followUps: 0, replies: 0 };

  try {
    let t = Date.now();

    assertSenderAlias_();
    setupSettingsSheet();
    assertRequiredHeaders_();
    setSetting_('AUTO_SEND', 'TRUE');
    installTriggers_();

    mark('0. Activation', t, 'AUTO_SEND = TRUE, 3 déclencheurs créés', '');

    const hasKey = !!PropertiesService
      .getScriptProperties()
      .getProperty('ANTHROPIC_API_KEY');

    let context = getContext_();
    const c0 = counters_(context);

    // Phase 1 : suivi
    t = Date.now();
    detectReplies_(context);
    detectBounces_(context);
    processFollowUps_(context);
    processIntegrationReminders_(context);

    const c1 = counters_(context);

    history.followUps = c1.fu - c0.fu;
    history.replies = c1.replies - c0.replies;

    mark('1. Suivi (réponses, rebonds, relances)', t,
      'Réponses détectées : ' + history.replies +
      ' | Relances envoyées : ' + history.followUps +
      ' | Rebonds (3 j) : ' + recentBounceCount_(context), '');

    // Phase 2 : e-mails manquants
    t = Date.now();

    const enriched = enrichEmails_(context, 45000);
    history.enriched = enriched.found.length;

    mark('2. E-mails manquants (pages des sites)', t,
      'Trouvés : ' + enriched.found.length + ' sur ' + enriched.tried + ' recherchés',
      'Trouvés : ' + (enriched.found.map(function (item) {
        return item.name + ' <' + item.email + '>';
      }).join(', ') || 'aucun') +
      ' | Introuvables : ' + (enriched.missing.join(', ') || 'aucun'));

    // Phase 3 : messages
    t = Date.now();
    history.refreshed = refreshOldMessages_(context);
    mark('3. Messages', t, history.refreshed + ' ancien(s) message(s) remplacé(s)', '');

    // Phase 4 : envoi sur la base existante
    t = Date.now();

    const queued1 = queueEligibleRows_(context, false);
    const from1 = run.sent.length;

    run.queued = queued1.slice();
    sendQueued_(context, run);

    mark('4. Mise en file + envoi (base existante)', t,
      'En file : ' + queued1.length + ' | Envoyés : ' + (run.sent.length - from1),
      sentNames(from1));

    // Phase 5 et 6 : nouveaux prospects si le quota du jour n'est pas atteint
    const remaining = limit - countInitialSendsToday_(context);

    if (remaining <= 0) {
      mark('5. Découverte (nouveaux prospects)', Date.now(), 'Ignorée', 'Quota du jour atteint.');
    } else if (!hasKey) {
      mark('5. Découverte (nouveaux prospects)', Date.now(), 'Ignorée', 'Clé API Claude absente.');
    } else if (Date.now() - started > 150000) {
      mark('5. Découverte (nouveaux prospects)', Date.now(), 'Ignorée',
        'Temps insuffisant : reprise automatique à 6h.');
    } else {
      t = Date.now();

      let summary = null;

      try {
        summary = discoverProspects_(70000);
      } catch (error) {
        saveDiscoveryFailure_(error);
        run.notes.push('Découverte : ' + safeError_(error));
      }

      if (summary) {
        history.proposed = summary.proposed || 0;
        history.added = summary.added.length;
        history.rejected = summary.rejected.length;
      }

      mark('5. Découverte (nouveaux prospects)', t,
        summary
          ? 'Proposés : ' + summary.proposed + ' | Ajoutés : ' + summary.added.length +
            ' | Écartés : ' + summary.rejected.length
          : 'Échec',
        summary
          ? 'Ajoutés : ' + (summary.added.join(', ') || 'aucun') +
            ' | Écartés : ' + (summary.rejected.join(' ; ') || 'aucun') +
            (summary.errors.length ? ' | Erreurs : ' + summary.errors.join(' | ') : '')
          : run.notes[run.notes.length - 1]);

      t = Date.now();
      context = getContext_();

      const queued2 = queueEligibleRows_(context, true);
      const from2 = run.sent.length;

      run.queued = run.queued.concat(queued2);
      sendQueued_(context, run);

      mark('6. Mise en file + envoi (nouveaux prospects)', t,
        'En file : ' + queued2.length + ' | Envoyés : ' + (run.sent.length - from2),
        sentNames(from2));
    }

    if (!run.sent.length) {
      run.notes.push(
        'Aucun e-mail envoyé : pas de prospect avec e-mail vérifié pour le moment. ' +
        'La machine continue automatiquement (recherche à 6h, envois lun-ven 9h-17h).'
      );
    }

    run.seconds = Math.round((Date.now() - started) / 1000);

    saveLastTest_(run);

    logHistory_('Lancement', {
      seconds: run.seconds,
      proposed: history.proposed,
      added: history.added,
      rejected: history.rejected,
      enriched: history.enriched,
      refreshed: history.refreshed,
      queued: run.queued.length,
      sent: run.sent.length,
      followUps: history.followUps,
      replies: history.replies,
      bounces: recentBounceCount_(context),
      notes: run.notes.join(' | ')
    });

    writeReportTab_();
  } finally {
    lock.releaseLock();
  }

  notify_(
    'Machine lancée et active en automatique (' + run.seconds + ' s). ' +
    'E-mails envoyés maintenant : ' + run.sent.length +
    (run.sent.length
      ? ' (' + run.sent.map(function (item) { return item.name; }).join(', ') + ')'
      : '') +
    '. Détail par phase dans l’onglet « Rapport », historique dans « Historique ».' +
    (run.notes.length ? ' Notes : ' + run.notes.join(' | ') : '')
  );
}

// ---------------------------------------------------------------
// TEST COMPLET (3 étapes) + ONGLET RAPPORT
// ---------------------------------------------------------------

// Lignes « À contacter » avec e-mail valide à cocher « Envoyer ».
// onlyAutoAdded = true : uniquement les prospects ajoutés par la découverte.
function queueEligibleRows_(context, onlyAutoAdded) {
  const names = [];

  context.rows.forEach(function (row, index) {
    if (!row['Nom du SaaS'] || row['Date envoi']) return;
    if (String(row['Statut prospection']).trim() !== 'À contacter') return;
    if (!isValidEmail_(String(row['Email public'] || '').trim())) return;

    if (
      onlyAutoAdded &&
      !/^Ajouté automatiquement/.test(String(row['Notes / prochaine action'] || ''))
    ) {
      return;
    }

    if (row['Envoyer'] !== true) {
      writeFields_(context, CONFIG.FIRST_DATA_ROW + index, { 'Envoyer': true });
    }

    names.push(row['Nom du SaaS']);
  });

  return names;
}

function runFullTest() {
  const ui = getUiSafely_();
  const cap = getNumberSetting_('TEST_MAX_SENDS', 3);

  if (getBoolSetting_('MASTER_PAUSE')) {
    notify_(
      '⏸ Pause générale active (MASTER_PAUSE = TRUE dans Réglages) : aucun ' +
      'mail ne sera envoyé. Repassez MASTER_PAUSE à FALSE dans l’onglet ' +
      'Réglages pour tester des envois réels.'
    );
    return;
  }

  if (ui) {
    const answer = ui.alert(
      'TEST COMPLET',
      'Ce test va : 1) chercher de nouveaux prospects, 2) mettre en file les ' +
      'prospects ajoutés automatiquement qui ont un e-mail vérifié, ' +
      '3) ENVOYER jusqu’à ' + cap + ' e-mail(s) réel(s) maintenant, sans ' +
      'attendre les horaires. Un onglet « Rapport » sera ensuite créé. Continuer ?',
      ui.ButtonSet.YES_NO
    );

    if (answer !== ui.Button.YES) return;
  }

  const lock = LockService.getScriptLock();

  if (!lock.tryLock(30000)) {
    throw new Error('Traitement en cours. Réessayez ensuite.');
  }

  const started = Date.now();

  const test = {
    date: new Date().toISOString(),
    queued: [],
    sent: [],
    notes: [],
    seconds: 0
  };

  try {
    assertSenderAlias_();
    assertRequiredHeaders_();

    // Étape 1 : découverte
    try {
      discoverProspects_();
    } catch (error) {
      saveDiscoveryFailure_(error);
      test.notes.push('Découverte : ' + safeError_(error));
    }

    // Étape 2 : mise en file
    const context = getContext_();

    detectReplies_(context);
    detectBounces_(context);

    test.queued = queueEligibleRows_(context, true);

    // Étape 3 : envoi (limité par TEST_MAX_SENDS)
    const before = context.rows.map(function (row) {
      return !!row['Date envoi'];
    });

    // Le test manuel (bouton "Test complet") n'est PAS bloqué par la pause
    // automatique anti-rebonds : il est déclenché à la main, volontairement,
    // et limité à TEST_MAX_SENDS (3 par défaut) — le risque est donc maîtrisé,
    // contrairement au moteur automatique horaire qui, lui, reste protégé.
    if (recentBounceCount_(context) >= getNumberSetting_('MAX_BOUNCES_PAUSE', 3)) {
      test.notes.push(
        'ℹ Pause anti-rebonds automatique normalement active (ignorée pour ce test manuel, max ' +
        cap + ' envoi(s)).'
      );
    }

    processInitialQueue_(context, cap);

    context.rows.forEach(function (row, index) {
      if (!before[index] && row['Date envoi']) {
        test.sent.push({
          name: String(row['Nom du SaaS']),
          email: String(row['Email public']),
          state: String(row['État envoi'] || '')
        });
      }
    });

    if (!test.sent.length) {
      test.notes.push(
        'Aucun e-mail envoyé : aucune ligne « À contacter » ajoutée ' +
        'automatiquement avec e-mail vérifié, ou limite quotidienne atteinte.'
      );
    }

    test.seconds = Math.round((Date.now() - started) / 1000);

    saveLastTest_(test);

    logHistory_('Test limité', {
      seconds: test.seconds,
      queued: test.queued.length,
      sent: test.sent.length,
      notes: test.notes.join(' | ')
    });

    writeReportTab_();
  } finally {
    lock.releaseLock();
  }

  notify_(
    'Test terminé en ' + test.seconds + ' s. ' +
    'En file : ' + test.queued.length + '. ' +
    'Envoyés : ' + test.sent.length +
    (test.sent.length
      ? ' (' + test.sent.map(function (item) { return item.name; }).join(', ') + ')'
      : '') +
    '. Le détail est dans l’onglet « Rapport ».' +
    (test.notes.length ? ' Notes : ' + test.notes.join(' | ') : '')
  );
}

function refreshReportTab() {
  writeReportTab_();
  notify_('Onglet Rapport mis à jour.');
}

function fmtDate_(value) {
  const date = toDate_(value);

  return date
    ? Utilities.formatDate(date, CONFIG.TIME_ZONE, 'yyyy-MM-dd HH:mm')
    : String(value || '');
}

function reportCell_(value) {
  if (typeof value === 'string' && /^[=+\-@]/.test(value)) {
    return "'" + value;
  }

  return value === null || value === undefined ? '' : value;
}

function countBy_(rows, header) {
  const counts = {};

  rows.forEach(function (row) {
    const key = String(row[header] || '(vide)').trim() || '(vide)';
    counts[key] = (counts[key] || 0) + 1;
  });

  return Object.keys(counts)
    .sort(function (a, b) { return counts[b] - counts[a]; })
    .map(function (key) { return [key, counts[key]]; });
}

function buildReportRows_() {
  const props = PropertiesService.getScriptProperties();

  function parse(key) {
    try {
      return JSON.parse(props.getProperty(key) || 'null');
    } catch (error) {
      return null;
    }
  }

  const discovery = parse('LAST_DISCOVERY');
  const test = parse('LAST_TEST');
  const context = getContext_();
  const prospects = context.rows.filter(function (row) { return row['Nom du SaaS']; });

  const out = [];
  const titles = [];
  const headers = [];

  function title(text) {
    titles.push(out.length);
    out.push([text]);
  }

  function header(cells) {
    headers.push(out.length);
    out.push(cells);
  }

  out.push(['RAPPORT DE DATA — MACHINE DE PROSPECTION', fmtDate_(new Date())]);
  titles.push(0);
  out.push([]);

  title('1. DERNIER LANCEMENT (machine ou test)');

  if (test) {
    out.push(['Date', fmtDate_(test.date)]);
    out.push(['Durée (secondes)', test.seconds]);
    out.push(['Mis en file (étape 2)', (test.queued || []).length, (test.queued || []).join(', ')]);
    out.push(['E-mails envoyés (étape 3)', (test.sent || []).length,
      (test.sent || []).map(function (item) { return item.name + ' <' + item.email + '>'; }).join(' ; ')]);
    out.push(['Notes', (test.notes || []).join(' | ')]);

    if ((test.phases || []).length) {
      out.push([]);
      header(['Phase', 'Durée (s)', 'Résultat', 'Détail']);

      test.phases.forEach(function (phase) {
        out.push([phase.name, phase.seconds, phase.result, phase.detail]);
      });
    }
  } else {
    out.push(['Aucun test enregistré.']);
  }

  out.push([]);
  title('2. ENTONNOIR DE LA DERNIÈRE DÉCOUVERTE');

  if (discovery) {
    const details = discovery.details || [];
    const added = details.filter(function (item) { return item.result === 'Ajouté'; });
    const rejected = details.filter(function (item) { return item.result === 'Écarté'; });

    const degraded = added.filter(function (item) {
      return item.claimedStatus &&
        item.claimedStatus.toLowerCase() !== 'unverified' &&
        item.finalStatus === 'Non vérifié';
    });

    out.push(['Date', fmtDate_(discovery.date)]);
    out.push(['Segments explorés', (discovery.segments || []).join(' ; ')]);
    out.push(['Candidats proposés par Claude', discovery.proposed || details.length]);
    out.push(['Écartés par le script', rejected.length]);
    out.push(['Ajoutés', added.length]);
    out.push(['dont e-mail vérifié', added.filter(function (item) { return item.emailVerified; }).length]);
    out.push(['dont page de contact accessible', added.filter(function (item) { return item.contactOk; }).length]);
    out.push(['dont statut ElevenLabs dégradé en « Non vérifié »', degraded.length]);
    out.push(['Erreurs', (discovery.errors || []).join(' | ')]);

    const reasons = {};

    rejected.forEach(function (item) {
      reasons[item.reason] = (reasons[item.reason] || 0) + 1;
    });

    out.push(['Raisons d’écart', Object.keys(reasons).map(function (key) {
      return key + ' : ' + reasons[key];
    }).join(' ; ') || 'aucune']);

    out.push([]);
    title('3. DÉTAIL PAR CANDIDAT (dernière découverte)');
    header(['Segment', 'Nom', 'Site', 'Statut annoncé', 'Statut final',
      'E-mail annoncé', 'E-mail vérifié', 'Page contact OK', 'Résultat', 'Raison']);

    details.forEach(function (item) {
      out.push([item.segment, item.name, item.site, item.claimedStatus,
        item.finalStatus, item.claimedEmail,
        item.emailVerified ? 'OUI' : 'NON', item.contactOk ? 'OUI' : 'NON',
        item.result, item.reason]);
    });
  } else {
    out.push(['Aucune découverte enregistrée.']);
  }

  out.push([]);
  title('4. RÉGLAGES ACTIFS');

  ['AUTO_SEND', 'DAILY_LIMIT', 'WEEKDAYS_ONLY', 'SEND_START_HOUR', 'SEND_END_HOUR',
    'MAX_BOUNCES_PAUSE', 'TEST_MAX_SENDS', 'DISCOVERY_PER_CALL', 'DISCOVERY_MAX_CALLS',
    'MODEL', 'BLOCKLIST_DOMAINS'].forEach(function (key) {
    out.push([key, getSetting_(key)]);
  });

  out.push([]);
  title('5. STATISTIQUES DE LA BASE');

  const contacted = prospects.filter(function (row) { return row['Date envoi']; });
  const replies = prospects.filter(function (row) { return row['Dernière réponse']; });

  out.push(['Prospects dans la base', prospects.length]);
  out.push(['Contactés', contacted.length]);
  out.push(['Réponses', replies.length,
    contacted.length ? Math.round(1000 * replies.length / contacted.length) / 10 + ' %' : '']);
  out.push(['Rebonds', prospects.filter(function (row) { return row['État envoi'] === 'Rebond'; }).length]);
  out.push([]);
  header(['Statut prospection', 'Nombre']);
  countBy_(prospects, 'Statut prospection').forEach(function (line) { out.push(line); });
  out.push([]);
  header(['Statut Corentin / ElevenLabs', 'Nombre']);
  countBy_(prospects, 'Corentin').forEach(function (line) { out.push(line); });
  out.push([]);
  header(['État d’envoi', 'Nombre']);
  countBy_(prospects, 'État envoi').forEach(function (line) { out.push(line); });
  out.push([]);
  header(['Type de SaaS', 'Nombre']);
  countBy_(prospects, 'Type de SaaS').forEach(function (line) { out.push(line); });

  out.push([]);
  title('6. BASE COMPLÈTE');

  const columns = ['ID prospect', 'Nom du SaaS', 'Site', 'Email public', 'Statut prospection',
    'Corentin', 'Zone / langue', 'Type de SaaS', 'Date envoi', 'Relance 1 envoyée',
    'Relance 2 envoyée', 'Dernière réponse', 'Résultat commercial', 'État envoi',
    'Erreur envoi', 'Source preuve', 'Notes / prochaine action'];

  header(columns);

  prospects.forEach(function (row) {
    out.push(columns.map(function (column) {
      const value = row[column];

      return /^(Date|Relance|Dernière)/.test(column) ? fmtDate_(value) : value;
    }));
  });

  return { rows: out, titles: titles, headers: headers };
}

function writeReportTab_() {
  const report = buildReportRows_();
  const ss = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);

  let sheet = ss.getSheetByName('Rapport');

  if (!sheet) sheet = ss.insertSheet('Rapport');

  sheet.clear();

  const width = Math.max.apply(null, report.rows.map(function (line) {
    return line.length;
  }).concat([2]));

  const padded = report.rows.map(function (line) {
    const cells = line.map(reportCell_);

    while (cells.length < width) cells.push('');

    return cells;
  });

  if (sheet.getMaxRows() < padded.length) {
    sheet.insertRowsAfter(sheet.getMaxRows(), padded.length - sheet.getMaxRows());
  }

  if (sheet.getMaxColumns() < width) {
    sheet.insertColumnsAfter(sheet.getMaxColumns(), width - sheet.getMaxColumns());
  }

  sheet.getRange(1, 1, padded.length, width).setValues(padded);

  report.titles.forEach(function (index) {
    sheet.getRange(index + 1, 1, 1, width)
      .setFontWeight('bold')
      .setBackground('#d9ead3');
  });

  report.headers.forEach(function (index) {
    sheet.getRange(index + 1, 1, 1, width)
      .setFontWeight('bold')
      .setBackground('#eeeeee');
  });

  sheet.setColumnWidth(1, 260);
  sheet.setColumnWidth(2, 220);
  sheet.setFrozenRows(1);
}

// ---------------------------------------------------------------
// TRAITEMENT (ENVOI, RÉPONSES, REBONDS, RELANCES)
// ---------------------------------------------------------------

function processProspectionMachine() {
  runMachine_(false);
}

function processProspectionMachineNow() {
  runMachine_(true);
}

function runMachine_(force) {
  const lock = LockService.getScriptLock();

  if (!lock.tryLock(30000)) return;

  try {
    runMachineBody_(force);
  } catch (error) {
    // Avant : une erreur ici (alias Gmail manquant, en-tête supprimé, etc.)
    // disparaissait silencieusement — aucune trace nulle part, et le moteur
    // restait bloqué des heures sans que personne ne le sache. Désormais
    // elle est toujours visible dans l'onglet Historique.
    logHistory_('⚠️ Erreur moteur (passage ignoré)', {
      notes: safeError_(error)
    });
    throw error;
  } finally {
    lock.releaseLock();
  }
}

function runMachineBody_(force) {
  {
    assertSenderAlias_();
    assertRequiredHeaders_();

    const context = getContext_();
    const before = counters_(context);

    detectReplies_(context);
    detectBounces_(context);
    migrateConfirmedPartners_(context);

    if (getBoolSetting_('MASTER_PAUSE')) {
      // Pause globale : ni premier mail, ni relance. Les réponses, rebonds
      // et passages en partenaire actif restent traités ci-dessus (aucun
      // envoi, donc sans danger même en pause).
      return;
    }

    if (force || inSendWindow_()) {
      processFollowUps_(context);
      processIntegrationReminders_(context);

      // La pause automatique sur rebonds a été retirée (2026-10-11) : la
      // vérification d'adresse MyEmailVerifier avant chaque envoi (voir
      // verifyEmailAddress_) est désormais la protection principale contre
      // les rebonds. Le nombre de rebonds récents reste calculé et affiché
      // dans le rapport quotidien (Historique / Synthèse), seulement pour
      // information — il ne bloque plus les envois.
      processInitialQueue_(context, getNumberSetting_('MAX_SENDS_PER_RUN', 15));
    }

    const after = counters_(context);

    if (
      after.sent !== before.sent ||
      after.fu !== before.fu ||
      after.replies !== before.replies
    ) {
      logHistory_('Envoi auto', {
        sent: after.sent - before.sent,
        followUps: after.fu - before.fu,
        replies: after.replies - before.replies,
        bounces: recentBounceCount_(context)
      });
    }
  }
}

function inSendWindow_() {
  const now = new Date();

  if (getBoolSetting_('WEEKDAYS_ONLY')) {
    const weekday = Number(Utilities.formatDate(now, CONFIG.TIME_ZONE, 'u'));
    if (weekday >= 6) return false;
  }

  const hour = Number(Utilities.formatDate(now, CONFIG.TIME_ZONE, 'H'));

  return (
    hour >= getNumberSetting_('SEND_START_HOUR', 9) &&
    hour < getNumberSetting_('SEND_END_HOUR', 17)
  );
}

// ---------------------------------------------------------------
// ANTI-DOUBLON : jamais deux premiers e-mails à la même entreprise
// ---------------------------------------------------------------

const FREE_MAIL_DOMAINS = [
  'gmail.com', 'googlemail.com', 'outlook.com', 'hotmail.com', 'live.com',
  'yahoo.com', 'icloud.com', 'proton.me', 'protonmail.com', 'aol.com'
];

function emailDomain_(email) {
  return String(email || '').trim().toLowerCase().split('@')[1] || '';
}

// Renvoie la raison si cette boîte ou cette entreprise a déjà été contactée, sinon ''.
function duplicateReason_(context, index, email) {
  const row = context.rows[index];
  const address = String(email || '').trim().toLowerCase();
  const domain = emailDomain_(address);
  const isFree = FREE_MAIL_DOMAINS.indexOf(domain) !== -1;
  const siteHost = hostOf_(row['Site']);
  const name = normalizeName_(row['Nom du SaaS']);

  for (let i = 0; i < context.rows.length; i++) {
    if (i === index) continue;

    const other = context.rows[i];

    if (!other['Nom du SaaS'] || !other['Date envoi']) continue;

    const otherEmail = String(other['Email public'] || '').trim().toLowerCase();
    const label = String(other['Nom du SaaS']);

    if (otherEmail && otherEmail === address) return 'même adresse que ' + label;
    if (!isFree && domain && emailDomain_(otherEmail) === domain) {
      return 'même domaine e-mail que ' + label;
    }
    if (siteHost && hostOf_(other['Site']) === siteHost) return 'même site que ' + label;
    if (name && normalizeName_(label) === name) return 'même nom que ' + label;
  }

  // Envois faits hors du Sheet : on regarde aussi les messages envoyés dans Gmail.
  try {
    const query = 'in:sent (to:' + address + (isFree || !domain ? '' : ' OR to:' + domain) + ')';

    if (GmailApp.search(query, 0, 1).length) {
      return 'déjà un e-mail envoyé à cette adresse ou ce domaine (Gmail)';
    }
  } catch (error) {
    console.log('Contrôle Gmail impossible : ' + safeError_(error));
  }

  return '';
}

function processInitialQueue_(context, cap) {
  let remaining = Math.max(
    0,
    getNumberSetting_('DAILY_LIMIT', CONFIG.DAILY_LIMIT) -
      countInitialSendsToday_(context)
  );

  if (cap !== undefined) remaining = Math.min(remaining, cap);

  if (!remaining) return;

  for (
    let i = 0;
    i < context.rows.length && remaining > 0;
    i++
  ) {
    const row = context.rows[i];

    if (
      row['Envoyer'] !== true ||
      row['Date envoi']
    ) {
      continue;
    }

    const sheetRow = CONFIG.FIRST_DATA_ROW + i;

    if (isPresentBanned_(row)) {
      writeFields_(context, sheetRow, {
        'Envoyer': false,
        'À relancer': false,
        'Statut prospection': 'Banni — voix déjà présente',
        'État envoi': 'Banni — voix déjà présente chez ce SaaS, aucun contact autorisé',
        'Erreur envoi': ''
      });

      continue;
    }

    // Dernier filet de sécurité, juste avant l'envoi : revisite le site du
    // prospect (et ses pages de preuve connues) et cherche l'ID ElevenLabs
    // exact de Corentin. Protège contre le cas où la plateforme a ajouté la
    // voix APRÈS sa découverte (par ChatGPT ou autrement), ou si la colonne
    // "Corentin" n'a pas été correctement renseignée à la découverte. Fail
    // open : si le site ne répond pas, on n'empêche pas l'envoi pour autant.
    const recheck = recheckVoicePresence_(row);

    if (recheck.present) {
      writeFields_(context, sheetRow, {
        'Envoyer': false,
        'À relancer': false,
        'Corentin': 'Exact confirmé',
        'Source preuve': recheck.url,
        'Statut prospection': 'Banni — voix déjà présente (détectée au recontrôle)',
        'État envoi': 'Banni — voix retrouvée sur leur site juste avant l’envoi',
        'Erreur envoi': ''
      });

      continue;
    }

    const recipient = String(
      row['Email public'] || ''
    ).trim();

    // Toujours régénéré à partir des modèles actuels de Réglages juste avant
    // l'envoi — jamais réutilisé depuis un texte mis en cache plus tôt. Ça
    // évite qu'un e-mail 1 modifié il y a des semaines dans Réglages reste
    // bloqué sur l'ancien texte pour les lignes déjà en file (incident du
    // 11/10 : plusieurs mails "Clipate"/etc. partis avec un ancien modèle
    // alors que Réglages avait déjà été mis à jour).
    const rawDraft = buildInitialDraft_(row);

    writeFields_(context, sheetRow, {
      'Message de contact': rawDraft
    });

    const draft = parseDraft_(rawDraft);

    if (!isValidEmail_(recipient)) {
      writeFields_(context, sheetRow, {
        'Envoyer': false,
        'État envoi': 'Formulaire manuel',
        'Erreur envoi': 'Aucune adresse email exploitable'
      });

      continue;
    }

    if (getBoolSetting_('EMAIL_VERIFY_ENABLED')) {
      const verif = verifyEmailAddress_(recipient);

      if (verif.checked && !verif.safe) {
        writeFields_(context, sheetRow, {
          'Envoyer': false,
          'À relancer': false,
          'Statut prospection': 'Email invalide (vérifié)',
          'État envoi': 'Email invalide — vérification API avant envoi',
          'Erreur envoi': 'MyEmailVerifier : ' + verif.raw
        });

        continue;
      }
    }

    if (!draft.subject || !draft.body) {
      writeFields_(context, sheetRow, {
        'Envoyer': false,
        'État envoi': 'Bloqué',
        'Erreur envoi': 'Objet ou message manquant'
      });

      continue;
    }

    const duplicate = duplicateReason_(context, i, recipient);

    if (duplicate) {
      writeFields_(context, sheetRow, {
        'Envoyer': false,
        'À relancer': false,
        'Statut prospection': 'Doublon',
        'État envoi': 'Doublon — non envoyé',
        'Erreur envoi': 'Déjà contacté : ' + duplicate
      });

      continue;
    }

    let sent = false;

    try {
      const options = initialMailOptions_(draft.body);

      writeFields_(context, sheetRow, {
        'Envoyer': false
      });

      SpreadsheetApp.flush();

      GmailApp.sendEmail(
        recipient,
        draft.subject,
        draft.body,
        options
      );

      sent = true;

      const now = new Date();

      writeFields_(context, sheetRow, {
        'Date envoi': now
      });

      // Garde une copie du dernier mail 1 réellement envoyé (objet + début du
      // corps en clair), relue par le rapport quotidien pour vérifier que le
      // bon modèle part bien — ça aurait permis de détecter immédiatement le
      // bug de cache qui envoyait l'ancien corps de mail.
      saveLastSentSample_(draft.subject, draft.body);

      // Espacement réel entre deux envois pour éviter un pattern de rafale
      // (plusieurs mails en quelques secondes) qui dégrade la délivrabilité.
      Utilities.sleep(getNumberSetting_('SEND_DELAY_MS', 18000));

      const thread = findSentThread_(
        recipient,
        draft.subject
      );

      writeFields_(context, sheetRow, {
        'Envoyer': false,
        'À relancer': true,
        'Statut prospection': 'Contacté',
        'Canal utilisé': 'Email',
        'Date du premier contact': now,
        'Prochaine relance': addDays_(
          now,
          CONFIG.FOLLOW_UP_1_DAYS
        ),
        'État envoi': 'Envoyé',
        'Date envoi': now,
        'ID conversation': thread ? thread.getId() : '',
        'Erreur envoi': ''
      });

      remaining--;
    } catch (error) {
      writeFields_(context, sheetRow, {
        'Envoyer': false,
        'À relancer': false,
        'État envoi': sent
          ? 'Envoyé — suivi à vérifier'
          : 'Erreur — vérifier Gmail avant nouvel essai',
        'Erreur envoi': safeError_(error)
      });
    }
  }
}

function detectReplies_(context) {
  for (let i = 0; i < context.rows.length; i++) {
    const row = context.rows[i];

    if (
      !row['ID conversation'] ||
      row['Dernière réponse']
    ) {
      continue;
    }

    const thread = getThreadSafely_(
      row['ID conversation']
    );

    if (!thread || !hasExternalReply_(thread)) {
      continue;
    }

    writeFields_(
      context,
      CONFIG.FIRST_DATA_ROW + i,
      {
        'À relancer': false,
        'Statut prospection': 'Réponse reçue',
        'Dernière réponse': new Date(),
        'Résultat commercial': 'En discussion',
        'État envoi': 'Réponse reçue',
        'Prochaine relance': ''
      }
    );
  }
}

// Repère les e-mails renvoyés par mailer-daemon et stoppe les relances.
function detectBounces_(context) {
  let threads = [];

  try {
    threads = GmailApp.search(
      'from:(mailer-daemon OR postmaster) newer_than:3d',
      0,
      30
    );
  } catch (error) {
    console.log('Recherche de rebonds impossible : ' + safeError_(error));
    return;
  }

  if (!threads.length) return;

  const bodies = [];

  threads.forEach(function (thread) {
    thread.getMessages().forEach(function (message) {
      bodies.push(String(message.getPlainBody() || '').toLowerCase());
    });
  });

  context.rows.forEach(function (row, index) {
    const email = String(row['Email public'] || '').trim().toLowerCase();

    if (
      !row['Date envoi'] ||
      !isValidEmail_(email) ||
      row['État envoi'] === 'Rebond' ||
      row['Dernière réponse']
    ) {
      return;
    }

    const bounced = bodies.some(function (body) {
      return body.indexOf(email) !== -1;
    });

    if (!bounced) return;

    writeFields_(context, CONFIG.FIRST_DATA_ROW + index, {
      'À relancer': false,
      'Statut prospection': 'Rebond',
      'État envoi': 'Rebond',
      'Prochaine relance': '',
      'Erreur envoi': 'Rebond détecté le ' +
        Utilities.formatDate(new Date(), CONFIG.TIME_ZONE, 'yyyy-MM-dd')
    });
  });
}

function recentBounceCount_(context) {
  const limit = Date.now() - 3 * 86400000;

  return context.rows.filter(function (row) {
    const sentAt = toDate_(row['Date envoi']);

    return (
      row['État envoi'] === 'Rebond' &&
      sentAt &&
      sentAt.getTime() >= limit
    );
  }).length;
}

function processFollowUps_(context) {
  const now = new Date();

  // Plafond + délai entre chaque relance, comme pour les premiers mails
  // (processInitialQueue_). Sans ça, si plusieurs dizaines de lignes
  // franchissent leur seuil J+4/J+9 le même jour (un gros lot envoyé le même
  // jour quelques jours plus tôt), TOUTES partent d'un coup, dans la même
  // minute, sans aucune pause — repéré le 12/10 : ~30 relances parties en
  // rafale entre 08:39 et 08:40. MAX_FOLLOWUPS_PER_RUN limite le nombre de
  // relances envoyées par passage, et SEND_DELAY_MS espace chaque envoi.
  let remaining = getNumberSetting_('MAX_FOLLOWUPS_PER_RUN', 10);

  for (let i = 0; i < context.rows.length && remaining > 0; i++) {
    const row = context.rows[i];

    if (
      row['À relancer'] !== true ||
      !row['Date envoi'] ||
      row['Dernière réponse']
    ) {
      continue;
    }

    const sheetRow = CONFIG.FIRST_DATA_ROW + i;

    if (isPresentBanned_(row)) {
      writeFields_(context, sheetRow, {
        'À relancer': false,
        'Statut prospection': 'Banni — voix déjà présente',
        'État envoi': 'Banni — voix déjà présente chez ce SaaS, relance interdite',
        'Prochaine relance': '',
        'Erreur envoi': ''
      });

      continue;
    }

    const recipient = String(
      row['Email public'] || ''
    ).trim();

    const sentAt = new Date(row['Date envoi']);
    const age = daysBetween_(sentAt, now);

    const thread = getThreadSafely_(
      row['ID conversation']
    );

    try {
      if (
        getBoolSetting_('FOLLOWUP_2_ENABLED') &&
        age >= CONFIG.FOLLOW_UP_2_DAYS &&
        !row['Relance 2 envoyée']
      ) {
        sendFollowUp_(
          thread,
          recipient,
          followUp2_(row)
        );

        writeFields_(context, sheetRow, {
          'À relancer': false,
          'Statut prospection': 'Relance 2',
          'Relance 2 envoyée': now,
          'Prochaine relance': '',
          'État envoi': 'Cycle terminé — attente de réponse',
          'Erreur envoi': ''
        });

        remaining--;
        Utilities.sleep(getNumberSetting_('SEND_DELAY_MS', 18000));
      } else if (
        age >= CONFIG.FOLLOW_UP_1_DAYS &&
        !row['Relance 1 envoyée']
      ) {
        sendFollowUp_(
          thread,
          recipient,
          followUp1_(row)
        );

        const followUp2On = getBoolSetting_('FOLLOWUP_2_ENABLED');

        writeFields_(context, sheetRow, {
          'À relancer': followUp2On,
          'Statut prospection': 'Relance 1',
          'Relance 1 envoyée': now,
          'Prochaine relance': followUp2On ? addDays_(sentAt, CONFIG.FOLLOW_UP_2_DAYS) : '',
          'État envoi': followUp2On
            ? 'Relance 1 envoyée'
            : 'Cycle terminé — attente de réponse',
          'Erreur envoi': ''
        });

        remaining--;
        Utilities.sleep(getNumberSetting_('SEND_DELAY_MS', 18000));
      }
    } catch (error) {
      writeFields_(context, sheetRow, {
        'État envoi': 'Erreur relance',
        'Erreur envoi': safeError_(error)
      });
    }
  }
}

// Répond réellement DANS le même fil Gmail (mêmes en-têtes In-Reply-To /
// References), au lieu d'envoyer un nouvel e-mail isolé avec juste « Re: »
// devant l'objet : le prospect voit la relance dans la conversation du
// premier message, pas comme un mail qui arrive « à froid ».
function sendFollowUp_(thread, recipient, body) {
  if (!isValidEmail_(recipient)) {
    throw new Error('Adresse de relance invalide.');
  }

  if (!thread) {
    throw new Error(
      'Conversation introuvable : relance bloquée ' +
      'pour éviter de relancer après une réponse non détectée.'
    );
  }

  if (hasExternalReply_(thread)) {
    throw new Error(
      'Réponse détectée : aucun mail de relance envoyé.'
    );
  }

  const messages = thread.getMessages();
  const lastMessage = messages[messages.length - 1];
  const options = mailOptions_();

  // Le texte de la relance reste simple (pas de gras, pas de bannière) pour
  // ne pas ressembler à un envoi automatisé dans une conversation déjà
  // entamée — seule la signature est identique au mail 1 (même design,
  // option 3). bodyWithoutSig = le texte sans la signature texte brut
  // ajoutée par followUp1_/followUp2_, pour ne pas la dupliquer dans le HTML.
  const bodyWithoutSig = body.split('\n\n' + buildSignaturePlainText_())[0];
  const emoji1 = getBoolSetting_('FORMAT_ENABLED') ? getSetting_('FORMAT_EMOJI_1').trim() : '';

  options.htmlBody = asciiSafeHtml_(
    '<div style="background:#ffffff;font-family:Arial,Helvetica,sans-serif;' +
    'font-size:14px;line-height:1.5;color:#202124;margin:0;">' +
    plainBodyToHtml_(bodyWithoutSig) +
    buildSignatureHtml_(emoji1) +
    '</div>'
  );

  lastMessage.replyAll(body, options);
}

// ---------------------------------------------------------------
// RELANCES "INTÉGRATION PROMISE" (J+7 / J+14)
// ---------------------------------------------------------------
// Pour les prospects qui ONT répondu (souvent positivement : "on va
// l'ajouter", "transmis en interne", etc.) mais qui n'ont jamais coché
// « Voix ajoutée (confirmée) » depuis. Le cycle de relance normal
// (processFollowUps_) s'arrête dès qu'une réponse est reçue — ce qui
// laisse ces conversations sans aucune relance automatique derrière.
// Contrairement à sendFollowUp_, on envoie volontairement ALORS QU'il y a
// déjà eu une réponse externe (c'est le but), donc pas de garde-fou
// hasExternalReply_ ici.
function sendIntegrationReminder_(thread, recipient, body) {
  if (!isValidEmail_(recipient)) {
    throw new Error('Adresse de relance intégration invalide.');
  }

  if (!thread) {
    throw new Error('Conversation introuvable : relance intégration bloquée.');
  }

  const messages = thread.getMessages();
  const lastMessage = messages[messages.length - 1];
  const options = mailOptions_();

  const bodyWithoutSig = body.split('\n\n' + buildSignaturePlainText_())[0];
  const emoji1 = getBoolSetting_('FORMAT_ENABLED') ? getSetting_('FORMAT_EMOJI_1').trim() : '';

  options.htmlBody = asciiSafeHtml_(
    '<div style="background:#ffffff;font-family:Arial,Helvetica,sans-serif;' +
    'font-size:14px;line-height:1.5;color:#202124;margin:0;">' +
    plainBodyToHtml_(bodyWithoutSig) +
    buildSignatureHtml_(emoji1) +
    '</div>'
  );

  lastMessage.replyAll(body, options);
}

function integrationFollowUp1_(row) {
  const saas = String(row['Nom du SaaS'] || 'your team').trim();
  return fillTemplate_(getSetting_('TPL_INTEGRATION_FU1'), saas) +
    '\n\n' + buildSignaturePlainText_();
}

function integrationFollowUp2_(row) {
  const saas = String(row['Nom du SaaS'] || 'your team').trim();
  return fillTemplate_(getSetting_('TPL_INTEGRATION_FU2'), saas) +
    '\n\n' + buildSignaturePlainText_();
}

// Relance les prospects qui ont répondu (positivement ou de façon neutre,
// mais pas un refus clair) et n'ont toujours pas coché « Voix ajoutée
// (confirmée) » : un rappel à J+7 depuis leur réponse, puis un dernier à
// J+14. Chaque étape n'est envoyée qu'une seule fois (colonnes dédiées).
//
// ARRÊT AUTOMATIQUE : dès que « Voix ajoutée (confirmée) » passe à TRUE —
// que ce soit coché à la main par Etienne, OU détecté automatiquement par
// l'IA de réponse (champ integration_confirmed dans processReplyAgentQueue_,
// ex. le prospect répond "it's live now") — cette fonction ignore
// immédiatement la ligne dès le prochain passage (voir le "continue" tout en
// haut de la boucle ci-dessous) : plus aucune relance J+7/J+14 ne part. La
// ligne est aussi migrée vers l'onglet « Partenaires actifs » au même moment
// par migrateConfirmedPartners_, donc une réponse positive confirmée arrête
// la relance ET fait avancer le prospect dans le même mouvement.
function processIntegrationReminders_(context) {
  if (!getBoolSetting_('INTEGRATION_REMINDER_ENABLED')) return;

  const now = new Date();
  const j1 = getNumberSetting_('INTEGRATION_REMINDER_J1', 7);
  const j2 = getNumberSetting_('INTEGRATION_REMINDER_J2', 14);

  // Même plafond + délai que processFollowUps_, pour la même raison : éviter
  // qu'un gros lot de réponses reçues le même jour ne déclenche une rafale
  // de relances d'intégration en une seule minute.
  let remaining = getNumberSetting_('MAX_FOLLOWUPS_PER_RUN', 10);

  for (let i = 0; i < context.rows.length && remaining > 0; i++) {
    const row = context.rows[i];

    if (!row['Nom du SaaS'] || row['Voix ajoutée (confirmée)'] === true) continue;
    if (!row['Dernière réponse']) continue;
    if (isPresentBanned_(row)) continue;

    const status = String(row['Statut prospection'] || '');

    if (/banni|doublon|partenaire actif/i.test(status)) continue;

    // Refus clair détecté par l'IA : on ne relance pas quelqu'un qui a dit non.
    if (/reject/i.test(String(row['Classification réponse IA'] || ''))) continue;

    // Une réponse de l'IA est déjà programmée ou en attente de validation
    // pour ce fil : pas besoin d'un rappel automatique en plus en même temps.
    if (/programmée|à valider/i.test(String(row['Statut réponse IA'] || ''))) continue;

    const replyDate = toDate_(row['Dernière réponse']);
    if (!replyDate) continue;

    const age = daysBetween_(replyDate, now);
    const recipient = String(row['Email public'] || '').trim();
    const sheetRow = CONFIG.FIRST_DATA_ROW + i;
    const thread = getThreadSafely_(row['ID conversation']);

    try {
      if (age >= j2 && !row['Relance intégration 2 envoyée']) {
        sendIntegrationReminder_(thread, recipient, integrationFollowUp2_(row));

        writeFields_(context, sheetRow, {
          'Relance intégration 2 envoyée': now
        });

        remaining--;
        Utilities.sleep(getNumberSetting_('SEND_DELAY_MS', 18000));
      } else if (age >= j1 && !row['Relance intégration 1 envoyée']) {
        sendIntegrationReminder_(thread, recipient, integrationFollowUp1_(row));

        writeFields_(context, sheetRow, {
          'Relance intégration 1 envoyée': now
        });

        remaining--;
        Utilities.sleep(getNumberSetting_('SEND_DELAY_MS', 18000));
      }
    } catch (error) {
      writeFields_(context, sheetRow, {
        'Notes / prochaine action': 'Erreur relance intégration : ' + safeError_(error)
      });
    }
  }
}

// Version HTML "simple" du corps d'une relance : paragraphes aérés, liens en
// bleu, mais sans gras ni émoji ni bannière (contrairement au mail 1), pour
// garder l'aspect naturel d'une relance dans une conversation déjà entamée.
function plainBodyToHtml_(body) {
  return String(body)
    .replace(/\r\n/g, '\n')
    .split(/\n{2,}/)
    .map(function (block) { return block.trim(); })
    .filter(Boolean)
    .map(function (paragraph) {
      let text = escapeHtml_(paragraph).replace(/\n/g, '<br>');

      text = text.replace(/https?:\/\/[^\s<]+/g, function (url) {
        return '<a href="' + url + '" style="color:#1155cc;text-decoration:underline;">' + url + '</a>';
      });

      return '<p style="margin:0 0 16px 0;">' + text + '</p>';
    })
    .join('');
}

// ---------------------------------------------------------------
// MESSAGES (modèles lus dans l'onglet Réglages)
// ---------------------------------------------------------------

function fillTemplate_(template, saas) {
  return String(template)
    .replace(/\{SAAS\}/g, saas)
    .replace(/\{VOICE_ID\}/g, VOICE_ID)
    .replace(/\{URL\}/g, CONFIG.SAMPLES_URL)
    .replace(/\{OPTOUT\}/g, getSetting_('OPTOUT_LINE'));
}

// present    : Corentin déjà visible dans le catalogue du SaaS
// importable : le SaaS accepte un voice_id externe
// catalog    : catalogue de voix / ElevenLabs confirmé, Corentin absent
// new-stack  : rien de prouvé (Non vérifié)
function prospectMode_(row) {
  const corentin = String(row['Corentin'] || '').toLowerCase();
  const evidence = String(row['Preuve ElevenLabs'] || '').toLowerCase();

  if (/non vérifié|not verified|à vérifier/.test(corentin)) {
    return 'new-stack';
  }

  if (/exact|présent|present|retrouv|visible/.test(corentin)) {
    return 'present';
  }

  if (/importable/.test(corentin)) {
    return 'importable';
  }

  if (/catalogue|elevenlabs|voice.?id/.test(corentin + ' ' + evidence)) {
    return 'catalog';
  }

  return 'new-stack';
}

// BANNISSEMENT ABSOLU : si la voix de Corentin est déjà confirmée présente
// chez ce SaaS ("Exact confirmé"), on ne doit plus jamais lui envoyer un
// message de type « votre voix y est déjà, mettez-la en avant » — ni premier
// contact, ni relance. Cet incident (JSON2Video a retiré la voix de son
// catalogue après un tel message) a coûté du revenu réel. Cette fonction est
// le garde-fou unique, vérifié avant tout envoi (premier contact ET relances).
//
// Trois signaux indépendants bannissent une ligne, pour ne jamais dépendre
// d'un seul champ qu'une découverte externe (ChatGPT) pourrait mal remplir :
//   1) Corentin = Exact confirmé / présent (prospectMode_ === 'present')
//   2) Statut prospection contient « Partenaire actif » (y compris la
//      migration automatique « Partenaire actif ✅ (déplacé) »)
//   3) Le SaaS figure déjà, par son nom normalisé, dans l'onglet
//      « Partenaires actifs » — même si une nouvelle ligne dupliquée est
//      recréée plus tard par la découverte externe sans ces deux champs.
function isPresentBanned_(row) {
  if (prospectMode_(row) === 'present') return true;

  const statut = String(row['Statut prospection'] || '').trim().toLowerCase();
  if (/partenaire actif/.test(statut)) return true;

  const name = normalizeName_(row['Nom du SaaS']);
  if (name && getKnownPartnerNames_()[name]) return true;

  return false;
}

// ---------------------------------------------------------------
// PASSAGE EN PARTENAIRE ACTIF (case « Voix ajoutée (confirmée) » cochée)
// ---------------------------------------------------------------

const PARTNERS_SHEET_NAME = 'Partenaires actifs';
const PARTNER_MIGRATED_STATUS = 'Partenaire actif ✅ (déplacé)';

// Cache mémoire (valable le temps d'une seule exécution du script) des noms
// de SaaS déjà listés dans l'onglet « Partenaires actifs », pour pouvoir
// vérifier isPresentBanned_ sur CHAQUE ligne sans relire la feuille à
// chaque fois. Fail open : si la lecture échoue, on ne bloque pas l'envoi
// pour autant (les signaux 1 et 2 restent actifs de toute façon).
let _knownPartnerNamesCache = null;

function getKnownPartnerNames_() {
  if (_knownPartnerNamesCache) return _knownPartnerNamesCache;

  const names = {};

  try {
    const ss = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
    const sheet = ss.getSheetByName(PARTNERS_SHEET_NAME);

    if (sheet) {
      const lastRow = sheet.getLastRow();

      if (lastRow >= 3) {
        sheet.getRange(3, 1, lastRow - 2, 1).getValues().forEach(function (line) {
          const name = normalizeName_(line[0]);
          if (name) names[name] = true;
        });
      }
    }
  } catch (error) {
    // Lecture impossible : on continue avec un cache vide pour cette
    // exécution plutôt que de faire planter l'envoi.
  }

  _knownPartnerNamesCache = names;
  return names;
}

function partnerCollabLabel_(row) {
  const label = {
    'catalog': 'Catalogue voix (ElevenLabs)',
    'importable': 'Voice ID importé',
    'new-stack': 'Intégration sur mesure',
    'present': 'Voix déjà présente'
  }[prospectMode_(row)];

  return label || 'Partenariat SaaS';
}

// Dès que la case « Voix ajoutée (confirmée) » est cochée pour un prospect
// (manuellement dans le Sheet, ou automatiquement par la réponse IA —
// voir processReplyAgentQueue_), ce prospect est : 1) ajouté à l'onglet
// « Partenaires actifs » du tableau de bord, 2) sorti du circuit de
// prospection (plus aucun premier mail ni relance ne lui sera envoyé).
// Idempotent : ne recrée jamais une ligne déjà présente côté
// « Partenaires actifs » et ignore les lignes déjà marquées migrées.
function migrateConfirmedPartners_(context) {
  const ss = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
  const sheet = ss.getSheetByName(PARTNERS_SHEET_NAME);

  if (!sheet) {
    console.log('Onglet "' + PARTNERS_SHEET_NAME + '" introuvable : migration ignorée.');
    return 0;
  }

  // Noms déjà présents dans l'onglet (à partir de la ligne 3, sous le
  // titre et l'en-tête), pour ne jamais ajouter deux fois le même SaaS.
  const existing = {};
  const lastRow = sheet.getLastRow();

  if (lastRow >= 3) {
    sheet.getRange(3, 1, lastRow - 2, 1).getValues().forEach(function (line) {
      const name = normalizeName_(line[0]);
      if (name) existing[name] = true;
    });
  }

  let moved = 0;

  context.rows.forEach(function (row, index) {
    if (!row['Nom du SaaS']) return;
    if (row['Voix ajoutée (confirmée)'] !== true) return;
    if (String(row['Statut prospection']).trim() === PARTNER_MIGRATED_STATUS) return;

    const name = String(row['Nom du SaaS']).trim();
    const key = normalizeName_(name);

    if (!existing[key]) {
      sheet.appendRow([
        name,
        '✅ Actif',
        partnerCollabLabel_(row),
        fmtDate_(new Date())
      ]);
      existing[key] = true;
      moved++;
    }

    writeFields_(context, CONFIG.FIRST_DATA_ROW + index, {
      'Statut prospection': PARTNER_MIGRATED_STATUS,
      'À relancer': false,
      'Prochaine relance': '',
      'Envoyer': false
    });
  });

  return moved;
}

// Menu : déplacement immédiat, sans attendre le passage horaire automatique.
function migratePartnersNow() {
  assertRequiredHeaders_();

  const context = getContext_();
  const moved = migrateConfirmedPartners_(context);

  notify_(
    moved
      ? moved + ' partenaire(s) déplacé(s) vers « ' + PARTNERS_SHEET_NAME + ' ».'
      : 'Aucun nouveau partenaire à déplacer (aucune case « Voix ajoutée (confirmée) » ' +
        'non traitée).'
  );
}

function buildInitialDraft_(row) {
  const saas = String(row['Nom du SaaS'] || 'your product').trim();

  const keys = {
    'present': 'TPL_PRESENT',
    'catalog': 'TPL_CATALOG',
    // Fusionné avec « catalog » : la confirmation "voice_id externe accepté"
    // en BYOK ne veut pas dire que la voix est déjà listée publiquement, donc
    // même message d'ouverture que « catalogue, Corentin absent ».
    'importable': 'TPL_CATALOG',
    'new-stack': 'TPL_NEWSTACK'
  };

  const mode = prospectMode_(row);
  const draft = fillTemplate_(getSetting_(keys[mode]), saas);
  const subject = fillTemplate_(
    getSetting_(mode === 'new-stack' ? 'SUBJECT_NEWSTACK' : 'SUBJECT_MAIN'),
    saas
  );

  return /^Subject:/m.test(draft)
    ? draft.replace(/^Subject:.*$/m, function () { return 'Subject: ' + subject; })
    : 'Subject: ' + subject + '\n\n' + draft;
}

function followUp1_(row) {
  const saas = String(row['Nom du SaaS'] || 'your team').trim();
  const keys = {
    'present': 'FU1_PRESENT',
    'new-stack': 'FU1_PLATFORM',
    'catalog': 'FU1_LIBRARY',
    'importable': 'FU1_LIBRARY'
  };

  return fillTemplate_(getSetting_(keys[prospectMode_(row)]), saas) +
    '\n\n' + buildSignaturePlainText_();
}

function followUp2_(row) {
  const saas = String(row['Nom du SaaS'] || 'your team').trim();
  const keys = {
    'present': 'FU2_PRESENT',
    'new-stack': 'FU2_PLATFORM',
    'catalog': 'FU2_LIBRARY',
    'importable': 'FU2_LIBRARY'
  };

  return fillTemplate_(getSetting_(keys[prospectMode_(row)]), saas) +
    '\n\n' + buildSignaturePlainText_();
}

// ---------------------------------------------------------------
// DÉCOUVERTE QUOTIDIENNE (API Claude + recherche web + vérifications)
// ---------------------------------------------------------------

function discoverProspectsDaily() {
  const lock = LockService.getScriptLock();

  if (!lock.tryLock(30000)) return;

  const startedAt = Date.now();

  try {
    const enriched = prepareBaseDaily_();
    const summary = discoverProspects_(120000);

    logHistory_('Découverte auto', {
      seconds: Math.round((Date.now() - startedAt) / 1000),
      enriched: enriched.found.length,
      proposed: summary.proposed,
      added: summary.added.length,
      rejected: summary.rejected.length,
      notes: summary.errors.join(' | ')
    });
  } catch (error) {
    saveDiscoveryFailure_(error);
    logHistory_('Découverte auto', { notes: safeError_(error) });
  } finally {
    lock.releaseLock();
  }
}

function saveDiscoveryFailure_(error) {
  PropertiesService.getScriptProperties().setProperty(
    'LAST_DISCOVERY',
    JSON.stringify({
      date: new Date().toISOString(),
      added: [],
      rejected: [],
      errors: [safeError_(error)],
      segments: [],
      details: [],
      proposed: 0
    })
  );
}

function discoverProspectsNow() {
  const lock = LockService.getScriptLock();

  if (!lock.tryLock(30000)) {
    throw new Error('Traitement en cours. Réessayez ensuite.');
  }

  let summary;

  try {
    summary = discoverProspects_();
  } finally {
    lock.releaseLock();
  }

  notify_(
    summary.added.length + ' prospect(s) ajouté(s), ' +
    summary.rejected.length + ' écarté(s)' +
    (summary.errors.length
      ? '. Erreurs : ' + summary.errors.join(' | ')
      : '.') +
    (summary.added.length
      ? ' Ajoutés : ' + summary.added.join(', ')
      : '')
  );
}

function discoverProspects_(budgetMs) {
  const budget = budgetMs || 240000;
  const props = PropertiesService.getScriptProperties();
  const apiKey = props.getProperty('ANTHROPIC_API_KEY');

  if (!apiKey) {
    throw new Error(
      'Clé API Claude absente (menu Prospection > Enregistrer la clé API Claude).'
    );
  }

  assertRequiredHeaders_();

  const started = Date.now();
  const context = getContext_();
  const known = buildKnownIndex_(context);
  const segments = getSegments_();

  if (!segments.length) {
    throw new Error('Aucun segment dans l’onglet Réglages (SEGMENT_1...).');
  }

  const maxCalls = getNumberSetting_('DISCOVERY_MAX_CALLS', 3);
  const perCall = getNumberSetting_('DISCOVERY_PER_CALL', 3);

  let index = Number(props.getProperty('SEGMENT_INDEX') || 0);

  const summary = {
    date: new Date().toISOString(),
    added: [],
    rejected: [],
    errors: [],
    segments: [],
    details: [],
    proposed: 0
  };

  for (let call = 0; call < maxCalls; call++) {
    if (Date.now() - started > budget) break;

    const segment = segments[index % segments.length];
    index++;

    summary.segments.push(segment.label);

    let candidates = [];

    try {
      candidates = askClaudeForProspects_(
        apiKey,
        segment,
        perCall,
        known.domains
      );
    } catch (error) {
      summary.errors.push(safeError_(error));
      continue;
    }

    if (!candidates.length) {
      summary.errors.push(
        'Aucun prospect exploitable pour « ' + segment.label + ' ». ' +
        'Réponse de Claude : ' + LAST_RAW_.slice(0, 500)
      );
    }

    summary.proposed += candidates.length;

    candidates.forEach(function (candidate) {
      if (Date.now() - started > budget + 80000) return;

      const result = qualifyCandidate_(candidate, segment, known);

      summary.details.push({
        segment: segment.label,
        name: String(candidate && candidate.name || '?').slice(0, 60),
        site: String(candidate && candidate.site || '').slice(0, 80),
        claimedStatus: result.diag.claimedStatus,
        finalStatus: result.diag.finalStatus,
        claimedEmail: result.diag.claimedEmail.slice(0, 60),
        emailVerified: result.diag.emailVerified,
        contactOk: result.diag.contactOk,
        result: result.ok ? 'Ajouté' : 'Écarté',
        reason: result.ok ? '' : result.reason
      });

      if (!result.ok) {
        summary.rejected.push(
          String(candidate && candidate.name || '?') + ' (' + result.reason + ')'
        );
        return;
      }

      appendProspectRow_(context, result.fields);
      known.add(result.host, result.fields['Nom du SaaS']);
      summary.added.push(
        result.fields['Nom du SaaS'] +
        (result.fields['Envoyer'] ? '' : ' [à valider]')
      );
    });
  }

  props.setProperty('SEGMENT_INDEX', String(index % segments.length));

  let stored = JSON.stringify(summary);

  if (stored.length > 8500) {
    stored = JSON.stringify(Object.assign({}, summary, { details: [] }));
  }

  props.setProperty('LAST_DISCOVERY', stored);

  return summary;
}

function buildKnownIndex_(context) {
  const hosts = {};
  const names = {};

  context.rows.forEach(function (row) {
    [row['Site'], row['Domaine canonique']].forEach(function (value) {
      const host = hostOf_(value);
      if (host) hosts[host] = true;
    });

    const name = normalizeName_(row['Nom du SaaS']);
    if (name) names[name] = true;
  });

  return {
    domains: Object.keys(hosts),
    has: function (host, name) {
      return !!(hosts[host] || names[normalizeName_(name)]);
    },
    add: function (host, name) {
      if (host) {
        hosts[host] = true;
        this.domains = Object.keys(hosts);
      }
      const normalized = normalizeName_(name);
      if (normalized) names[normalized] = true;
    }
  };
}

function hostOf_(value) {
  const match = String(value || '')
    .toLowerCase()
    .match(/^(?:https?:\/\/)?([a-z0-9.-]+\.[a-z]{2,})/);

  return match ? match[1].replace(/^www\./, '') : '';
}

function normalizeName_(value) {
  return String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
}

function askClaudeForProspects_(apiKey, segment, count, knownDomains) {
  const system =
    'Tu es l’analyste de prospection de Corentin AI Voice. Tu cherches des ' +
    'SaaS réels et vérifiables à qui proposer d’ajouter la voix française ' +
    '« Corentin — Young and Dynamic » (ElevenLabs Voice ID ' + VOICE_ID + ').\n' +
    'RÈGLES ABSOLUES :\n' +
    '- Ne retenir que des SaaS actifs dont le site officiel montre une ' +
    'génération vidéo ou vocale avec voix off.\n' +
    '- N’invente JAMAIS une adresse e-mail, une intégration ou une ' +
    'compatibilité. Un e-mail n’est valable que s’il est écrit tel quel sur ' +
    'une page publique officielle (partenariats, business, sales, produit ou ' +
    'support), avec l’URL exacte de cette page.\n' +
    '- Pas d’adresse personnelle, pas d’adresse déduite d’un modèle.\n' +
    '- Ne pas présumer d’un besoin français sans indice.\n' +
    '- Statuts autorisés : exact (Voice ID exact trouvé sur une source ' +
    'officielle), importable (la documentation officielle accepte un ' +
    'voice_id ElevenLabs externe), catalog (ElevenLabs explicitement mentionné ' +
    'et catalogue de voix, Corentin absent), unverified (rien de prouvé).\n' +
    '- Aucune affirmation chiffrée, aucun « numéro 1 ».\n' +
    '- Réponds UNIQUEMENT par un tableau JSON, sans texte autour ni balises.';

  const user =
    'Segment : ' + segment.label + '\n' +
    'Marchés / langues à explorer : ' + segment.languages + '\n' +
    'Nombre de prospects voulus : ' + count + ' (moins si peu sont solides).\n' +
    'Domaines DÉJÀ dans la base, à exclure : ' +
    (knownDomains.slice(0, 200).join(', ') || 'aucun') + '\n\n' +
    'Format de chaque élément :\n' +
    '{"name":"","site":"https://...","language":"EN","type":"","precise_type":"",' +
    '"elevenlabs_status":"exact|importable|catalog|unverified",' +
    '"evidence_url":"","evidence_note":"","email":"","email_source_url":"",' +
    '"contact_url":"","priority":3}\n' +
    'Laisse une chaîne vide quand une information n’est pas confirmée.';

  const messages = [{ role: 'user', content: user }];
  let text = '';
  let stopReason = '';

  for (let turn = 0; turn < 3; turn++) {
    const response = UrlFetchApp.fetch(CONFIG.API_URL, {
      method: 'post',
      contentType: 'application/json',
      headers: {
        'x-api-key': apiKey,
        'anthropic-version': CONFIG.API_VERSION
      },
      payload: JSON.stringify({
        model: getSetting_('MODEL') || 'claude-sonnet-5',
        max_tokens: 8000,
        system: system,
        tools: [{ type: 'web_search_20250305', name: 'web_search', max_uses: 5 }],
        messages: messages
      }),
      muteHttpExceptions: true
    });

    const code = response.getResponseCode();
    const data = JSON.parse(response.getContentText());

    if (code !== 200) {
      throw new Error(
        'API Claude ' + code + ' : ' +
        String(data && data.error && data.error.message || 'erreur')
      );
    }

    text = (data.content || [])
      .filter(function (block) { return block.type === 'text'; })
      .map(function (block) { return block.text; })
      .join('\n');

    stopReason = String(data.stop_reason || '');

    if (data.stop_reason === 'pause_turn') {
      messages.push({ role: 'assistant', content: data.content });
      continue;
    }

    break;
  }

  LAST_RAW_ = '[fin=' + stopReason + '] ' + String(text).replace(/\s+/g, ' ');

  return extractJsonArray_(text);
}

// Récupère les objets complets d'un tableau JSON coupé (réponse arrêtée par max_tokens).
function salvageJsonObjects_(text) {
  const value = String(text || '');
  const start = value.indexOf('[');

  if (start < 0) return [];

  const objects = [];
  let depth = 0;
  let inString = false;
  let escaped = false;
  let objectStart = -1;

  for (let i = start + 1; i < value.length; i++) {
    const ch = value[i];

    if (inString) {
      if (escaped) escaped = false;
      else if (ch === '\\') escaped = true;
      else if (ch === '"') inString = false;
      continue;
    }

    if (ch === '"') {
      inString = true;
    } else if (ch === '{') {
      if (depth === 0) objectStart = i;
      depth++;
    } else if (ch === '}') {
      depth--;

      if (depth === 0 && objectStart >= 0) {
        try {
          objects.push(JSON.parse(value.slice(objectStart, i + 1)));
        } catch (error) {
          // objet illisible : on l'ignore
        }

        objectStart = -1;
      }
    }
  }

  return objects;
}

function extractJsonArray_(text) {
  const value = String(text || '');
  const end = value.lastIndexOf(']');

  if (end >= 0) {
    let start = value.indexOf('[');
    let tries = 0;

    while (start >= 0 && start < end && tries < 40) {
      try {
        const parsed = JSON.parse(value.slice(start, end + 1));

        if (Array.isArray(parsed)) return parsed;
      } catch (error) {
        // On essaie le « [ » suivant (texte d'introduction avec crochets).
      }

      start = value.indexOf('[', start + 1);
      tries++;
    }
  }

  return salvageJsonObjects_(value);
}

function fetchPage_(url) {
  const clean = String(url || '').trim();

  if (!/^https?:\/\//i.test(clean)) {
    return { ok: false, text: '' };
  }

  try {
    const response = UrlFetchApp.fetch(clean, {
      muteHttpExceptions: true,
      followRedirects: true,
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; CorentinVoiceCheck/1.0)' }
    });

    const code = response.getResponseCode();

    return {
      ok: code >= 200 && code < 400,
      text: String(response.getContentText() || '')
        .slice(0, 600000)
        .replace(/&#0*64;|&commat;/gi, '@')
        .toLowerCase()
    };
  } catch (error) {
    return { ok: false, text: '' };
  }
}

// Dernier filet de sécurité avant envoi : revisite le site du prospect (et
// ses pages de preuve déjà connues) et cherche l'ID ElevenLabs exact de
// Corentin dans le HTML. Sert de backstop indépendant du système externe de
// découverte (ChatGPT), au cas où la voix aurait été ajoutée APRÈS la
// découverte du prospect, ou si la colonne "Corentin" a été mal renseignée.
// Fail open : si aucune page ne répond, on ne bloque pas l'envoi pour autant.
function recheckVoicePresence_(row) {
  const needle = String(VOICE_ID || '').trim().toLowerCase();

  if (!needle) return { checked: false, present: false, url: '' };

  const candidates = [
    row['Catalogue public'],
    row['Preuve ElevenLabs'],
    row['Page de contact'],
    row['Site']
  ];

  const seen = {};
  let anyFetched = false;

  for (let i = 0; i < candidates.length; i++) {
    const clean = String(candidates[i] || '').trim();

    if (!clean || seen[clean]) continue;
    seen[clean] = true;

    const page = fetchPage_(clean);

    if (!page.ok) continue;
    anyFetched = true;

    if (page.text.indexOf(needle) !== -1) {
      return { checked: true, present: true, url: clean };
    }
  }

  return { checked: anyFetched, present: false, url: '' };
}

function emailVerified_(email, urls, host) {
  const value = String(email || '').trim().toLowerCase();

  if (!isValidEmail_(value)) return false;
  if (/^(no-?reply|do-?not-?reply)@/.test(value)) return false;

  const domain = value.split('@')[1];

  if (
    !(domain === host || domain.endsWith('.' + host) || host.endsWith('.' + domain))
  ) {
    return false;
  }

  const seen = {};

  return urls.some(function (url) {
    const clean = String(url || '').trim();

    if (!clean || seen[clean]) return false;
    seen[clean] = true;

    const page = fetchPage_(clean);
    return page.ok && page.text.indexOf(value) !== -1;
  });
}

function qualifyCandidate_(candidate, segment, known) {
  const diag = {
    claimedStatus: String(candidate && candidate.elevenlabs_status || ''),
    finalStatus: '',
    claimedEmail: String(candidate && candidate.email || ''),
    emailVerified: false,
    contactOk: false
  };

  if (!candidate || !candidate.name || !candidate.site) {
    return { ok: false, diag: diag, reason: 'données incomplètes' };
  }

  const name = clean_(candidate.name).slice(0, 80);
  const host = hostOf_(candidate.site);

  if (!host) return { ok: false, diag: diag, reason: 'site invalide' };

  const blocked = String(getSetting_('BLOCKLIST_DOMAINS'))
    .toLowerCase()
    .split(',')
    .map(function (item) { return item.trim(); })
    .filter(Boolean);

  if (blocked.indexOf(host) !== -1) {
    return { ok: false, diag: diag, reason: 'domaine bloqué' };
  }

  if (known.has(host, name)) {
    return { ok: false, diag: diag, reason: 'doublon' };
  }

  const site = fetchPage_(candidate.site);

  if (!site.ok) return { ok: false, diag: diag, reason: 'site inaccessible' };

  if (!/(video|vidéo|voice|voix|tts|text.to.speech|narrat)/.test(site.text)) {
    return { ok: false, diag: diag, reason: 'aucune fonction vidéo/voix visible' };
  }

  // Statut de preuve : vérifié dans le script, jamais amélioré, seulement dégradé.
  const labels = {
    exact: 'Exact confirmé',
    importable: 'Importable par ID',
    catalog: 'Catalogue ElevenLabs',
    unverified: 'Non vérifié'
  };

  let status = labels[String(candidate.elevenlabs_status || '').toLowerCase()] ||
    'Non vérifié';

  if (status !== 'Non vérifié') {
    const evidence = fetchPage_(candidate.evidence_url);
    let confirmed = false;

    if (evidence.ok) {
      if (status === 'Exact confirmé') {
        confirmed = evidence.text.indexOf(VOICE_ID.toLowerCase()) !== -1;
      } else if (status === 'Importable par ID') {
        confirmed =
          evidence.text.indexOf('elevenlabs') !== -1 &&
          /voice[_\s-]?id/.test(evidence.text);
      } else {
        confirmed = evidence.text.indexOf('elevenlabs') !== -1;
      }
    }

    if (!confirmed) status = 'Non vérifié';
  }

  let emailOk = emailVerified_(
    candidate.email,
    [candidate.email_source_url, candidate.contact_url, candidate.site],
    host
  );

  let finalEmail = emailOk ? String(candidate.email).trim().toLowerCase() : '';

  if (!emailOk) {
    finalEmail = findEmailOnSite_(candidate.site, candidate.contact_url);
    emailOk = !!finalEmail;
  }

  const contactPage = fetchPage_(candidate.contact_url);

  const emailCell = emailOk
    ? finalEmail
    : (contactPage.ok
        ? 'Formulaire — ' + String(candidate.contact_url).trim()
        : 'Non public');

  diag.finalStatus = status;
  diag.emailVerified = emailOk;
  diag.contactOk = contactPage.ok;

  // BANNISSEMENT ABSOLU : un SaaS où la voix est déjà confirmée présente ne
  // doit jamais être mis en envoi auto, ni recevoir un message « mettez-la
  // en avant » — voir isPresentBanned_.
  const autoSend = status !== 'Exact confirmé' && emailOk && getBoolSetting_('AUTO_SEND');

  const preuve = status === 'Non vérifié'
    ? 'Non vérifié'
    : clean_(candidate.evidence_note || 'Source officielle').slice(0, 200);

  const actions = {
    'Exact confirmé': 'Banni — voix déjà présente, ne pas contacter',
    'Importable par ID': 'Proposer un preset FR',
    'Catalogue ElevenLabs': 'Demander ajout à la liste publique',
    'Non vérifié': 'Vérifier la compatibilité voix externe'
  };

  const today = Utilities.formatDate(new Date(), CONFIG.TIME_ZONE, 'yyyy-MM-dd');
  const priority = Math.min(5, Math.max(1, Number(candidate.priority) || 3));

  const fields = {
    'Type de SaaS': clean_(candidate.type || segment.label).slice(0, 120),
    'Nom du SaaS': name,
    'Site': String(candidate.site).trim(),
    'Email public': emailCell,
    'Message de contact': buildInitialDraft_({
      'Nom du SaaS': name,
      'Corentin': status,
      'Preuve ElevenLabs': preuve
    }),
    'Envoyer': autoSend,
    'À relancer': false,
    'Statut prospection': status === 'Exact confirmé' ? 'Banni — voix déjà présente' : 'À contacter',
    'Zone / langue': clean_(candidate.language).slice(0, 60),
    'Type précis': clean_(candidate.precise_type).slice(0, 200),
    'Corentin': status,
    'Action recommandée': actions[status],
    'Priorité': priority,
    'Preuve ElevenLabs': preuve,
    'Page de contact': String(candidate.contact_url || candidate.site).trim(),
    'Source preuve': String(candidate.evidence_url || '').trim(),
    'Date vérification': today,
    'Notes / prochaine action':
      'Ajouté automatiquement le ' + today + ' — ' + segment.label +
      (autoSend ? '' : ' — à traiter manuellement (pas d’e-mail vérifié ou envoi auto désactivé)')
  };

  return { ok: true, fields: fields, host: host, diag: diag };
}

// Adresses génériques utiles, par ordre de préférence. Aucune adresse déduite :
// l'adresse doit être écrite telle quelle sur une page du site officiel.
const EMAIL_PREFIXES = [
  'partnerships', 'partners', 'partner', 'business', 'bd', 'sales', 'product',
  'hello', 'contact', 'support', 'info', 'team'
];

function findEmailOnSite_(site, contactUrl) {
  const host = hostOf_(site);

  if (!host) return '';

  const base = String(site).trim().replace(/^(https?:\/\/[^\/]+).*$/i, '$1');
  const urls = [];

  [contactUrl, base + '/contact', base + '/contact-us', base + '/about',
    base + '/support', base + '/legal', base + '/mentions-legales', base + '/'
  ].forEach(function (url) {
    const clean = String(url || '').trim();

    if (/^https?:\/\//i.test(clean) && urls.indexOf(clean) === -1) {
      urls.push(clean);
    }
  });

  const found = {};

  for (let i = 0; i < urls.length; i++) {
    const page = fetchPage_(urls[i]);

    if (!page.ok) continue;

    (page.text.match(/[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}/g) || []).forEach(
      function (email) {
        const domain = email.split('@')[1];

        if (domain === host || domain.endsWith('.' + host)) {
          found[email] = true;
        }
      }
    );

    if (Object.keys(found).length) break;
  }

  const emails = Object.keys(found);

  for (let p = 0; p < EMAIL_PREFIXES.length; p++) {
    const match = emails.filter(function (email) {
      return email.split('@')[0] === EMAIL_PREFIXES[p];
    });

    if (match.length) return match[0];
  }

  return '';
}

function nextProspectId_(context) {
  let max = 0;

  context.rows.forEach(function (row) {
    const match = String(row['ID prospect'] || '').match(/^P-(\d+)$/);
    if (match) max = Math.max(max, Number(match[1]));
  });

  return 'P-' + ('0000' + (max + 1)).slice(-4);
}

// Première ligne dont « Nom du SaaS » est vide, en partant du haut.
// (getLastRow() est faussé par les cases à cocher pré-remplies en bas.)
function firstFreeRow_(context) {
  const sheet = context.sheet;
  const column = context.map['Nom du SaaS'];
  const count = sheet.getMaxRows() - CONFIG.FIRST_DATA_ROW + 1;

  if (count <= 0) return CONFIG.FIRST_DATA_ROW;

  const values = sheet
    .getRange(CONFIG.FIRST_DATA_ROW, column, count, 1)
    .getValues();

  for (let i = 0; i < values.length; i++) {
    if (!String(values[i][0] || '').trim()) {
      return CONFIG.FIRST_DATA_ROW + i;
    }
  }

  return CONFIG.FIRST_DATA_ROW + values.length;
}

// Retire les balises (ex. <cite ...>) que la recherche web glisse dans le texte.
function clean_(value) {
  return String(value || '')
    .replace(/<[^>]*>/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function appendProspectRow_(context, fields) {
  const sheet = context.sheet;
  const lastColumn = sheet.getLastColumn();
  const newRow = firstFreeRow_(context);

  // Plus de ligne libre dans la feuille : on en ajoute et on copie le format.
  if (newRow > sheet.getMaxRows()) {
    sheet.insertRowsAfter(sheet.getMaxRows(), newRow - sheet.getMaxRows());

    if (newRow > CONFIG.FIRST_DATA_ROW) {
      const source = sheet.getRange(newRow - 1, 1, 1, lastColumn);
      const target = sheet.getRange(newRow, 1, 1, lastColumn);

      source.copyTo(target, SpreadsheetApp.CopyPasteType.PASTE_FORMAT, false);
      source.copyTo(target, SpreadsheetApp.CopyPasteType.PASTE_DATA_VALIDATION, false);
    }
  }

  const all = {};
  all['ID prospect'] = nextProspectId_(context);
  Object.keys(fields).forEach(function (key) { all[key] = fields[key]; });

  const rowObject = {};

  Object.keys(all).forEach(function (header) {
    const column = context.map[header];

    if (!column) return;

    sheet.getRange(newRow, column).setValue(all[header]);
    rowObject[header] = all[header];
  });

  const index = newRow - CONFIG.FIRST_DATA_ROW;

  if (index < context.rows.length) {
    context.rows[index] = rowObject;
  } else if (index === context.rows.length) {
    context.rows.push(rowObject);
  }
}

// ---------------------------------------------------------------
// RAPPORT QUOTIDIEN
// ---------------------------------------------------------------

function sendDailyReport() {
  const context = getContext_();
  const to = String(getSetting_('REPORT_TO')).trim() ||
    Session.getEffectiveUser().getEmail();

  if (!isValidEmail_(to)) {
    throw new Error('Adresse de rapport invalide.');
  }

  const report = buildDailyReport_(context);

  GmailApp.sendEmail(to, report.subject, report.body, {
    name: 'Machine de prospection'
  });
}

function sendDailyReportNow() {
  sendDailyReport();
  notify_('Rapport envoyé.');
}

function buildDailyReport_(context) {
  const since = Date.now() - 24 * 3600 * 1000;

  function recent(value) {
    const date = toDate_(value);
    return !!date && date.getTime() >= since;
  }

  const rows = context.rows.filter(function (row) { return row['Nom du SaaS']; });

  const sent = rows.filter(function (row) { return recent(row['Date envoi']); });
  const fu1 = rows.filter(function (row) { return recent(row['Relance 1 envoyée']); });
  const fu2 = rows.filter(function (row) { return recent(row['Relance 2 envoyée']); });
  const replies = rows.filter(function (row) { return recent(row['Dernière réponse']); });

  const errors = rows.filter(function (row) {
    return /^(erreur|bloqué)/i.test(String(row['État envoi'] || ''));
  });

  const queue = rows.filter(function (row) {
    return row['Envoyer'] === true && !row['Date envoi'];
  });

  // Combien seront réellement tentés aujourd'hui, pas juste combien attendent
  // en file (qui peut être un gros chiffre qui s'étale sur plusieurs jours).
  const todayStr = Utilities.formatDate(new Date(), CONFIG.TIME_ZONE, 'yyyy-MM-dd');

  function isToday(value) {
    const date = toDate_(value);
    return !!date && Utilities.formatDate(date, CONFIG.TIME_ZONE, 'yyyy-MM-dd') === todayStr;
  }

  const sentToday = rows.filter(function (row) { return isToday(row['Date envoi']); }).length;
  const dailyLimit = getNumberSetting_('DAILY_LIMIT', 50);
  const remainingToday = Math.max(0, dailyLimit - sentToday);
  const plannedToday = Math.min(queue.length, remainingToday);

  const toContact = rows.filter(function (row) {
    return String(row['Statut prospection']).trim() === 'À contacter' &&
      !row['Date envoi'];
  });

  const toContactWithEmail = toContact.filter(function (row) {
    return isValidEmail_(String(row['Email public'] || '').trim());
  });

  const contactedTotal = rows.filter(function (row) { return row['Date envoi']; }).length;
  const repliesTotal = rows.filter(function (row) { return row['Dernière réponse']; }).length;
  const bounces = recentBounceCount_(context);
  const maxBounces = getNumberSetting_('MAX_BOUNCES_PAUSE', 3);

  let discovery = null;

  try {
    discovery = JSON.parse(
      PropertiesService.getScriptProperties().getProperty('LAST_DISCOVERY') || 'null'
    );
  } catch (error) {
    discovery = null;
  }

  function names(list) {
    return list.length
      ? list.map(function (row) { return row['Nom du SaaS']; }).join(', ')
      : 'aucun';
  }

  const lines = [];

  lines.push('RAPPORT DES DERNIÈRES 24 H');
  lines.push('');
  lines.push('Envois');
  lines.push('- Premiers e-mails : ' + sent.length + ' (' + names(sent) + ')');
  lines.push('- Relances 1 : ' + fu1.length + ' | Relances 2 : ' + fu2.length);
  lines.push('- Réponses reçues : ' + replies.length + ' (' + names(replies) + ')');
  lines.push('- Rebonds sur 3 jours : ' + bounces);
  lines.push('- Erreurs : ' + errors.length + (errors.length ? ' (' + names(errors) + ')' : ''));
  lines.push('');
  lines.push('Découverte');

  if (discovery) {
    lines.push('- Dernière exécution : ' + discovery.date);
    lines.push('- Segments : ' + (discovery.segments.join(' ; ') || 'aucun'));
    lines.push('- Ajoutés : ' + (discovery.added.join(', ') || 'aucun'));
    lines.push('- Écartés : ' + discovery.rejected.length +
      (discovery.rejected.length ? ' (' + discovery.rejected.slice(0, 8).join(' ; ') + ')' : ''));

    if (discovery.errors.length) {
      lines.push('- Erreurs : ' + discovery.errors.join(' | '));
    }
  } else {
    lines.push('- Aucune exécution enregistrée.');
  }

  lines.push('');
  lines.push('File');
  lines.push('- 📅 Programmés pour AUJOURD’HUI (' + todayStr + ') : ' + plannedToday +
    ' (déjà envoyés aujourd’hui : ' + sentToday + ' / limite ' + dailyLimit + ')');
  lines.push('- En attente d’envoi automatique (total, plusieurs jours) : ' + queue.length);
  lines.push('- « À contacter » : ' + toContact.length +
    ' (dont ' + toContactWithEmail.length + ' avec e-mail valide)');
  lines.push('');
  lines.push('Totaux');
  lines.push('- Prospects contactés : ' + contactedTotal);
  lines.push('- Réponses : ' + repliesTotal +
    (contactedTotal ? ' (' + Math.round(100 * repliesTotal / contactedTotal) + ' %)' : ''));
  lines.push('');
  lines.push('État');
  lines.push('- Envoi automatique (AUTO_SEND) : ' + (getBoolSetting_('AUTO_SEND') ? 'actif' : 'désactivé'));
  lines.push('- Interrupteur général (MASTER_PAUSE) : ' + (getBoolSetting_('MASTER_PAUSE') ? '⚠ EN PAUSE' : 'actif'));
  lines.push('- Fenêtre d’envoi : ' +
    (getBoolSetting_('WEEKDAYS_ONLY') ? 'lun-ven' : '7j/7') + ', ' +
    getSetting_('SEND_START_HOUR') + 'h-' + getSetting_('SEND_END_HOUR') + 'h (Paris)');
  lines.push('- Délai entre envois (SEND_DELAY_MS) : ' + getNumberSetting_('SEND_DELAY_MS', 18000) + ' ms');
  lines.push('- Max envois / passage (MAX_SENDS_PER_RUN) : ' + getNumberSetting_('MAX_SENDS_PER_RUN', 5));
  lines.push('- Relance 2 (FOLLOWUP_2_ENABLED) : ' + (getBoolSetting_('FOLLOWUP_2_ENABLED') ? 'active' : 'désactivée'));

  if (bounces >= maxBounces) {
    lines.push('- ℹ ' + bounces + ' rebond(s) récent(s) (3 j) — informatif uniquement, ' +
      'les envois ne sont plus suspendus pour ça (vérification d’adresse active avant envoi).');
  }

  lines.push('');
  lines.push('Diagnostic — rafale d’envoi');

  const burstCheck = detectSendBurst_(rows, since);

  if (burstCheck.count < 2) {
    lines.push('- Pas assez d’envois sur 24h pour vérifier l’espacement.');
  } else if (burstCheck.minGapSeconds < 10) {
    lines.push('- ⚠ Écart minimum observé entre deux envois : ' + burstCheck.minGapSeconds +
      ' s (entre "' + burstCheck.minGapPair[0] + '" et "' + burstCheck.minGapPair[1] +
      '"). Ça ressemble à une rafale — vérifier SEND_DELAY_MS et le code déployé.');
  } else {
    lines.push('- OK : écart minimum entre deux envois = ' + burstCheck.minGapSeconds + ' s.');
  }

  lines.push('');
  lines.push('Diagnostic — version du code');

  const codeCheck = checkCodeVersion_();

  if (codeCheck.changed) {
    lines.push('- ℹ Code mis à jour depuis le dernier rapport : "' + codeCheck.previous +
      '" → "' + codeCheck.current + '". Vérifier qu’un envoi de test a bien été fait après le collage.');
  } else {
    lines.push('- Version inchangée depuis le dernier rapport (' + codeCheck.current + ').');
  }

  lines.push('');
  lines.push('Diagnostic — dernier mail 1 réellement envoyé');
  lines.push(lastSentSampleLines_().join('\n'));

  const day = Utilities.formatDate(new Date(), CONFIG.TIME_ZONE, 'dd/MM/yyyy');

  return {
    subject: 'Prospection Corentin AI Voice — rapport du ' + day,
    body: lines.join('\n')
  };
}

// Regarde tous les envois des dernières 24h (1ers mails + relances) et
// renvoie l'écart minimum observé entre deux envois consécutifs, pour
// détecter un pattern de rafale (le bug corrigé le 10/10 : 15 mails en
// 12 secondes à cause d'un Utilities.sleep(800) au lieu du réglage
// SEND_DELAY_MS).
function detectSendBurst_(rows, since) {
  const events = [];

  rows.forEach(function (row) {
    ['Date envoi', 'Relance 1 envoyée', 'Relance 2 envoyée'].forEach(function (field) {
      const date = toDate_(row[field]);

      if (date && date.getTime() >= since) {
        events.push({ at: date.getTime(), label: String(row['Nom du SaaS'] || '?') + ' (' + field + ')' });
      }
    });
  });

  events.sort(function (a, b) { return a.at - b.at; });

  let minGapSeconds = Infinity;
  let minGapPair = ['', ''];

  for (let i = 1; i < events.length; i++) {
    const gap = Math.round((events[i].at - events[i - 1].at) / 1000);

    if (gap < minGapSeconds) {
      minGapSeconds = gap;
      minGapPair = [events[i - 1].label, events[i].label];
    }
  }

  return {
    count: events.length,
    minGapSeconds: isFinite(minGapSeconds) ? minGapSeconds : null,
    minGapPair: minGapPair
  };
}

// Compare CONFIG.CODE_VERSION à la dernière valeur vue par un rapport
// précédent (stockée dans les propriétés du script). Signale un changement
// de code sans bloquer quoi que ce soit — c'est une information, pas une
// alerte en soi.
function checkCodeVersion_() {
  const props = PropertiesService.getScriptProperties();
  const previous = props.getProperty('LAST_REPORTED_CODE_VERSION') || '';
  const current = CONFIG.CODE_VERSION;

  props.setProperty('LAST_REPORTED_CODE_VERSION', current);

  return {
    changed: !!previous && previous !== current,
    previous: previous || '(aucune valeur précédente)',
    current: current
  };
}

// Relit l'échantillon du dernier mail 1 sauvegardé par saveLastSentSample_,
// pour que le rapport quotidien affiche en clair ce qui part vraiment.
function lastSentSampleLines_() {
  try {
    const raw = PropertiesService.getScriptProperties().getProperty('LAST_SENT_SAMPLE');

    if (!raw) return ['- Aucun mail 1 enregistré pour le moment.'];

    const sample = JSON.parse(raw);

    return [
      '- Envoyé le : ' + sample.at,
      '- Objet : ' + sample.subject,
      '- Début du corps : ' + sample.bodyExcerpt.replace(/\n+/g, ' / ') + '…'
    ];
  } catch (error) {
    return ['- Échantillon illisible : ' + safeError_(error)];
  }
}

// ---------------------------------------------------------------
// OUTILS
// ---------------------------------------------------------------

function getContext_() {
  const sheet = SpreadsheetApp
    .openById(CONFIG.SPREADSHEET_ID)
    .getSheetByName(CONFIG.SHEET_NAME);

  if (!sheet) {
    throw new Error('Onglet Prospection introuvable.');
  }

  const lastColumn = sheet.getLastColumn();

  const headers = sheet
    .getRange(CONFIG.HEADER_ROW, 1, 1, lastColumn)
    .getDisplayValues()[0];

  const map = {};

  headers.forEach(function (header, index) {
    if (header) map[header] = index + 1;
  });

  const rowCount = Math.max(
    0,
    sheet.getLastRow() - CONFIG.FIRST_DATA_ROW + 1
  );

  const values = rowCount
    ? sheet.getRange(
        CONFIG.FIRST_DATA_ROW,
        1,
        rowCount,
        lastColumn
      ).getValues()
    : [];

  const rows = values.map(function (line) {
    const object = {};

    headers.forEach(function (header, index) {
      if (header) object[header] = line[index];
    });

    return object;
  });

  return {
    sheet: sheet,
    headers: headers,
    map: map,
    rows: rows
  };
}

function writeFields_(context, row, fields) {
  Object.keys(fields).forEach(function (header) {
    const column = context.map[header];

    if (!column) {
      throw new Error(
        'Colonne manquante : ' + header
      );
    }

    const cell = context.sheet.getRange(row, column);

    if (
      [
        'État envoi',
        'Date envoi',
        'Relance 1 envoyée',
        'Relance 2 envoyée',
        'ID conversation',
        'Erreur envoi',
        'Statut prospection'
      ].indexOf(header) !== -1
    ) {
      cell.clearDataValidations();
    }

    cell.setValue(fields[header]);

    const index = row - CONFIG.FIRST_DATA_ROW;

    if (index >= 0 && context.rows[index]) {
      context.rows[index][header] = fields[header];
    }
  });
}

function assertRequiredHeaders_() {
  const context = getContext_();

  [
    'Nom du SaaS',
    'Site',
    'Email public',
    'Message de contact',
    'Envoyer',
    'À relancer',
    'Statut prospection',
    'Canal utilisé',
    'Date du premier contact',
    'Prochaine relance',
    'Dernière réponse',
    'Résultat commercial',
    'État envoi',
    'Date envoi',
    'Relance 1 envoyée',
    'Relance 2 envoyée',
    'ID conversation',
    'Erreur envoi'
  ].forEach(function (header) {
    if (!context.map[header]) {
      throw new Error(
        'Colonne manquante : ' + header
      );
    }
  });
}

function assertSenderAlias_() {
  const self = Session.getEffectiveUser().getEmail().toLowerCase();

  // Compte principal (ex. compte Workspace dédié) : rien à vérifier.
  if (self === CONFIG.SENDER_ALIAS.toLowerCase()) return;

  const aliases = GmailApp.getAliases().map(
    function (email) {
      return email.toLowerCase();
    }
  );

  if (
    aliases.indexOf(
      CONFIG.SENDER_ALIAS.toLowerCase()
    ) === -1
  ) {
    throw new Error(
      'Ajoutez d’abord ' + CONFIG.SENDER_ALIAS +
      ' dans Gmail > Paramètres > Comptes et importation > ' +
      'Envoyer des e-mails en tant que.'
    );
  }
}

function mailOptions_() {
  return {
    from: CONFIG.SENDER_ALIAS,
    name: CONFIG.SENDER_NAME,
    replyTo: CONFIG.SENDER_ALIAS
  };
}

// Format "vrai mail" : texte simple aligné à gauche, pas de bannière
// publicitaire pleine largeur (ça fait trop newsletter/pub). La photo/bannière
// n'est plus insérée automatiquement — voir sendWithOptionalSignaturePhoto_
// si une petite photo de signature (type portrait, pas une bannière) doit
// être ajoutée un jour.
function initialMailOptions_(body) {
  const options = mailOptions_();

  options.htmlBody = asciiSafeHtml_(
    '<div style="background:#ffffff;font-family:Arial,Helvetica,sans-serif;' +
    'font-size:16px;line-height:1.5;color:#222;margin:0;">' +
    formatBodyHtml_(body) +
    '</div>'
  );

  return options;
}

// Apps Script encode mal les émojis (caractères hors du plan de base) dans les e-mails HTML :
// ils arrivent en « ������ ». On les écrit donc en références numériques (&#128231;),
// qui ne dépendent d'aucun encodage.
function asciiSafeHtml_(html) {
  let out = '';

  for (const ch of String(html)) {
    const code = ch.codePointAt(0);

    out += code > 127 ? '&#' + code + ';' : ch;
  }

  return out;
}

function escapeRegex_(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Mise en forme du corps : paragraphes aérés, gras ciblé (réglage FORMAT_BOLD),
// la question principale entièrement en gras sur son propre paragraphe, et les
// liens en simple lien bleu (jamais en bouton). Le texte brut (secours) reste
// sans mise en forme — seule la version HTML change ici.
function formatBodyHtml_(body) {
  const paragraphs = String(body)
    .replace(/\r\n/g, '\n')
    .split(/\n{2,}/)
    .map(function (block) { return block.trim(); })
    .filter(Boolean);

  const enabled = getBoolSetting_('FORMAT_ENABLED');

  const boldPhrases = enabled
    ? getSetting_('FORMAT_BOLD')
        .split('|')
        .map(function (phrase) { return phrase.trim(); })
        .filter(Boolean)
    : [];

  const emoji1 = enabled ? getSetting_('FORMAT_EMOJI_1').trim() : '';
  const emoji2 = enabled ? getSetting_('FORMAT_EMOJI_2').trim() : '';
  let emoji2Used = false;

  return paragraphs.map(function (paragraph) {
    let text = escapeHtml_(paragraph).replace(/\n/g, '<br>');

    // Toute URL en clair devient un simple lien bleu (jamais un bouton).
    text = text.replace(/https?:\/\/[^\s<]+/g, function (url) {
      const prefix = (!emoji2Used && emoji2) ? emoji2 + ' ' : '';
      emoji2Used = true;
      return prefix + '<a href="' + url + '" style="color:#1155cc;text-decoration:underline;">' + url + '</a>';
    });

    boldPhrases.forEach(function (phrase) {
      const safe = escapeHtml_(phrase);
      text = text.replace(new RegExp(escapeRegex_(safe)), function (match) {
        return '<strong>' + match + '</strong>';
      });
    });

    // La question principale (ligne qui se termine par « ? ») ressort
    // entièrement en gras, quel que soit le modèle utilisé.
    const isQuestion = /\?\s*$/.test(paragraph) && paragraph.indexOf('\n') === -1;
    const inner = isQuestion ? '<strong>' + text + '</strong>' : text;

    return '<p style="margin:0 0 20px 0;">' + inner + '</p>';
  }).join('') + buildSignatureHtml_(emoji1) + buildBannerHtml_();
}

// Signature HTML du mail 1 : nom, tagline, puis liens (site + Instagram) dans
// une barre d'accent verticale. Ajoutée après le texte (qui se termine par
// « Best, » tout seul) — le « Best, » fait partie du corps, pas de la
// signature, qui elle est toujours identique et générée ici pour rester
// cohérente sans devoir être recopiée dans chaque modèle.
function buildSignatureHtml_(emoji1) {
  const prefix = emoji1 ? emoji1 + ' ' : '';

  return '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:4px 0 0 0;">' +
    '<tr><td style="border-left:3px solid #202124;padding:2px 0 2px 14px;">' +
    '<strong style="font-size:14px;color:#202124;">Corentin Cugnet</strong><br>' +
    '<span style="font-size:13px;color:#5f6368;">' + prefix + 'French voice-over</span><br>' +
    '<span style="font-size:13px;">' +
    '<a href="https://corentinvoice.live/" style="color:#5f6368;text-decoration:underline;">corentinvoice.live</a>' +
    '&nbsp;&middot;&nbsp;' +
    '<a href="https://www.instagram.com/corentin_n1_voice_/?hl=fr" style="color:#5f6368;text-decoration:underline;">Instagram</a>' +
    '</span>' +
    '</td></tr></table>';
}

// Signature texte (relances, envoyées en texte brut sans HTML) : mêmes
// informations que buildSignatureHtml_, sans mise en forme.
function buildSignaturePlainText_() {
  return [
    'Corentin Cugnet',
    'French voice-over',
    'corentinvoice.live · instagram.com/corentin_n1_voice_'
  ].join('\n');
}

// Bannière en bas de chaque mail (réglage SIG_PHOTO) : image pleine largeur,
// pas de photo de signature ni de retour à la ligne forcé — juste un visuel
// de marque après le texte, comme une image de présentation classique.
function buildBannerHtml_() {
  const banner = getSetting_('SIG_PHOTO').trim();

  if (!banner) return '';

  return '<p style="margin:12px 0 0 0;">' +
    '<img src="' + banner + '" alt="" ' +
    'style="max-width:100%;width:480px;height:auto;display:block;border-radius:8px;">' +
    '</p>';
}

// Conserve un échantillon du dernier mail 1 réellement envoyé (objet + 400
// premiers caractères du corps), relu par le rapport quotidien. Sert
// uniquement de garde-fou de diagnostic, jamais utilisé pour l'envoi.
function saveLastSentSample_(subject, body) {
  try {
    PropertiesService.getScriptProperties().setProperty(
      'LAST_SENT_SAMPLE',
      JSON.stringify({
        at: new Date().toISOString(),
        subject: String(subject || ''),
        bodyExcerpt: String(body || '').slice(0, 400)
      })
    );
  } catch (error) {
    // Diagnostic seulement : une erreur ici ne doit jamais bloquer l'envoi.
  }
}

function escapeHtml_(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function parseDraft_(value) {
  const text = String(value || '')
    .replace(/\r\n/g, '\n')
    .trim();

  const match = text.match(
    /^Subject:\s*(.+)\n+/i
  );

  if (!match) {
    return {
      subject: '',
      body: text
    };
  }

  return {
    subject: match[1].trim(),
    body: text.slice(match[0].length).trim()
  };
}

function findSentThread_(recipient, subject) {
  const cleanSubject = String(subject)
    .replace(/["\\]/g, ' ')
    .trim();

  const threads = GmailApp.search(
    'in:sent to:' + recipient +
    ' subject:"' + cleanSubject + '"',
    0,
    5
  );

  return threads.length ? threads[0] : null;
}

function getThreadSafely_(threadId) {
  if (!threadId) return null;

  try {
    return GmailApp.getThreadById(
      String(threadId)
    );
  } catch (error) {
    return null;
  }
}

// Détecte les réponses AUTOMATIQUES de boîte mail (absence du bureau, accusé
// de réception d'un système de ticket type Zendesk/Freshdesk, etc.) pour ne
// jamais les confondre avec une vraie réponse humaine : ni pour marquer
// « Dernière réponse », ni pour déclencher l'agent IA (qui répondrait sinon
// à un robot — inutile, et risque de boucle robot-contre-robot).
function isAutoResponderMessage_(message) {
  try {
    const autoSubmitted = String(message.getHeader('Auto-Submitted') || '').toLowerCase();
    if (autoSubmitted && autoSubmitted !== 'no') return true;

    const precedence = String(message.getHeader('Precedence') || '').toLowerCase();
    if (/auto_reply|bulk/.test(precedence)) return true;

    if (message.getHeader('X-Autoreply') || message.getHeader('X-Autorespond')) {
      return true;
    }
  } catch (error) {
    // En-têtes indisponibles : on retombe sur le texte ci-dessous.
  }

  const subject = String(message.getSubject() || '').toLowerCase();
  const snippet = String(message.getPlainBody() || '').slice(0, 400).toLowerCase();
  const text = subject + ' ' + snippet;

  return /out of office|automatic reply|auto-reply|auto reply|absence du bureau|r[ée]ponse automatique|en cong[ée]|away from (the office|my desk)|currently (away|out|unavailable)|we('| )ve received your (message|request|email)|your (ticket|request) (has been|was) (created|received|opened)|thank you for (contacting|reaching out to) us|this is an automated (message|response|reply)|ticket #?\d+ (has been|was) created|we will get back to you (shortly|soon|as soon as possible)/i.test(text);
}

function hasExternalReply_(thread) {
  const own = GmailApp.getAliases()
    .concat([
      CONFIG.SENDER_ALIAS,
      Session.getEffectiveUser().getEmail()
    ])
    .map(function (email) {
      return String(email || '').toLowerCase();
    });

  return thread.getMessages().some(
    function (message) {
      const from = extractEmail_(
        message.getFrom()
      );

      return (
        from &&
        own.indexOf(from) === -1 &&
        !/mailer-daemon|postmaster/.test(from) &&
        !message.isDraft() &&
        !isAutoResponderMessage_(message)
      );
    }
  );
}

function countInitialSendsToday_(context) {
  const today = Utilities.formatDate(
    new Date(),
    CONFIG.TIME_ZONE,
    'yyyy-MM-dd'
  );

  return context.rows.filter(function (row) {
    if (!row['Date envoi']) return false;

    return Utilities.formatDate(
      new Date(row['Date envoi']),
      CONFIG.TIME_ZONE,
      'yyyy-MM-dd'
    ) === today;
  }).length;
}

function toDate_(value) {
  if (!value) return null;

  const date = value instanceof Date ? value : new Date(value);

  return isNaN(date.getTime()) ? null : date;
}

function isValidEmail_(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(
    String(value || '').trim()
  );
}

// Vérifie une adresse via l'API MyEmailVerifier juste avant le premier envoi,
// pour éviter les rebonds dus à des adresses scrapées invalides/fermées.
// Volontairement "fail-open" : si l'API est indisponible, en erreur, ou si le
// quota est dépassé, on considère l'adresse comme sûre et on envoie quand
// même (la vérification est un filet de sécurité en plus, pas un nouveau
// point de blocage pour toute la file). Seul un résultat EXPLICITE "invalide"
// bloque l'envoi.
function verifyEmailAddress_(email) {
  const apiKey = String(getSetting_('EMAIL_VERIFY_API_KEY') || '').trim();

  if (!apiKey) {
    return { checked: false, safe: true, raw: 'Clé API absente' };
  }

  try {
    const url = 'https://client.myemailverifier.com/verifyapi/verifysingle/' +
      encodeURIComponent(apiKey) + '/' + encodeURIComponent(email);

    const response = UrlFetchApp.fetch(url, {
      method: 'get',
      muteHttpExceptions: true
    });

    const code = response.getResponseCode();
    const text = response.getContentText();

    if (code < 200 || code >= 300) {
      console.log('Vérification email (' + email + ') : HTTP ' + code + ' — ' + text.slice(0, 200));
      return { checked: false, safe: true, raw: 'HTTP ' + code };
    }

    let data;

    try {
      data = JSON.parse(text);
    } catch (parseError) {
      console.log('Vérification email (' + email + ') : réponse non JSON — ' + text.slice(0, 200));
      return { checked: false, safe: true, raw: text.slice(0, 200) };
    }

    // Les noms de champs exacts de MyEmailVerifier n'ont pas pu être confirmés
    // depuis cet environnement (API non accessible pour un test direct) — on
    // couvre les variantes les plus probables (Status / status, Safe_To_Send).
    const status = String(data.Status || data.status || '').trim();
    const safeToSend = String(data.Safe_To_Send || data.safe_to_send || '').toLowerCase();

    const explicitlyInvalid = /^invalid$/i.test(status) || safeToSend === 'false';
    const explicitlySafe = safeToSend === 'true' || /^valid$/i.test(status);

    if (explicitlyInvalid) {
      return { checked: true, safe: false, raw: status || text.slice(0, 200) };
    }

    // Statut inconnu/ambigu (ex. "Unknown", "Catch-All") → on n'est pas sûr
    // que ce soit mauvais, donc on laisse passer plutôt que de bloquer un
    // prospect valide par excès de prudence.
    return { checked: true, safe: true, raw: status || (explicitlySafe ? 'valid' : text.slice(0, 200)) };
  } catch (error) {
    console.log('Vérification email (' + email + ') : erreur — ' + safeError_(error));
    return { checked: false, safe: true, raw: safeError_(error) };
  }
}

function extractEmail_(value) {
  const match = String(value || '')
    .toLowerCase()
    .match(
      /<([^>]+)>|([^\s<>]+@[^\s<>]+)/
    );

  return match
    ? String(match[1] || match[2])
        .replace(/[>,;]$/, '')
    : '';
}

function addDays_(date, days) {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}

function daysBetween_(from, to) {
  return Math.floor(
    (to.getTime() - from.getTime()) / 86400000
  );
}

function safeError_(error) {
  return String(
    error && error.message
      ? error.message
      : error
  ).slice(0, 500);
}

function getUiSafely_() {
  try {
    return SpreadsheetApp.getUi();
  } catch (error) {
    return null;
  }
}

function notify_(message) {
  console.log(message);

  const ui = getUiSafely_();

  if (ui) {
    try {
      ui.alert(message);
    } catch (error) {
      console.log(
        'Confirmation disponible dans le journal : ' +
        message
      );
    }
  }
}

// =================================================================
// MOTEUR « OPPORTUNITÉS » — SYSTÈME PARALLÈLE, INDÉPENDANT DU MOTEUR
// SAAS PRINCIPAL CI-DESSUS.
//
// Différences volontaires avec le moteur SaaS :
//  - Cible des ACHETEURS de voix (agences, créateurs, marques), pas des
//    plateformes à intégrer.
//  - Aucune découverte automatique ici : les prospects viennent du prompt
//    ChatGPT « Opportunités » et sont collés à la main dans l'onglet
//    « Prospection Opportunités ».
//  - Son propre interrupteur (AUTO_SEND_OPP), ses propres déclencheurs
//    (OPP_MACHINE_HANDLERS), ses propres modèles de message. Activer,
//    désactiver, ou traiter ce moteur n'a AUCUN effet sur le moteur SaaS,
//    et inversement — ils peuvent tourner en même temps ou séparément.
//  - Ne touche jamais à l'onglet « Prospection » ni à ses colonnes.
// =================================================================

const OPP_CONFIG = Object.freeze({
  SPREADSHEET_ID: CONFIG.SPREADSHEET_ID,
  SHEET_NAME: 'Prospection Opportunités',
  HEADER_ROW: 1,
  FIRST_DATA_ROW: 2
});

const OPP_MACHINE_HANDLERS = ['processOpportunitesMachine'];

DEFAULT_SETTINGS.push(
  ['AUTO_SEND_OPP', 'FALSE',
    'Moteur OPPORTUNITÉS (indépendant du moteur SaaS). TRUE = les lignes « À contacter » avec e-mail + observation sont mises en file et envoyées automatiquement. FALSE = validation manuelle via le menu.'],
  ['DAILY_LIMIT_OPP', '5', 'Opportunités : nombre maximum de premiers e-mails par jour.'],
  ['MAX_SENDS_PER_RUN_OPP', '5', 'Opportunités : premiers e-mails envoyés au maximum par passage horaire automatique.'],
  ['MIN_SCORE_OPP', '3', 'Opportunités : priorité minimum (1-5) pour une mise en file automatique.'],
  ['FOLLOWUP_2_ENABLED_OPP', 'FALSE', 'Opportunités : TRUE = envoie une 2e relance (J+{RELANCE_OPP_J2}).'],
  ['RELANCE_OPP_J1', '4', 'Opportunités : jours avant la relance 1.'],
  ['RELANCE_OPP_J2', '9', 'Opportunités : jours avant la relance 2 (si activée).'],
  ['SUBJECT_OPP', 'Quick question about your voiceovers',
    'Opportunités : objet du premier e-mail.'],
  ['TPL_OPP_INITIAL',
    [
      'Hi {NOM},',
      '',
      "I'm Corentin Cugnet, a French voice-over artist — my voice has already " +
      'been used across 10,000+ projects (HOLY, Hearthstone, VISION) and is ' +
      'available in 15+ languages through ElevenLabs.',
      '',
      'I noticed {OBSERVATION} — do you work with voiceovers on those ' +
      'projects? Would licensing an AI voice be useful for you?',
      '',
      'You can check it out here: {URL}',
      '',
      'Let me know what you think 🙂',
      '',
      '{OPTOUT}',
      '',
      'Best,',
      'Corentin Cugnet',
      'Corentin AI Voice',
      '{URL}'
    ].join('\n'),
    'Opportunités : premier message. Variables : {NOM} {OBSERVATION} {VOICE_ID} {URL} {OPTOUT}.'],
  ['FU1_OPP',
    [
      'Hi {NOM},',
      '',
      'Just following up — curious whether voiceovers are something you look ' +
      'for on these projects. Happy to share samples if useful: {URL}',
      '',
      'Best,',
      'Corentin Cugnet',
      'Corentin AI Voice'
    ].join('\n'),
    'Opportunités : relance 1.'],
  ['FU2_OPP',
    [
      'Hi {NOM},',
      '',
      "Last follow-up from me — if this isn't relevant right now, no worries " +
      'at all. {URL}',
      '',
      'Best,',
      'Corentin Cugnet',
      'Corentin AI Voice'
    ].join('\n'),
    'Opportunités : relance 2 (si activée).']
);

// ---------------------------------------------------------------
// LECTURE / ÉCRITURE DE L'ONGLET « PROSPECTION OPPORTUNITÉS »
// ---------------------------------------------------------------

function getContextOpp_() {
  const sheet = SpreadsheetApp
    .openById(OPP_CONFIG.SPREADSHEET_ID)
    .getSheetByName(OPP_CONFIG.SHEET_NAME);

  if (!sheet) {
    throw new Error('Onglet « Prospection Opportunités » introuvable.');
  }

  const lastColumn = sheet.getLastColumn();
  const headers = sheet
    .getRange(OPP_CONFIG.HEADER_ROW, 1, 1, lastColumn)
    .getDisplayValues()[0];

  const map = {};
  headers.forEach(function (header, index) {
    if (header) map[header] = index + 1;
  });

  const rowCount = Math.max(0, sheet.getLastRow() - OPP_CONFIG.FIRST_DATA_ROW + 1);

  const values = rowCount
    ? sheet.getRange(OPP_CONFIG.FIRST_DATA_ROW, 1, rowCount, lastColumn).getValues()
    : [];

  const rows = values.map(function (line) {
    const object = {};
    headers.forEach(function (header, index) {
      if (header) object[header] = line[index];
    });
    return object;
  });

  return { sheet: sheet, headers: headers, map: map, rows: rows };
}

function writeFieldsOpp_(context, row, fields) {
  Object.keys(fields).forEach(function (header) {
    const column = context.map[header];

    if (!column) {
      throw new Error('Colonne manquante (Opportunités) : ' + header);
    }

    const cell = context.sheet.getRange(row, column);

    if (
      [
        'État envoi', 'Date 1er contact', 'Relance 1 envoyée',
        'Relance 2 envoyée', 'ID conversation', 'Erreur envoi', 'Statut'
      ].indexOf(header) !== -1
    ) {
      cell.clearDataValidations();
    }

    cell.setValue(fields[header]);

    const index = row - OPP_CONFIG.FIRST_DATA_ROW;
    if (index >= 0 && context.rows[index]) {
      context.rows[index][header] = fields[header];
    }
  });
}

function assertRequiredHeadersOpp_() {
  const context = getContextOpp_();

  [
    'Nom', 'Famille (catégorie)', 'Site', 'Email public', 'Nom contact',
    'Observation personnalisée', 'Priorité (1-5)', 'Statut', 'Date 1er contact',
    'Réponse reçue (résumé)', 'Notes / prochaine action', 'Envoyer', 'À relancer',
    'Message de contact', 'État envoi', 'ID conversation', 'Relance 1 envoyée',
    'Relance 2 envoyée', 'Prochaine relance', 'Erreur envoi'
  ].forEach(function (header) {
    if (!context.map[header]) {
      throw new Error('Colonne manquante (Opportunités) : ' + header);
    }
  });
}

// ---------------------------------------------------------------
// MESSAGES
// ---------------------------------------------------------------

function fillTemplateOpp_(template, row) {
  const nom = String(row['Nom contact'] || row['Nom'] || 'there').trim();
  const observation = String(row['Observation personnalisée'] || '').trim();

  return String(template)
    .replace(/\{NOM\}/g, nom)
    .replace(/\{OBSERVATION\}/g, observation)
    .replace(/\{VOICE_ID\}/g, VOICE_ID)
    .replace(/\{URL\}/g, CONFIG.SAMPLES_URL)
    .replace(/\{OPTOUT\}/g, getSetting_('OPTOUT_LINE'));
}

function buildInitialDraftOpp_(row) {
  const subject = fillTemplateOpp_(getSetting_('SUBJECT_OPP'), row);
  const body = fillTemplateOpp_(getSetting_('TPL_OPP_INITIAL'), row);

  return 'Subject: ' + subject + '\n\n' + body;
}

function followUp1Opp_(row) {
  return fillTemplateOpp_(getSetting_('FU1_OPP'), row);
}

function followUp2Opp_(row) {
  return fillTemplateOpp_(getSetting_('FU2_OPP'), row);
}

// ---------------------------------------------------------------
// MENU ET ACTIVATION (indépendants du moteur SaaS)
// ---------------------------------------------------------------

function installTriggersOpp_() {
  removeMachineTriggersOpp_();

  ScriptApp.newTrigger('processOpportunitesMachine')
    .timeBased()
    .everyHours(1)
    .create();
}

function removeMachineTriggersOpp_() {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (OPP_MACHINE_HANDLERS.indexOf(trigger.getHandlerFunction()) !== -1) {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

function setupOpportunitesMachine() {
  assertSenderAlias_();
  setupSettingsSheet();
  assertRequiredHeadersOpp_();
  installTriggersOpp_();

  notify_(
    'Moteur Opportunités activé (indépendant du moteur SaaS) : traitement ' +
    'chaque heure. Envoi automatique : ' +
    (getBoolSetting_('AUTO_SEND_OPP') ? 'OUI' : 'NON — validation manuelle ' +
      'via « Mettre en file les « À contacter » (Opportunités) ».') +
    ' Limite : ' + getNumberSetting_('DAILY_LIMIT_OPP', 5) +
    ' premiers e-mails par jour.'
  );
}

function disableOpportunitesMachine() {
  removeMachineTriggersOpp_();
  notify_(
    'Moteur Opportunités désactivé. Le moteur SaaS principal n’est pas ' +
    'affecté et continue selon son propre réglage.'
  );
}

// Coche « Envoyer » sur les lignes « À contacter » avec e-mail valide,
// une observation personnalisée renseignée, et une priorité suffisante.
function queueOppValidRows() {
  const ui = getUiSafely_();

  assertRequiredHeadersOpp_();

  const context = getContextOpp_();
  const minScore = getNumberSetting_('MIN_SCORE_OPP', 3);
  const candidates = [];

  context.rows.forEach(function (row, index) {
    if (
      row['Nom'] &&
      !row['Date 1er contact'] &&
      row['Envoyer'] !== true &&
      String(row['Statut']).trim() === 'À contacter' &&
      isValidEmail_(String(row['Email public'] || '').trim()) &&
      String(row['Observation personnalisée'] || '').trim() &&
      Number(row['Priorité (1-5)'] || 0) >= minScore
    ) {
      candidates.push(index);
    }
  });

  if (!candidates.length) {
    notify_(
      'Aucune ligne « À contacter » (Opportunités) avec e-mail valide, ' +
      'observation personnalisée et priorité ≥ ' + minScore + '.'
    );
    return;
  }

  if (ui) {
    const answer = ui.alert(
      'Mettre en file (Opportunités)',
      candidates.length + ' ligne(s) seront cochées « Envoyer ». Continuer ?',
      ui.ButtonSet.YES_NO
    );

    if (answer !== ui.Button.YES) return;
  }

  candidates.forEach(function (index) {
    writeFieldsOpp_(context, OPP_CONFIG.FIRST_DATA_ROW + index, { 'Envoyer': true });
  });

  notify_(candidates.length + ' ligne(s) mises en file (Opportunités).');
}

function sendTestEmailOpp() {
  assertSenderAlias_();

  const recipient = Session.getEffectiveUser().getEmail();

  if (!isValidEmail_(recipient)) {
    throw new Error("Impossible d'identifier votre adresse Google pour le test.");
  }

  const draft = parseDraft_(
    buildInitialDraftOpp_({
      'Nom': 'Test Agence',
      'Nom contact': 'Alex',
      'Observation personnalisée': 'you produce UGC ads for several DTC brands'
    })
  );

  GmailApp.sendEmail(
    recipient,
    '[TEST OPPORTUNITÉS] ' + draft.subject,
    draft.body,
    initialMailOptions_(draft.body)
  );

  notify_('Test (Opportunités) envoyé à ' + recipient + '.');
}

// ---------------------------------------------------------------
// TRAITEMENT (ENVOI, RÉPONSES, REBONDS, RELANCES) — Opportunités
// ---------------------------------------------------------------

function processOpportunitesMachine() {
  runMachineOpp_(false);
}

function processOpportunitesMachineNow() {
  runMachineOpp_(true);
}

function runMachineOpp_(force) {
  const lock = LockService.getScriptLock();

  if (!lock.tryLock(30000)) return;

  try {
    assertSenderAlias_();
    assertRequiredHeadersOpp_();

    const context = getContextOpp_();

    detectRepliesOpp_(context);
    detectBouncesOpp_(context);

    if (getBoolSetting_('AUTO_SEND_OPP')) {
      queueEligibleRowsOpp_(context);
    }

    if (force || inSendWindow_()) {
      processFollowUpsOpp_(context);
      processInitialQueueOpp_(context, getNumberSetting_('MAX_SENDS_PER_RUN_OPP', 5));
    }
  } finally {
    lock.releaseLock();
  }
}

function queueEligibleRowsOpp_(context) {
  const minScore = getNumberSetting_('MIN_SCORE_OPP', 3);

  context.rows.forEach(function (row, index) {
    if (!row['Nom'] || row['Date 1er contact']) return;
    if (String(row['Statut']).trim() !== 'À contacter') return;
    if (!isValidEmail_(String(row['Email public'] || '').trim())) return;
    if (!String(row['Observation personnalisée'] || '').trim()) return;
    if (Number(row['Priorité (1-5)'] || 0) < minScore) return;
    if (row['Envoyer'] === true) return;

    writeFieldsOpp_(context, OPP_CONFIG.FIRST_DATA_ROW + index, { 'Envoyer': true });
  });
}

function duplicateReasonOpp_(context, index, email) {
  const row = context.rows[index];
  const address = String(email || '').trim().toLowerCase();
  const domain = emailDomain_(address);
  const isFree = FREE_MAIL_DOMAINS.indexOf(domain) !== -1;
  const siteHost = hostOf_(row['Site']);
  const name = normalizeName_(row['Nom']);

  for (let i = 0; i < context.rows.length; i++) {
    if (i === index) continue;

    const other = context.rows[i];
    if (!other['Nom'] || !other['Date 1er contact']) continue;

    const otherEmail = String(other['Email public'] || '').trim().toLowerCase();
    const label = String(other['Nom']);

    if (otherEmail && otherEmail === address) return 'même adresse que ' + label;
    if (!isFree && domain && emailDomain_(otherEmail) === domain) {
      return 'même domaine e-mail que ' + label;
    }
    if (siteHost && hostOf_(other['Site']) === siteHost) return 'même site que ' + label;
    if (name && normalizeName_(label) === name) return 'même nom que ' + label;
  }

  // Sécurité commune : ne jamais ré-envoyer à une adresse déjà contactée par
  // Gmail, même si c'est le moteur SaaS (ou un envoi manuel) qui l'a fait.
  try {
    const query = 'in:sent (to:' + address + (isFree || !domain ? '' : ' OR to:' + domain) + ')';

    if (GmailApp.search(query, 0, 1).length) {
      return 'déjà un e-mail envoyé à cette adresse ou ce domaine (Gmail)';
    }
  } catch (error) {
    console.log('Contrôle Gmail impossible (Opportunités) : ' + safeError_(error));
  }

  return '';
}

function processInitialQueueOpp_(context, cap) {
  let remaining = Math.max(
    0,
    getNumberSetting_('DAILY_LIMIT_OPP', 5) - countInitialSendsTodayOpp_(context)
  );

  if (cap !== undefined) remaining = Math.min(remaining, cap);

  if (!remaining) return;

  for (let i = 0; i < context.rows.length && remaining > 0; i++) {
    const row = context.rows[i];

    if (row['Envoyer'] !== true || row['Date 1er contact']) continue;

    const sheetRow = OPP_CONFIG.FIRST_DATA_ROW + i;
    const recipient = String(row['Email public'] || '').trim();

    let rawDraft = String(row['Message de contact'] || '').trim();

    if (!rawDraft) {
      rawDraft = buildInitialDraftOpp_(row);
      writeFieldsOpp_(context, sheetRow, { 'Message de contact': rawDraft });
    }

    const draft = parseDraft_(rawDraft);

    if (!isValidEmail_(recipient)) {
      writeFieldsOpp_(context, sheetRow, {
        'Envoyer': false,
        'État envoi': 'Adresse invalide',
        'Erreur envoi': 'Aucune adresse email exploitable'
      });
      continue;
    }

    if (!draft.subject || !draft.body) {
      writeFieldsOpp_(context, sheetRow, {
        'Envoyer': false,
        'État envoi': 'Bloqué',
        'Erreur envoi': 'Objet ou message manquant'
      });
      continue;
    }

    const duplicate = duplicateReasonOpp_(context, i, recipient);

    if (duplicate) {
      writeFieldsOpp_(context, sheetRow, {
        'Envoyer': false,
        'À relancer': false,
        'Statut': 'Doublon',
        'État envoi': 'Doublon — non envoyé',
        'Erreur envoi': 'Déjà contacté : ' + duplicate
      });
      continue;
    }

    let sent = false;

    try {
      const options = initialMailOptions_(draft.body);

      writeFieldsOpp_(context, sheetRow, { 'Envoyer': false });
      SpreadsheetApp.flush();

      GmailApp.sendEmail(recipient, draft.subject, draft.body, options);
      sent = true;

      const now = new Date();
      Utilities.sleep(getNumberSetting_('SEND_DELAY_MS', 18000));

      const thread = findSentThread_(recipient, draft.subject);

      writeFieldsOpp_(context, sheetRow, {
        'Envoyer': false,
        'À relancer': true,
        'Statut': 'Contacté',
        'Date 1er contact': now,
        'Prochaine relance': addDays_(now, getNumberSetting_('RELANCE_OPP_J1', 4)),
        'État envoi': 'Envoyé',
        'ID conversation': thread ? thread.getId() : '',
        'Erreur envoi': ''
      });

      remaining--;
    } catch (error) {
      writeFieldsOpp_(context, sheetRow, {
        'Envoyer': false,
        'À relancer': false,
        'État envoi': sent
          ? 'Envoyé — suivi à vérifier'
          : 'Erreur — vérifier Gmail avant nouvel essai',
        'Erreur envoi': safeError_(error)
      });
    }
  }
}

function countInitialSendsTodayOpp_(context) {
  const today = Utilities.formatDate(new Date(), CONFIG.TIME_ZONE, 'yyyy-MM-dd');

  return context.rows.filter(function (row) {
    const sentAt = toDate_(row['Date 1er contact']);
    return sentAt && Utilities.formatDate(sentAt, CONFIG.TIME_ZONE, 'yyyy-MM-dd') === today;
  }).length;
}

function detectRepliesOpp_(context) {
  for (let i = 0; i < context.rows.length; i++) {
    const row = context.rows[i];

    if (!row['ID conversation'] || row['Réponse reçue (résumé)']) continue;

    const thread = getThreadSafely_(row['ID conversation']);

    if (!thread || !hasExternalReply_(thread)) continue;

    writeFieldsOpp_(context, OPP_CONFIG.FIRST_DATA_ROW + i, {
      'À relancer': false,
      'Statut': 'Réponse reçue',
      'Réponse reçue (résumé)': 'Réponse détectée le ' +
        Utilities.formatDate(new Date(), CONFIG.TIME_ZONE, 'yyyy-MM-dd') +
        ' — à lire dans Gmail et classer manuellement.',
      'État envoi': 'Réponse reçue',
      'Prochaine relance': ''
    });
  }
}

function detectBouncesOpp_(context) {
  let threads = [];

  try {
    threads = GmailApp.search('from:(mailer-daemon OR postmaster) newer_than:3d', 0, 30);
  } catch (error) {
    console.log('Recherche de rebonds impossible (Opportunités) : ' + safeError_(error));
    return;
  }

  if (!threads.length) return;

  const bodies = [];

  threads.forEach(function (thread) {
    thread.getMessages().forEach(function (message) {
      bodies.push(String(message.getPlainBody() || '').toLowerCase());
    });
  });

  context.rows.forEach(function (row, index) {
    const email = String(row['Email public'] || '').trim().toLowerCase();

    if (
      !row['Date 1er contact'] ||
      !isValidEmail_(email) ||
      row['État envoi'] === 'Rebond' ||
      row['Réponse reçue (résumé)']
    ) {
      return;
    }

    const bounced = bodies.some(function (body) { return body.indexOf(email) !== -1; });
    if (!bounced) return;

    writeFieldsOpp_(context, OPP_CONFIG.FIRST_DATA_ROW + index, {
      'À relancer': false,
      'Statut': 'Refus / pas pertinent',
      'État envoi': 'Rebond',
      'Prochaine relance': '',
      'Erreur envoi': 'Rebond détecté le ' +
        Utilities.formatDate(new Date(), CONFIG.TIME_ZONE, 'yyyy-MM-dd')
    });
  });
}

function processFollowUpsOpp_(context) {
  const now = new Date();

  for (let i = 0; i < context.rows.length; i++) {
    const row = context.rows[i];

    if (
      row['À relancer'] !== true ||
      !row['Date 1er contact'] ||
      row['Réponse reçue (résumé)']
    ) {
      continue;
    }

    const sheetRow = OPP_CONFIG.FIRST_DATA_ROW + i;
    const recipient = String(row['Email public'] || '').trim();
    const sentAt = new Date(row['Date 1er contact']);
    const age = daysBetween_(sentAt, now);
    const thread = getThreadSafely_(row['ID conversation']);

    try {
      if (
        getBoolSetting_('FOLLOWUP_2_ENABLED_OPP') &&
        age >= getNumberSetting_('RELANCE_OPP_J2', 9) &&
        !row['Relance 2 envoyée']
      ) {
        sendFollowUp_(thread, recipient, followUp2Opp_(row));

        writeFieldsOpp_(context, sheetRow, {
          'À relancer': false,
          'Relance 2 envoyée': now,
          'Prochaine relance': '',
          'État envoi': 'Cycle terminé — attente de réponse',
          'Erreur envoi': ''
        });
      } else if (
        age >= getNumberSetting_('RELANCE_OPP_J1', 4) &&
        !row['Relance 1 envoyée']
      ) {
        sendFollowUp_(thread, recipient, followUp1Opp_(row));

        const followUp2On = getBoolSetting_('FOLLOWUP_2_ENABLED_OPP');

        writeFieldsOpp_(context, sheetRow, {
          'À relancer': followUp2On,
          'Relance 1 envoyée': now,
          'Prochaine relance': followUp2On
            ? addDays_(sentAt, getNumberSetting_('RELANCE_OPP_J2', 9))
            : '',
          'État envoi': followUp2On ? 'Relance 1 envoyée' : 'Cycle terminé — attente de réponse',
          'Erreur envoi': ''
        });
      }
    } catch (error) {
      writeFieldsOpp_(context, sheetRow, {
        'État envoi': 'Erreur relance',
        'Erreur envoi': safeError_(error)
      });
    }
  }
}

// =================================================================
// MOTEUR DE RÉPONSE AUTOMATIQUE (IA) — SaaS uniquement
// =================================================================
// Répond automatiquement aux prospects SaaS dont le statut est
// "Réponse reçue" (détecté par detectReplies_ ci-dessus).
//
// INDÉPENDANT DE MASTER_PAUSE : MASTER_PAUSE bloque les PREMIERS
// mails et les relances à froid (risque = contacter quelqu'un qui
// n'a rien demandé). Ici, on répond à quelqu'un qui a DÉJÀ répondu :
// risque différent, interrupteur dédié = REPLY_AGENT_ENABLED.
//
// Déroulé (déclencheur toutes les 10 min, processReplyAgentMachine) :
//  1. processReplyAgentQueue_ : pour chaque ligne "Réponse reçue" pas
//     encore vue par l'IA (colonne "Statut réponse IA" vide), lit le
//     dernier message du prospect dans le fil Gmail, appelle Claude
//     (modèle REPLY_AGENT_MODEL, ex. Haiku) avec le prompt complet
//     (réglage REPLY_AGENT_PROMPT, catégories A-J + lien WhatsApp
//     d'Etienne en catégorie G), qui renvoie classification + brouillon
//     + confiance + "révision humaine requise".
//       - Cas sûr (pas de clause sensible, confiance >= 0.75) :
//         "Statut réponse IA" = "Programmée", heure d'envoi = maintenant
//         + délai naturel aléatoire proposé par l'IA (ou réglage par défaut).
//       - Cas sensible (contrat/exclusivité/royalties précises/NDA/etc.
//         ou confiance < 0.75) : "Statut réponse IA" = "À valider
//         manuellement", brouillon écrit dans le Sheet, AUCUN envoi auto.
//  2. processScheduledReplies_ : envoie (dans le MÊME fil Gmail, comme
//     une vraie relance) les réponses "Programmée" dont l'heure est passée.

const REPLY_AGENT_HANDLERS = ['processReplyAgentMachine'];

function getReplyAgentPrompt_() {
  const prompt = getSetting_('REPLY_AGENT_PROMPT');

  if (!prompt) {
    throw new Error(
      'Réglage REPLY_AGENT_PROMPT manquant dans l’onglet Réglages.'
    );
  }

  return prompt;
}

// Dernier message du fil qui ne vient PAS de nous (donc : le prospect).
function getLastExternalReply_(thread) {
  const own = GmailApp.getAliases()
    .concat([CONFIG.SENDER_ALIAS, Session.getEffectiveUser().getEmail()])
    .map(function (email) { return String(email || '').toLowerCase(); });

  const messages = thread.getMessages();

  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    const from = extractEmail_(message.getFrom());

    if (
      from &&
      own.indexOf(from) === -1 &&
      !/mailer-daemon|postmaster/.test(from) &&
      !message.isDraft() &&
      !isAutoResponderMessage_(message)
    ) {
      return {
        id: message.getId(),
        name: String(message.getFrom() || '').replace(/<.*>/, '').trim() || from,
        text: String(message.getPlainBody() || '').trim().slice(0, 6000)
      };
    }
  }

  return null;
}

// Appelle Claude (Haiku par défaut) avec le prompt système complet du
// réglage REPLY_AGENT_PROMPT (catégories A-J, lien WhatsApp d'Etienne
// en catégorie G) + le dernier message du prospect. Renvoie l'objet
// JSON décrit dans "OUTPUT FORMAT FOR AUTOMATION" de ce prompt.
function askReplyAgent_(apiKey, payload) {
  const system = getReplyAgentPrompt_() +
    '\n\n==================================================\n' +
    'MODE AUTOMATISATION\n' +
    '==================================================\n' +
    'Réponds UNIQUEMENT avec l’objet JSON décrit dans OUTPUT FORMAT FOR ' +
    'AUTOMATION ci-dessus, sans texte autour, sans balises markdown. ' +
    '"reply_body" doit être le corps complet du mail (sans ligne ' +
    '"Subject:"), prêt à être envoyé tel quel, en texte brut (pas de HTML). ' +
    'Ajoute aussi un champ booléen "integration_confirmed" : true UNIQUEMENT ' +
    'si ce message précis confirme que la voix a été ajoutée/intégrée/mise ' +
    'en ligne chez eux (ex: "it\'s live", "we added it", "done, it\'s up", ' +
    '"c\'est intégré/ajouté"), false dans tous les autres cas (question, ' +
    'demande d\'info, discussion en cours, etc.).';

  const user =
    'SaaS : ' + payload.saas + '\n' +
    'Interlocuteur : ' + (payload.contact || 'inconnu') + '\n\n' +
    'Dernier message reçu du prospect :\n' + payload.replyText;

  const response = UrlFetchApp.fetch(CONFIG.API_URL, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': CONFIG.API_VERSION
    },
    payload: JSON.stringify({
      model: getSetting_('REPLY_AGENT_MODEL') || 'claude-haiku-4-5-20251001',
      max_tokens: 1500,
      system: system,
      messages: [{ role: 'user', content: user }]
    }),
    muteHttpExceptions: true
  });

  const code = response.getResponseCode();
  const data = JSON.parse(response.getContentText());

  if (code !== 200) {
    throw new Error(
      'API Claude ' + code + ' : ' +
      String(data && data.error && data.error.message || 'erreur')
    );
  }

  const text = (data.content || [])
    .filter(function (block) { return block.type === 'text'; })
    .map(function (block) { return block.text; })
    .join('\n');

  const match = text.match(/\{[\s\S]*\}/);

  if (!match) {
    throw new Error(
      'Réponse IA non exploitable (pas de JSON) : ' + text.slice(0, 200)
    );
  }

  return JSON.parse(match[0]);
}

// Classe + rédige une réponse pour chaque NOUVEAU message du prospect pas
// encore traité par l'IA (pas seulement le tout premier — une réponse qui
// confirme ensuite "la voix est en ligne" est aussi traitée), et programme
// son envoi (ou la met "à valider"). Suit l'ID du dernier message vu par
// fil (colonne "Dernier message IA (ID)") pour ne jamais retraiter deux
// fois le même message, même après plusieurs échanges dans le même fil.
function processReplyAgentQueue_(context) {
  if (!getBoolSetting_('REPLY_AGENT_ENABLED')) return;

  const apiKey = PropertiesService.getScriptProperties().getProperty('ANTHROPIC_API_KEY');
  if (!apiKey) return;

  for (let i = 0; i < context.rows.length; i++) {
    const row = context.rows[i];

    if (!row['ID conversation']) continue;

    const sheetRow = CONFIG.FIRST_DATA_ROW + i;
    const thread = getThreadSafely_(row['ID conversation']);

    if (!thread) continue;

    const reply = getLastExternalReply_(thread);
    if (!reply || !reply.text) continue;

    // Déjà traité : le dernier message externe du fil est celui qu'on a
    // déjà classé lors d'un passage précédent.
    if (String(row['Dernier message IA (ID)'] || '') === String(reply.id || '')) {
      continue;
    }

    let result;

    try {
      result = askReplyAgent_(apiKey, {
        saas: String(row['Nom du SaaS'] || ''),
        contact: reply.name,
        replyText: reply.text
      });
    } catch (error) {
      writeFields_(context, sheetRow, {
        'Statut réponse IA': 'Erreur IA : ' + safeError_(error)
      });
      continue;
    }

    const body = String(result.reply_body || '').trim();
    const integrationConfirmed = !!result.integration_confirmed;

    const confirmationFields = integrationConfirmed
      ? {
          'Voix ajoutée (confirmée)': true,
          'Statut prospection': 'Voix intégrée ✅'
        }
      : {};

    if (!body) {
      writeFields_(context, sheetRow, Object.assign({
        'Classification réponse IA': String(result.classification || ''),
        'Statut réponse IA': 'Erreur IA : réponse vide',
        'Dernier message IA (ID)': String(reply.id || '')
      }, confirmationFields));
      continue;
    }

    // Par défaut (REPLY_AGENT_AUTO_SEND = FALSE), AUCUNE réponse n'est
    // envoyée toute seule : tout passe en brouillon à valider manuellement,
    // quelle que soit la confiance de l'IA. Seul un passage explicite de
    // REPLY_AGENT_AUTO_SEND à TRUE dans Réglages réactive l'envoi auto pour
    // les réponses à confiance élevée.
    const needsHuman = !getBoolSetting_('REPLY_AGENT_AUTO_SEND') ||
      !!result.human_review_required ||
      !isFinite(Number(result.confidence)) ||
      Number(result.confidence) < 0.75;

    if (needsHuman) {
      writeFields_(context, sheetRow, Object.assign({
        'Classification réponse IA': String(result.classification || ''),
        'Brouillon réponse IA': body,
        'Statut réponse IA': 'À valider manuellement',
        'Envoi réponse prévu': '',
        'Dernier message IA (ID)': String(reply.id || '')
      }, confirmationFields));
      continue;
    }

    const minDelay = getNumberSetting_('REPLY_AGENT_MIN_DELAY', 3);
    const maxDelay = getNumberSetting_('REPLY_AGENT_MAX_DELAY', 18);
    let delay = Number(result.recommended_delay_minutes);

    if (!isFinite(delay) || delay <= 0) {
      delay = minDelay + Math.random() * Math.max(1, maxDelay - minDelay);
    }

    delay = Math.min(45, Math.max(2, delay));

    writeFields_(context, sheetRow, Object.assign({
      'Classification réponse IA': String(result.classification || ''),
      'Brouillon réponse IA': body,
      'Statut réponse IA': 'Programmée',
      'Envoi réponse prévu': new Date(Date.now() + delay * 60000),
      'Dernier message IA (ID)': String(reply.id || '')
    }, confirmationFields));
  }
}

// Envoie, dans le même fil Gmail, les réponses "Programmée" dont
// l'heure prévue est passée.
function processScheduledReplies_(context) {
  const now = Date.now();

  for (let i = 0; i < context.rows.length; i++) {
    const row = context.rows[i];

    if (String(row['Statut réponse IA'] || '').trim() !== 'Programmée') continue;

    const due = toDate_(row['Envoi réponse prévu']);
    if (!due || due.getTime() > now) continue;

    const sheetRow = CONFIG.FIRST_DATA_ROW + i;
    const thread = getThreadSafely_(row['ID conversation']);
    const recipient = String(row['Email public'] || '').trim();
    const body = String(row['Brouillon réponse IA'] || '').trim();

    if (!thread || !isValidEmail_(recipient) || !body) {
      writeFields_(context, sheetRow, {
        'Statut réponse IA': 'Erreur envoi : fil, adresse ou brouillon manquant'
      });
      continue;
    }

    try {
      const messages = thread.getMessages();
      messages[messages.length - 1].replyAll(body, mailOptions_());

      writeFields_(context, sheetRow, {
        'Statut réponse IA': 'Envoyée',
        'Envoi réponse prévu': ''
      });
    } catch (error) {
      writeFields_(context, sheetRow, {
        'Statut réponse IA': 'Erreur envoi : ' + safeError_(error)
      });
    }
  }
}

function assertReplyAgentHeaders_() {
  const context = getContext_();

  [
    'Classification réponse IA',
    'Brouillon réponse IA',
    'Statut réponse IA',
    'Envoi réponse prévu',
    'Voix ajoutée (confirmée)',
    'Dernier message IA (ID)'
  ].forEach(function (header) {
    if (!context.map[header]) {
      throw new Error(
        'Colonne manquante dans Prospection : ' + header
      );
    }
  });
}

function processReplyAgentMachine() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) return;

  try {
    assertSenderAlias_();
    assertRequiredHeaders_();
    assertReplyAgentHeaders_();

    const context = getContext_();

    processReplyAgentQueue_(context);
    processScheduledReplies_(context);
    // Dès que l'IA confirme l'intégration ("integration_confirmed"), le
    // prospect est déplacé immédiatement — pas besoin d'attendre le
    // prochain passage horaire du moteur principal.
    migrateConfirmedPartners_(context);
  } finally {
    lock.releaseLock();
  }
}

function processReplyAgentMachineNow() {
  processReplyAgentMachine();

  notify_(
    'Réponses automatiques traitées. Voir les colonnes "Classification ' +
    'réponse IA" / "Statut réponse IA" dans l’onglet Prospection ' +
    '(Programmée = partira au prochain passage, À valider manuellement ' +
    '= brouillon prêt mais non envoyé, Envoyée = déjà parti).'
  );
}

// Marque TOUTES les conversations ayant déjà une réponse externe comme
// « déjà vues » par l'agent, SANS générer ni envoyer aucune réponse. À
// exécuter UNE SEULE FOIS avant la toute première activation de l'agent,
// pour ne jamais répondre d'un coup à des dizaines de réponses reçues il y a
// des jours ou des semaines (ce qui paraîtrait à la fois étrange pour le
// destinataire et risquerait un envoi en rafale). Après ce passage, l'agent
// ne réagira qu'aux réponses reçues à partir de maintenant.
function skipExistingRepliesNow_() {
  assertRequiredHeaders_();
  assertReplyAgentHeaders_();

  const context = getContext_();
  let marked = 0;

  for (let i = 0; i < context.rows.length; i++) {
    const row = context.rows[i];

    if (!row['ID conversation']) continue;
    if (String(row['Classification réponse IA'] || '')) continue; // déjà traité

    const thread = getThreadSafely_(row['ID conversation']);
    if (!thread) continue;

    const reply = getLastExternalReply_(thread);
    if (!reply || !reply.id) continue;

    if (String(row['Dernier message IA (ID)'] || '') === String(reply.id)) continue;

    writeFields_(context, CONFIG.FIRST_DATA_ROW + i, {
      'Dernier message IA (ID)': String(reply.id),
      'Statut réponse IA': 'Ignorée (antérieure à l’activation de l’agent)'
    });

    marked++;
  }

  notify_(
    marked + ' conversation(s) marquée(s) comme déjà vues, sans réponse générée. ' +
    'L’agent ne réagira désormais qu’aux réponses reçues à partir de maintenant.'
  );
}

function installReplyAgentTriggers_() {
  removeReplyAgentTriggers_();

  ScriptApp.newTrigger('processReplyAgentMachine')
    .timeBased()
    .everyMinutes(10)
    .create();
}

function removeReplyAgentTriggers_() {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (REPLY_AGENT_HANDLERS.indexOf(trigger.getHandlerFunction()) !== -1) {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

function setupReplyAgentMachine() {
  assertSenderAlias_();
  assertRequiredHeaders_();
  assertReplyAgentHeaders_();
  installReplyAgentTriggers_();

  const hasKey = !!PropertiesService
    .getScriptProperties()
    .getProperty('ANTHROPIC_API_KEY');

  notify_(
    '🤖 Réponse automatique IA activée : vérification toutes les 10 min. ' +
    'Modèle : ' + (getSetting_('REPLY_AGENT_MODEL') || 'claude-haiku-4-5-20251001') +
    '. Indépendant de MASTER_PAUSE (ne touche que les prospects qui ont déjà répondu). ' +
    (hasKey
      ? ''
      : 'ATTENTION : clé API Claude absente (menu Prospection > Enregistrer la clé API Claude).')
  );
}

function disableReplyAgentMachine() {
  removeReplyAgentTriggers_();

  notify_(
    'Réponse automatique IA désactivée. Les brouillons déjà en attente ' +
    'restent visibles dans le Sheet (rien n’est envoyé).'
  );
}

// Test sans risque : simule un message reçu, appelle l'IA, affiche le
// résultat dans une popup. N'écrit RIEN dans le Sheet, n'envoie AUCUN mail.
function testReplyAgent() {
  const ui = getUiSafely_();

  if (!ui) {
    throw new Error('Utilisez le menu Prospection du Google Sheets pour ce test.');
  }

  const nameAnswer = ui.prompt(
    'Test réponse IA (1/2)',
    'Nom du SaaS (fictif, juste pour le contexte) :',
    ui.ButtonSet.OK_CANCEL
  );

  if (nameAnswer.getSelectedButton() !== ui.Button.OK) return;

  const saas = String(nameAnswer.getResponseText() || '').trim() || 'Test SaaS';

  const replyAnswer = ui.prompt(
    'Test réponse IA (2/2)',
    'Colle ici le message que le prospect aurait envoyé (une ligne) :',
    ui.ButtonSet.OK_CANCEL
  );

  if (replyAnswer.getSelectedButton() !== ui.Button.OK) return;

  const replyText = String(replyAnswer.getResponseText() || '').trim();

  if (!replyText) {
    ui.alert('Aucun message saisi, test annulé.');
    return;
  }

  const apiKey = PropertiesService.getScriptProperties().getProperty('ANTHROPIC_API_KEY');

  if (!apiKey) {
    ui.alert(
      'Clé API Claude absente (menu Prospection > Enregistrer la clé API Claude).'
    );
    return;
  }

  let result;

  try {
    result = askReplyAgent_(apiKey, {
      saas: saas,
      contact: 'Test',
      replyText: replyText
    });
  } catch (error) {
    ui.alert('Erreur IA : ' + safeError_(error));
    return;
  }

  const confidence = Number(result.confidence);
  const needsHuman = !!result.human_review_required ||
    !isFinite(confidence) || confidence < 0.75;

  ui.alert(
    'Résultat du test — RIEN n’est envoyé, RIEN n’est écrit dans le Sheet',
    'Catégorie : ' + String(result.classification || '?') + '\n' +
    'Confiance : ' + (isFinite(confidence) ? confidence : '?') + '\n' +
    'Validation humaine requise : ' + (needsHuman ? 'OUI — resterait en brouillon' : 'non — partirait automatiquement') + '\n' +
    'Délai recommandé avant envoi : ' + String(result.recommended_delay_minutes || '?') + ' min\n\n' +
    '--- Brouillon de réponse généré ---\n\n' +
    String(result.reply_body || '(vide)'),
    ui.ButtonSet.OK
  );
}

// FIN DU SCRIPT COMPLET

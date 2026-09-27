<?php
/**
 * MarketForge Engine — creation automatique d'une fiche podcast Listenly (table _c_p_shows),
 * sans passer par /admin/podcast_show/__new. Remplace l'etape manuelle "creer le lien Listenly".
 *
 * POST /api/podcast-show-import.php   (header X-Import-Secret = KNOWLEDGE_IMPORT_SECRET du .env)
 * Body JSON :
 *   {"mode": "describe"}                          -> structure de _c_p_shows + mapping detecte + 1 ligne exemple
 *   {"mode": "dry_run", "podcast": {...}}         -> montre la ligne qui SERAIT inseree, n'ecrit rien
 *   {"mode": "insert",  "podcast": {...}}         -> insere (ou renvoie l'existant si deja present)
 * podcast = {title, rss_url, description, cover_image, language, author, email, website}
 * Reponse : {"ok": true, "created": bool, "id": 123, "seo_url": "...", "listenly_url": "https://listenly.fr/podcast/show/..."}
 *
 * Meme pattern que knowledge-moments-import.php / get-episode-url.php (.env, PDO).
 * Securite : le mode insert refuse de tourner tant que les colonnes obligatoires (title,
 * seo_url, rss) ne sont pas identifiees -- verifier d'abord avec mode=describe.
 */

header('Content-Type: application/json; charset=utf-8');

function out($code, $data) {
    http_response_code($code);
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
    exit;
}

function load_env($path) {
    $env = [];
    if (!file_exists($path)) return $env;
    foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        $line = trim($line);
        if ($line === '' || $line[0] === '#' || strpos($line, '=') === false) continue;
        list($key, $value) = explode('=', $line, 2);
        $value = trim($value);
        if (strlen($value) >= 2) {
            $f = $value[0]; $l = $value[strlen($value) - 1];
            if (($f === '"' && $l === '"') || ($f === "'" && $l === "'")) $value = substr($value, 1, -1);
        }
        $env[trim($key)] = $value;
    }
    return $env;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') out(405, ['ok' => false, 'error' => 'POST uniquement']);

$env = load_env('/home/cuet0006/.env');
$secret = $env['KNOWLEDGE_IMPORT_SECRET'] ?? '';
if ($secret === '' || !hash_equals($secret, $_SERVER['HTTP_X_IMPORT_SECRET'] ?? '')) {
    out(403, ['ok' => false, 'error' => 'Acces refuse']);
}

try {
    $pdo = new PDO(
        'mysql:host=' . ($env['DB_HOST'] ?? 'localhost') . ';dbname=' . ($env['DB_NAME'] ?? 'cuet0006_listenly') . ';charset=utf8mb4',
        $env['DB_USER'] ?? '', $env['DB_PASS'] ?? ($env['DB_PASSWORD'] ?? ''),
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
    );
} catch (PDOException $e) {
    out(500, ['ok' => false, 'error' => 'Connexion base impossible']);
}

const TABLE = '_c_p_shows';

// --- Structure reelle de la table ---
$cols = [];
foreach ($pdo->query('SHOW COLUMNS FROM `' . TABLE . '`')->fetchAll(PDO::FETCH_ASSOC) as $c) {
    $cols[$c['Field']] = $c;
}

// --- Mapping champ logique -> colonne (premiere colonne existante de la liste) ---
// Ajuster ici si describe montre un nom different.
$CANDIDATES = [
    'title'       => ['title', 'name'],
    'seo_url'     => ['seo_url', 'slug'],
    'rss_url'     => ['rss', 'rss_url', 'feed', 'feed_url', 'url_rss'],
    'description' => ['description', 'desc', 'summary', 'content'],
    'cover_image' => ['image', 'cover_image', 'picture', 'thumbnail', 'artwork'],  // cover_id = id media BOF, pas une URL : non rempli
    'language'    => ['lang', 'language', 'lang_id'],
    'author'      => ['author', 'artist', 'owner_name'],
    'email'       => ['email', 'owner_email'],
    'website'     => ['website', 'site', 'link', 'url'],
];
$map = [];
foreach ($CANDIDATES as $logical => $names) {
    foreach ($names as $n) {
        if (isset($cols[$n])) { $map[$logical] = $n; break; }
    }
}

$input = json_decode(file_get_contents('php://input'), true) ?: [];
$mode = $input['mode'] ?? 'describe';

if ($mode === 'describe') {
    $sample = $pdo->query('SELECT * FROM `' . TABLE . '` ORDER BY 1 DESC LIMIT 1')->fetch(PDO::FETCH_ASSOC) ?: [];
    foreach ($sample as $k => $v) {
        if (is_string($v) && mb_strlen($v) > 160) $sample[$k] = mb_substr($v, 0, 160) . '…';
    }
    $related = [];
    foreach ($pdo->query("SHOW TABLES LIKE '\\_c\\_p\\_%'")->fetchAll(PDO::FETCH_COLUMN) as $t) $related[] = $t;
    out(200, ['ok' => true, 'columns' => array_values($cols), 'mapping_detecte' => $map, 'exemple_derniere_ligne' => $sample, 'tables_c_p' => $related]);
}

// --- Donnees du podcast ---
$p = $input['podcast'] ?? [];
$title = trim($p['title'] ?? '');
$rss = trim($p['rss_url'] ?? '');
if ($title === '' || $rss === '') out(400, ['ok' => false, 'error' => 'podcast.title et podcast.rss_url requis']);
foreach (['title', 'seo_url', 'rss_url'] as $req) {
    if (!isset($map[$req])) out(409, ['ok' => false, 'error' => "Colonne '$req' non identifiee dans " . TABLE . ' — lancer mode=describe et ajuster $CANDIDATES', 'mapping_detecte' => $map]);
}

function slugify($s) {
    $s = iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $s);
    $s = strtolower(preg_replace('/[^a-zA-Z0-9]+/', '-', $s));
    return trim(substr(trim($s, '-'), 0, 120), '-') ?: 'podcast';
}
function show_url($seo) { return 'https://listenly.fr/podcast/show/' . $seo; }

// --- Deja present ? (meme flux RSS ou meme titre) -> on renvoie l'existant, jamais de doublon ---
$pk = null;
foreach ($cols as $name => $c) { if ($c['Key'] === 'PRI') { $pk = $name; break; } }
// Anti-doublon elargi (27/09/2026, apres le doublon "rock-your-money-rock-your-life-2") : meme RSS,
// meme titre, meme seo_url de base, ou meme code (titre sans ponctuation), comme l'admin les ecrit.
$dedupBase = slugify($title);
$dedupCode = str_replace('-', '', $dedupBase);
$where = ["`{$map['rss_url']}` = :rss", "`{$map['title']}` = :title", "`{$map['seo_url']}` = :base", "LOWER(`{$map['title']}`) = :tslug"];
$args = [':rss' => $rss, ':title' => $title, ':base' => $dedupBase, ':tslug' => $dedupBase];
if (isset($cols['code'])) { $where[] = '`code` = :code'; $args[':code'] = $dedupCode; }
$sel = 'SELECT ' . ($pk ? "`$pk` AS id, " : '') . "`{$map['seo_url']}` AS seo_url FROM `" . TABLE . "` WHERE " . implode(' OR ', $where) . ' LIMIT 1';
$st = $pdo->prepare($sel);
$st->execute($args);
if ($row = $st->fetch(PDO::FETCH_ASSOC)) {
    out(200, ['ok' => true, 'created' => false, 'id' => $row['id'] ?? null, 'seo_url' => $row['seo_url'], 'listenly_url' => show_url($row['seo_url'])]);
}

// --- seo_url unique ---
$base = slugify($title); $seo = $base; $i = 2;
$chk = $pdo->prepare("SELECT COUNT(*) FROM `" . TABLE . "` WHERE `{$map['seo_url']}` = :s");
while (true) { $chk->execute([':s' => $seo]); if (!$chk->fetchColumn()) break; $seo = $base . '-' . $i++; }

// hash (md5 32 hex) et code (slug sans tirets) : UNIQUE NOT NULL, meme format que l'admin
// (ex. hash 103b00e9..., code thegoaldiggerpodcast pour seo_url the-goal-digger-podcast).
$extra = [];
if (isset($cols['hash'])) {
    $h = $pdo->prepare("SELECT COUNT(*) FROM `" . TABLE . "` WHERE `hash` = :h");
    do { $hash = md5(random_bytes(16)); $h->execute([':h' => $hash]); } while ($h->fetchColumn());
    $extra['hash'] = $hash;
}
if (isset($cols['code'])) {
    $cbase = substr(str_replace('-', '', $base), 0, 140) ?: 'podcast';
    $code = $cbase; $j = 2;
    $cc = $pdo->prepare("SELECT COUNT(*) FROM `" . TABLE . "` WHERE `code` = :c");
    while (true) { $cc->execute([':c' => $code]); if (!$cc->fetchColumn()) break; $code = $cbase . $j++; }
    $extra['code'] = $code;
}

$values = $extra + [
    $map['title'] => $title,
    $map['seo_url'] => $seo,
    $map['rss_url'] => $rss,
];
foreach (['description', 'cover_image', 'author', 'email', 'website', 'language'] as $f) {
    if (isset($map[$f]) && isset($p[$f]) && $p[$f] !== '') {
        $isNum = preg_match('/int|decimal|float|double/i', $cols[$map[$f]]['Type']);
        if (!$isNum) $values[$map[$f]] = mb_substr((string)$p[$f], 0, 60000);
    }
}
// La description BOF est au format Editor.js ({"time":..,"blocks":[...]}), pas du texte brut.
if (isset($map['description'], $values[$map['description']])) {
    $values[$map['description']] = json_encode([
        'time' => (int) round(microtime(true) * 1000),
        'blocks' => [['type' => 'paragraph', 'data' => ['text' => htmlspecialchars($values[$map['description']], ENT_QUOTES)]]],
        'version' => '2.28.2',
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
}
// Valeurs BOF connues (vues sur une fiche creee par l'admin) : rss_generate=1 -> le lecteur RSS du
// CMS importe les episodes ; creator_id=1 comme l'admin ; dates d'ajout/sortie.
$BOF_DEFAULTS = ['rss_generate' => 1, 'creator_id' => 1, 'time_add' => date('Y-m-d H:i:s'), 'time_release' => date('Y-m-d H:i:s'),
                 'external_addresses' => '[]', 'translations' => '[]', 'seo_data' => '[]', 'price_setting' => '{"disable_subs":false}'];
foreach ($BOF_DEFAULTS as $k => $v) { if (isset($cols[$k]) && !isset($values[$k])) $values[$k] = $v; }
// Colonnes NOT NULL sans valeur par defaut : valeur neutre selon le type
$filled = [];
foreach ($cols as $name => $c) {
    if (isset($values[$name]) || $c['Null'] === 'YES' || $c['Default'] !== null || stripos($c['Extra'], 'auto_increment') !== false) continue;
    $t = strtolower($c['Type']);
    if (preg_match('/datetime|timestamp/', $t)) $values[$name] = date('Y-m-d H:i:s');
    elseif (preg_match('/^date/', $t)) $values[$name] = date('Y-m-d');
    elseif (preg_match('/int|decimal|float|double/', $t)) $values[$name] = 0;
    else $values[$name] = '';
    $filled[] = $name;
}
// Dates de creation/maj si elles existent et sont nullables
foreach (['created_at', 'date_add', 'created', 'date_created', 'updated_at', 'date_upd'] as $d) {
    if (isset($cols[$d]) && !isset($values[$d])) $values[$d] = date('Y-m-d H:i:s');
}

if ($mode === 'dry_run') {
    out(200, ['ok' => true, 'dry_run' => true, 'ligne' => $values, 'colonnes_remplies_par_defaut' => $filled, 'listenly_url' => show_url($seo)]);
}
if ($mode !== 'insert') out(400, ['ok' => false, 'error' => 'mode inconnu']);

$names = array_keys($values);
$sql = 'INSERT INTO `' . TABLE . '` (`' . implode('`,`', $names) . '`) VALUES (:' . implode(', :', array_map(fn($n) => 'v' . md5($n), $names)) . ')';
$params = [];
foreach ($values as $n => $v) $params[':v' . md5($n)] = $v;
try {
    $pdo->prepare($sql)->execute($params);
} catch (PDOException $e) {
    out(500, ['ok' => false, 'error' => 'Insertion refusee : ' . $e->getMessage()]);
}
out(200, ['ok' => true, 'created' => true, 'id' => $pdo->lastInsertId(), 'seo_url' => $seo, 'listenly_url' => show_url($seo)]);

<?php
/**
 * MarketForge Engine — enregistrement automatique d'un flux RSS dans le lecteur RSS de Listenly
 * (table _c_p_rss_readers, celle que l'admin /admin/podcast_rss_readers alimente normalement a la main).
 * Sans cette ligne, la fiche podcast existe (_c_p_shows) mais ses episodes ne sont jamais scrapes.
 *
 * Meme pattern que podcast-show-import.php (.env, PDO, header X-Import-Secret).
 *
 * POST /api/rss-reader-register.php
 * Body JSON :
 *   {"mode": "dry_run", "link": "https://..."}  -> montre la ligne qui SERAIT inseree, n'ecrit rien
 *   {"mode": "insert",  "link": "https://..."}  -> insere (ou renvoie l'existant si deja present, jamais de doublon)
 * Reponse : {"ok": true, "created": bool, "id": 123}
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

const TABLE = '_c_p_rss_readers';

$input = json_decode(file_get_contents('php://input'), true) ?: [];
$mode = $input['mode'] ?? 'dry_run';
$link = trim($input['link'] ?? '');
if ($link === '') out(400, ['ok' => false, 'error' => 'link requis']);
if (!preg_match('#^https?://#i', $link)) out(400, ['ok' => false, 'error' => 'link doit etre une URL http(s)']);

$hash = md5($link);

// Deja present (par hash, comme le fait l'admin) -> jamais de doublon
$st = $pdo->prepare('SELECT `ID` FROM `' . TABLE . '` WHERE `link_hash` = :h LIMIT 1');
$st->execute([':h' => $hash]);
if ($row = $st->fetch(PDO::FETCH_ASSOC)) {
    out(200, ['ok' => true, 'created' => false, 'id' => (int) $row['ID']]);
}

// Valeurs par defaut observees sur les lignes ajoutees par l'admin (priority=1, time_interval=72h)
$values = ['link' => $link, 'link_hash' => $hash, 'priority' => 1, 'time_interval' => 72, 'active' => 1];

if ($mode === 'dry_run') out(200, ['ok' => true, 'dry_run' => true, 'ligne' => $values]);
if ($mode !== 'insert') out(400, ['ok' => false, 'error' => 'mode inconnu (dry_run|insert)']);

try {
    $ins = $pdo->prepare(
        'INSERT INTO `' . TABLE . '` (`link`, `link_hash`, `priority`, `time_interval`, `active`) ' .
        'VALUES (:link, :link_hash, :priority, :time_interval, :active)'
    );
    $ins->execute($values);
} catch (PDOException $e) {
    out(500, ['ok' => false, 'error' => 'Insertion refusee : ' . $e->getMessage()]);
}
out(200, ['ok' => true, 'created' => true, 'id' => (int) $pdo->lastInsertId()]);

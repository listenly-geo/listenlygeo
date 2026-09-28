<?php
/**
 * Outil de diagnostic (temporaire) — decrit n'importe quelle table _c_p_% de la base Listenly :
 * colonnes + derniere ligne (valeurs longues tronquees). Meme pattern d'auth que podcast-show-import.php.
 * Sert a retrouver la structure de la table utilisee par /admin/podcast_rss_readers (nom exact inconnu
 * cote code), avant d'ecrire l'insertion automatique dans le pipeline d'onboarding.
 *
 * POST /api/admin-table-describe.php   (header X-Import-Secret = KNOWLEDGE_IMPORT_SECRET du .env)
 * Body JSON :
 *   {"mode": "list"}                     -> toutes les tables _c_p_%
 *   {"mode": "describe", "table": "..."}  -> colonnes + derniere ligne de cette table (doit commencer par _c_p_)
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

$allTables = $pdo->query("SHOW TABLES LIKE '\\_c\\_p\\_%'")->fetchAll(PDO::FETCH_COLUMN);

$input = json_decode(file_get_contents('php://input'), true) ?: [];
$mode = $input['mode'] ?? 'list';

if ($mode === 'list') {
    out(200, ['ok' => true, 'tables' => $allTables]);
}

if ($mode !== 'describe') out(400, ['ok' => false, 'error' => 'mode inconnu (list|describe)']);

$table = $input['table'] ?? '';
if (!in_array($table, $allTables, true)) {
    out(400, ['ok' => false, 'error' => 'table inconnue ou non autorisee', 'tables' => $allTables]);
}

$cols = $pdo->query('SHOW COLUMNS FROM `' . $table . '`')->fetchAll(PDO::FETCH_ASSOC);
$count = (int) $pdo->query('SELECT COUNT(*) FROM `' . $table . '`')->fetchColumn();
$sample = $pdo->query('SELECT * FROM `' . $table . '` ORDER BY 1 DESC LIMIT 2')->fetchAll(PDO::FETCH_ASSOC);
foreach ($sample as &$row) {
    foreach ($row as $k => $v) {
        if (is_string($v) && mb_strlen($v) > 200) $row[$k] = mb_substr($v, 0, 200) . '…';
    }
}
out(200, ['ok' => true, 'table' => $table, 'row_count' => $count, 'columns' => $cols, 'derniers_exemples' => $sample]);

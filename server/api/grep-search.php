<?php
/**
 * Outil de diagnostic (temporaire) — equivalent HTTP de `grep -R --include="*.php" -n "..." .`
 * sur la racine du site (pas d'acces SSH disponible, ce script tourne sur le serveur via HTTP).
 * Meme pattern d'auth que les autres outils server/api/*.php.
 *
 * POST /api/grep-search.php   (header X-Import-Secret = KNOWLEDGE_IMPORT_SECRET)
 * Body JSON :
 *   {"pattern": "time_scrap", "subdirs": ["api","app"], "max_results": 60}
 *   subdirs vide/absent = toute la racine du site. Recherche insensible a la casse, texte simple
 *   (pas de regex), fichiers *.php uniquement. Racine fixee en dur (pas de path traversal possible).
 *   {"mode": "read", "file": "debug/rss_cron_only.php"}  -> contenu complet d'UN fichier PHP (lecture
 *   seule, chemin resolu et verifie a l'interieur de la racine, .. interdit).
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

const ROOT = '/home/cuet0006/listenly.fr';   // racine fixe : jamais fournie par l'appelant

$input = json_decode(file_get_contents('php://input'), true) ?: [];

if (($input['mode'] ?? '') === 'read') {
    $rel = ltrim((string) ($input['file'] ?? ''), '/');
    if ($rel === '' || strpos($rel, '..') !== false) out(400, ['ok' => false, 'error' => 'file invalide']);
    $full = ROOT . '/' . $rel;
    $real = realpath($full);
    if (!$real || strpos($real, realpath(ROOT) . DIRECTORY_SEPARATOR) !== 0) out(404, ['ok' => false, 'error' => 'fichier introuvable']);
    if (strtolower(pathinfo($real, PATHINFO_EXTENSION)) !== 'php') out(400, ['ok' => false, 'error' => 'seuls les .php sont lisibles']);
    $content = file_get_contents($real);
    out(200, ['ok' => true, 'file' => $rel, 'size' => strlen($content), 'content' => $content]);
}

$pattern = (string) ($input['pattern'] ?? '');
if ($pattern === '') out(400, ['ok' => false, 'error' => 'pattern requis']);
$subdirs = $input['subdirs'] ?? [];
$maxResults = min((int) ($input['max_results'] ?? 60), 200);

$bases = [];
if ($subdirs) {
    foreach ($subdirs as $d) {
        $d = trim($d, '/');
        if ($d === '' || strpos($d, '..') !== false) continue;
        $p = ROOT . '/' . $d;
        if (is_dir($p)) $bases[] = $p;
    }
} else {
    $bases = [ROOT];
}
if (!$bases) out(400, ['ok' => false, 'error' => 'aucun sous-dossier valide']);

$results = [];
$filesScanned = 0;
$startTime = microtime(true);
foreach ($bases as $base) {
    $it = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($base, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::SELF_FIRST
    );
    foreach ($it as $file) {
        if (count($results) >= $maxResults) break 2;
        if (microtime(true) - $startTime > 25) break 2;   // budget de temps (evite le timeout PHP-FPM)
        if ($file->isDir()) continue;
        if (strtolower($file->getExtension()) !== 'php') continue;
        // Ignore les dossiers evidents de vendor/cache pour rester rapide et pertinent
        $rel = substr($file->getPathname(), strlen(ROOT) + 1);
        if (preg_match('#(^|/)(vendor|node_modules|cache|\.git)(/|$)#', $rel)) continue;
        $filesScanned++;
        $lines = @file($file->getPathname(), FILE_IGNORE_NEW_LINES);
        if (!$lines) continue;
        foreach ($lines as $i => $line) {
            if (stripos($line, $pattern) !== false) {
                $results[] = ['file' => $rel, 'line' => $i + 1, 'text' => trim(mb_substr($line, 0, 220))];
                if (count($results) >= $maxResults) break;
            }
        }
    }
}
out(200, ['ok' => true, 'pattern' => $pattern, 'files_scanned' => $filesScanned,
          'matches' => count($results), 'results' => $results,
          'truncated' => count($results) >= $maxResults]);

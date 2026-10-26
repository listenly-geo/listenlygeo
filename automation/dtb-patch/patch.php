<?php
if (($_GET['t'] ?? '') !== '__TOKEN__') { http_response_code(404); exit; }
header('Content-Type: text/plain'); @set_time_limit(0); ignore_user_abort(true); ini_set('memory_limit', '512M');
$root = dirname(__DIR__); $zip = $root.'/dtb-hub-patch.zip'; $step = $_GET['step'] ?? '';
echo 'PHP '.PHP_VERSION."\n";
if ($step === 'extract') {
    $z = new ZipArchive;
    if ($z->open($zip) !== true) { echo "ERREUR: paquet illisible\n"; exit; }
    $n = $z->numFiles; $z->extractTo($root); $z->close();
    echo "EXTRACT_OK $n\n"; exit;
}
if ($step === 'artisan') {
    try {
        require $root.'/vendor/autoload.php';
        $app = require $root.'/bootstrap/app.php';
        $k = $app->make(Illuminate\Contracts\Console\Kernel::class); $k->bootstrap();
        foreach ([['optimize:clear', []], ['config:cache', []], ['route:cache', []], ['view:cache', []]] as $c) {
            try { $r = $k->call($c[0], $c[1]); echo $c[0].' => '.$r."\n"; } catch (Throwable $e) { echo $c[0].' ERREUR: '.substr($e->getMessage(), 0, 250)."\n"; }
        }
    } catch (Throwable $e) { echo 'ERREUR: '.substr($e->getMessage(), 0, 300)."\n"; }
    echo "ARTISAN_FINI\n"; exit;
}
if ($step === 'clean') { @unlink($zip); @unlink(__FILE__); echo "NETTOYE\n"; exit; }
echo "etape inconnue\n";

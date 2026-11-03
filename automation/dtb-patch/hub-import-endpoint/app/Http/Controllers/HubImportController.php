<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Str;

/**
 * Reçoit les questions-réponses générées par GitHub (marketforge-hub) et les importe
 * dans le hub du client, avec la même logique que la commande hub:import.
 *
 * Authentification : en-tête X-Hub-Token = HUB_IMPORT_TOKEN (fichier .env).
 */
class HubImportController extends Controller
{
    public function __invoke(Request $request): JsonResponse
    {
        $expected = (string) config('services.hub_import.token');
        $given = (string) $request->header('X-Hub-Token', '');

        if ($expected === '' || ! hash_equals($expected, $given)) {
            return response()->json(['error' => 'unauthorized'], 401);
        }

        $payload = $request->json()->all();
        $site = trim((string) ($payload['site'] ?? ''));

        if ($site === '' || empty($payload['answers']) || ! is_array($payload['answers'])) {
            return response()->json(['error' => 'payload invalide : "site" et "answers" sont requis'], 422);
        }

        $dir = storage_path('app/hub-imports');
        File::ensureDirectoryExists($dir);
        $file = $dir.'/'.Str::uuid().'.json';
        File::put($file, json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

        $status = Artisan::call('hub:import', [
            'site' => $site,
            'file' => $file,
            '--publish' => (bool) ($payload['publish'] ?? false),
            '--dry-run' => (bool) ($payload['dry_run'] ?? false),
        ]);

        File::delete($file);

        return response()->json([
            'ok' => $status === 0,
            'output' => trim(Artisan::output()),
        ], $status === 0 ? 200 : 500);
    }
}

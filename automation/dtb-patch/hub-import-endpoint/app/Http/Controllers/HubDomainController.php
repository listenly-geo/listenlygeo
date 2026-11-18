<?php

namespace App\Http\Controllers;

use App\Models\Site;
use App\Models\SiteDomain;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;

/**
 * Enregistrement et verification du domaine d'un client (18/11/2026). Authentification : X-Hub-Token (comme hub/import).
 *  action=link  {site, host}  : relie le domaine a l'Index (statut pending), cree la ligne si besoin.
 *  action=check {host}        : le domaine pointe-t-il vers l'app (DNS) et repond-il en HTTPS ? Si oui : statut active + verified_at.
 */
class HubDomainController extends Controller
{
    public function __invoke(Request $request): JsonResponse
    {
        $expected = (string) config('services.hub_import.token');
        if ($expected === '' || ! hash_equals($expected, (string) $request->header('X-Hub-Token', ''))) {
            return response()->json(['error' => 'unauthorized'], 401);
        }

        $host = Str::lower(trim((string) $request->input('host', '')));
        if (! preg_match('/^(?=.{1,253}$)(?!-)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/i', $host)) {
            return response()->json(['ok' => false, 'error' => 'domaine invalide'], 422);
        }
        $appHost = parse_url((string) config('app.url'), PHP_URL_HOST) ?: 'app.marketforge.fr';
        if ($host === $appHost || Str::endsWith($host, '.'.$appHost)) {
            return response()->json(['ok' => false, 'error' => 'domaine reserve'], 422);
        }

        if ($request->input('action') === 'link') {
            $site = Site::query()->where('slug', trim((string) $request->input('site', '')))->first();
            if (! $site) {
                return response()->json(['ok' => false, 'error' => 'site introuvable'], 404);
            }
            $domain = SiteDomain::query()->where('host', $host)->first();
            if ($domain && (int) $domain->site_id !== (int) $site->id) {
                return response()->json(['ok' => false, 'error' => 'domaine deja utilise par un autre Index'], 409);
            }
            if (! $domain) {
                $site->domains()->create(['host' => $host, 'is_primary' => ! $site->domains()->exists(), 'status' => 'pending', 'dns_target' => $appHost]);
            }

            return response()->json(['ok' => true, 'host' => $host, 'dns_target' => $appHost]);
        }

        if ($request->input('action') === 'check') {
            $domain = SiteDomain::query()->where('host', $host)->first();
            if (! $domain) {
                return response()->json(['ok' => false, 'error' => 'domaine non enregistre'], 404);
            }
            $dns = $this->pointsToApp($host, $appHost);
            $https = $dns ? $this->httpsAnswers($host) : null;
            if ($dns && $https === true) {
                $domain->forceFill(['status' => 'active', 'verified_at' => $domain->verified_at ?? now()])->save();
            }

            return response()->json(['ok' => true, 'host' => $host, 'dns' => $dns, 'https' => $https, 'active' => $dns && $https === true]);
        }

        return response()->json(['ok' => false, 'error' => 'action inconnue'], 422);
    }

    private function pointsToApp(string $host, string $appHost): bool
    {
        $cname = @dns_get_record($host, DNS_CNAME) ?: [];
        foreach ($cname as $r) {
            if (Str::lower(rtrim((string) ($r['target'] ?? ''), '.')) === Str::lower($appHost)) {
                return true;
            }
        }
        $mine = @dns_get_record($appHost, DNS_A) ?: [];
        $theirs = @dns_get_record($host, DNS_A) ?: [];
        $ips = array_column($mine, 'ip');

        return $ips !== [] && array_intersect($ips, array_column($theirs, 'ip')) !== [];
    }

    /** true = repond en HTTPS avec un certificat valide ; false = ne repond pas ; null = non teste. */
    private function httpsAnswers(string $host): bool
    {
        $ctx = stream_context_create(['http' => ['timeout' => 10, 'ignore_errors' => true, 'follow_location' => 0], 'ssl' => ['verify_peer' => true, 'verify_peer_name' => true]]);
        $body = @file_get_contents('https://'.$host.'/robots.txt', false, $ctx);

        return $body !== false && str_contains((string) $body, 'Sitemap:');
    }
}

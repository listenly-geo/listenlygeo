<?php

namespace App\Http\Controllers;

use App\Models\Site;
use App\Models\SiteDomain;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;

/**
 * Sert un Index sur le domaine du client (ex. expertise.sonsite.com), 18/11/2026.
 * Le domaine est enregistre dans site_domains ; la requete est confiee au controleur habituel des pages publiees.
 * Enregistre uniquement quand l'hote demande n'est pas celui de l'app (voir routes/web.php).
 */
class CustomDomainController extends Controller
{
    public function resolve(Request $request): ?Site
    {
        $host = Str::lower($request->getHost());
        $domain = SiteDomain::query()->where('host', $host)->first();

        return $domain ? Site::query()->whereKey($domain->site_id)->first() : null;
    }

    public function __invoke(Request $request, ?string $path = null)
    {
        $site = $this->resolve($request);
        abort_if(! $site, 404);

        $res = app(PublishedDocsController::class)($request, $site->slug, $path);

        // Les redirections internes restent sur le domaine du client (jamais /docs/{site}/...).
        if ($res instanceof RedirectResponse) {
            $p = (string) parse_url($res->getTargetUrl(), PHP_URL_PATH);
            $prefix = '/docs/'.$site->slug;
            if (str_starts_with($p, $prefix)) {
                return redirect(substr($p, strlen($prefix)) ?: '/');
            }
        }

        return $res;
    }

    public function sitemap(Request $request)
    {
        $site = $this->resolve($request);
        abort_if(! $site, 404);

        return app(SitemapController::class)($site->slug);
    }

    public function robots(Request $request)
    {
        $site = $this->resolve($request);
        abort_if(! $site, 404);

        return response("User-agent: *\nAllow: /\n\nSitemap: https://".Str::lower($request->getHost())."/sitemap.xml\n", 200, ['Content-Type' => 'text/plain; charset=UTF-8']);
    }
}

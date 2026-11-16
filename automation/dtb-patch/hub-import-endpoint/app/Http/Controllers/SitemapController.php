<?php

namespace App\Http\Controllers;

use App\Models\ReleasePage;
use App\Models\Site;
use App\Support\DocsSeo;
use App\Support\DocsTheme;
use Illuminate\Http\Response;
use Illuminate\Support\Arr;

/** Plan du site des Index publies (15/11/2026) : /sitemap.xml (tous) et /docs/{site}/sitemap.xml (un seul). */
class SitemapController extends Controller
{
    public function __invoke(?string $siteSlug = null): Response
    {
        $query = Site::query()->whereNotNull('current_release_id');
        if ($siteSlug !== null) {
            $query->where('slug', $siteSlug);
        }
        $sites = $query->orderBy('id')->get();
        abort_if($siteSlug !== null && $sites->isEmpty(), 404);

        $urls = [];
        foreach ($sites as $site) {
            $settings = $site->settings_json ?? [];
            if (Arr::get($settings, 'seo.noindex', false)) {
                continue;
            }
            $s = ['slug' => $site->slug, 'primaryDomain' => null];
            $lastSite = $site->currentRelease?->published_at;
            if (DocsTheme::normalize(Arr::get($settings, 'appearance.docs_theme')) === 'listenly') {
                $urls[] = [DocsSeo::pageUrl($s, ''), $lastSite];
            }
            $pages = ReleasePage::query()->where('release_id', $site->current_release_id)->orderBy('position')->orderBy('path')->limit(50000)->get(['path', 'updated_at']);
            foreach ($pages as $p) {
                $urls[] = [DocsSeo::pageUrl($s, (string) $p->path), $p->updated_at ?? $lastSite];
            }
        }

        $xml = '<?xml version="1.0" encoding="UTF-8"?>'."\n".'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'."\n";
        foreach (array_slice($urls, 0, 50000) as [$loc, $last]) {
            $xml .= '  <url><loc>'.htmlspecialchars($loc, ENT_XML1 | ENT_QUOTES, 'UTF-8').'</loc>'.($last ? '<lastmod>'.$last->toAtomString().'</lastmod>' : '').'</url>'."\n";
        }
        $xml .= '</urlset>'."\n";

        return response($xml, 200, ['Content-Type' => 'application/xml; charset=UTF-8']);
    }
}

<?php

namespace App\Http\Controllers;

use App\Actions\Docs\BuildPublishedSitePayload;
use App\Models\Site;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class PublishedDocsController extends Controller
{
    public function __construct(
        private readonly BuildPublishedSitePayload $buildPublishedSitePayload,
    ) {}

    public function __invoke(Request $request, string $siteSlug, ?string $path = null): Response|RedirectResponse
    {
        $site = Site::query()
            ->where('slug', $siteSlug)
            ->whereNotNull('current_release_id')
            ->firstOrFail();

        if ($path === null || $path === '') {
            $payload = ($this->buildPublishedSitePayload)($site);

            return redirect()->route('docs.show', [
                'siteSlug' => $site->slug,
                'path' => $payload['page']['path'],
            ]);
        }

        return Inertia::render('docs/show', ($this->buildPublishedSitePayload)($site, $path));
    }
}

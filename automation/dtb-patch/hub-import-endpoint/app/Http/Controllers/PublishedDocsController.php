<?php

namespace App\Http\Controllers;

use App\Actions\Docs\BuildPublishedSitePayload;
use App\Models\Site;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\View;
use App\Support\DocsSeo;
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

            // Hub Listenly : la page d'accueil liste les réponses au lieu de rediriger vers la première.
            if (($payload['site']['docsTheme'] ?? null) === 'listenly') {
                $payload['page'] = [
                    'title' => $payload['site']['brandName'] ?? $site->name,
                    'subtitle' => $payload['site']['tagline'] ?? null,
                    'path' => '',
                    'spaceName' => null,
                    'blocks' => [],
                ];
                $payload['previousPage'] = null;
                $payload['nextPage'] = null;
                $this->shareSeo($site, $payload);

                return Inertia::render('docs/show', $payload);
            }

            return redirect()->route('docs.show', [
                'siteSlug' => $site->slug,
                'path' => $payload['page']['path'],
            ]);
        }

        $payload = ($this->buildPublishedSitePayload)($site, $path);
        $this->shareSeo($site, $payload);

        return Inertia::render('docs/show', $payload);
    }

    /** Titre, description, adresse officielle, donnees structurees et texte sans JavaScript (indexation, 15/11/2026). */
    private function shareSeo(Site $site, array $payload): void
    {
        View::share('seo', DocsSeo::build($payload, (bool) Arr::get($site->settings_json ?? [], 'seo.noindex', false)));
    }
}

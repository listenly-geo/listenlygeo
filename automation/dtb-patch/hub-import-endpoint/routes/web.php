<?php

use App\Http\Controllers\Admin\AdminAddonsController;
use App\Http\Controllers\Admin\AdminAnalyticsController;
use App\Http\Controllers\Admin\AdminDashboardController;
use App\Http\Controllers\Admin\AdminLandingContentController;
use App\Http\Controllers\Admin\AdminPlansController;
use App\Http\Controllers\Admin\AdminReportsController;
use App\Http\Controllers\Admin\AdminUsersController;
use App\Http\Controllers\DashboardAnalyticsController;
use App\Http\Controllers\DashboardBillingController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\DashboardMediaController;
use App\Http\Controllers\DashboardReleasesController;
use App\Http\Controllers\DashboardSettingsController;
use App\Http\Controllers\DashboardSiteExportController;
use App\Http\Controllers\DashboardSitesController;
use App\Http\Controllers\DashboardTeamController;
use App\Http\Controllers\Editor\DraftDocsPreviewController;
use App\Http\Controllers\Editor\PrototypeEditorAiWriterController;
use App\Http\Controllers\Editor\PrototypeEditorAutosaveController;
use App\Http\Controllers\Editor\PrototypeEditorController;
use App\Http\Controllers\Editor\PrototypeEditorExportController;
use App\Http\Controllers\Editor\PrototypeEditorPageTreeController;
use App\Http\Controllers\Editor\PrototypeEditorPublishController;
use App\Http\Controllers\Editor\PrototypeEditorRevisionRestoreController;
use App\Http\Controllers\Editor\PrototypeEditorCommentController;
use App\Http\Controllers\Editor\PrototypeEditorMediaController;
use App\Http\Controllers\Editor\PrototypeEditorSpaceController;
use App\Http\Controllers\PublishedDocsController;
use App\Http\Controllers\StripeWebhookController;
use App\Models\Site;
use App\Models\Space;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Laravel\Fortify\Features;

Route::inertia('/', 'welcome', [
    'canRegister' => Features::enabled(Features::registration()),
])->name('home');

Route::get('media-assets/{asset}', [DashboardMediaController::class, 'show'])->name('media.assets.show');

Route::get('docs/{siteSlug}', PublishedDocsController::class)
    ->name('docs.index');
Route::get('docs/{siteSlug}/{path}', PublishedDocsController::class)
    ->where('path', '.*')
    ->name('docs.show');
Route::post('webhooks/stripe', StripeWebhookController::class)->name('stripe.webhook');

Route::post('hub/import', \App\Http\Controllers\HubImportController::class)->name('hub.import');

Route::middleware(['auth', 'verified'])->group(function () {
    Route::middleware('platform.admin')->prefix('admin')->name('admin.')->group(function () {
        Route::get('/', AdminDashboardController::class)->name('dashboard');
        Route::get('plans', AdminPlansController::class)->name('plans');
        Route::post('plans', [AdminPlansController::class, 'store'])->name('plans.store');
        Route::patch('plans/{subscriptionPlan}', [AdminPlansController::class, 'update'])->name('plans.update');
        Route::post('plans/{subscriptionPlan}/stripe-sync', [AdminPlansController::class, 'sync'])->name('plans.stripe-sync');
        Route::get('users', AdminUsersController::class)->name('users');
        Route::get('reports', AdminReportsController::class)->name('reports');
        Route::get('analytics', AdminAnalyticsController::class)->name('analytics');
        Route::get('commerce', [DashboardBillingController::class, 'adminCommerce'])->name('commerce');
        Route::patch('commerce', [DashboardBillingController::class, 'update'])->name('commerce.update');
        Route::patch('commerce/gateway', [DashboardBillingController::class, 'updateGateway'])->name('commerce.gateway.update');
        Route::get('landing-content', [AdminLandingContentController::class, 'index'])->name('landing-content');
        Route::post('landing-content', [AdminLandingContentController::class, 'store'])->name('landing-content.store');
        Route::patch('landing-content/{landingContent}', [AdminLandingContentController::class, 'update'])->name('landing-content.update');
        Route::delete('landing-content/{landingContent}', [AdminLandingContentController::class, 'destroy'])->name('landing-content.destroy');
        Route::patch('landing-settings', [AdminLandingContentController::class, 'updateSettings'])->name('landing-settings.update');
        Route::get('addons', [AdminAddonsController::class, 'index'])->name('addons.index');
        Route::post('addons/{addon}/install', [AdminAddonsController::class, 'install'])->name('addons.install');
        Route::post('addons/{addon}/uninstall', [AdminAddonsController::class, 'uninstall'])->name('addons.uninstall');
    });

    Route::get('dashboard/commerce', function (Request $request) {
        abort_unless($request->user()?->is_platform_admin === true, 403);

        return redirect()->route('admin.commerce');
    })->name('dashboard.commerce');
    Route::patch('dashboard/commerce', [DashboardBillingController::class, 'update'])->name('dashboard.commerce.update');
    Route::patch('dashboard/commerce/gateway', [DashboardBillingController::class, 'updateGateway'])->name('dashboard.commerce.gateway.update');

    Route::middleware('customer.workspace')->group(function () {
        Route::get('dashboard', DashboardController::class)->name('dashboard');
        Route::get('dashboard/billing', DashboardBillingController::class)->name('dashboard.billing');
        Route::patch('dashboard/billing', [DashboardBillingController::class, 'update'])->name('dashboard.billing.update');
        Route::post('dashboard/billing/checkout', [DashboardBillingController::class, 'checkout'])->name('dashboard.billing.checkout');
        Route::post('dashboard/billing/portal', [DashboardBillingController::class, 'portal'])->name('dashboard.billing.portal');
        Route::post('dashboard/billing/cancel', [DashboardBillingController::class, 'cancel'])->name('dashboard.billing.cancel');
        Route::post('dashboard/billing/resume', [DashboardBillingController::class, 'resume'])->name('dashboard.billing.resume');
        Route::get('dashboard/media', DashboardMediaController::class)->name('dashboard.media');
        Route::post('dashboard/media/sites/{site}/assets', [DashboardMediaController::class, 'store'])->name('dashboard.media.assets.store');
        Route::delete('dashboard/media/assets/{asset}', [DashboardMediaController::class, 'destroy'])->name('dashboard.media.assets.destroy');
        Route::get('dashboard/analytics', DashboardAnalyticsController::class)->name('dashboard.analytics');
        Route::get('dashboard/releases', DashboardReleasesController::class)->name('dashboard.releases');
        Route::get('dashboard/sites', DashboardSitesController::class)->name('dashboard.sites');
        Route::get('dashboard/sites/{site}', [DashboardSitesController::class, 'show'])->name('dashboard.sites.show');
        Route::get('dashboard/sites/{site}/export/{format}', DashboardSiteExportController::class)
            ->whereIn('format', ['html', 'plain-html', 'pdf'])
            ->name('dashboard.sites.export');
        Route::get('dashboard/settings', DashboardSettingsController::class)->name('dashboard.settings');
        Route::get('dashboard/team', DashboardTeamController::class)->name('dashboard.team');
        Route::post('dashboard/releases/sites/{site}/publish', [DashboardReleasesController::class, 'publish'])
            ->name('dashboard.releases.publish');
        Route::post('dashboard/sites', [DashboardSitesController::class, 'storeSite'])->name('dashboard.sites.store');
        Route::post('dashboard/sites/{site}/spaces', [DashboardSitesController::class, 'storeSpace'])->name('dashboard.sites.spaces.store');
        Route::post('dashboard/sites/{site}/logo', [DashboardSitesController::class, 'updateLogo'])
            ->name('dashboard.sites.logo.update');
        Route::patch('dashboard/sites/{site}/appearance', [DashboardSitesController::class, 'updateAppearance'])
            ->name('dashboard.sites.appearance.update');
        Route::patch('dashboard/sites/{site}/default-space', [DashboardSitesController::class, 'updateDefaultSpace'])
            ->name('dashboard.sites.default-space.update');
        Route::patch('dashboard/settings/sites/{site}', [DashboardSettingsController::class, 'updateSiteSettings'])
            ->name('dashboard.settings.sites.update');
        Route::post('dashboard/settings/sites/{site}/domains', [DashboardSettingsController::class, 'storeDomain'])
            ->name('dashboard.settings.domains.store');
        Route::patch('dashboard/settings/domains/{domain}/primary', [DashboardSettingsController::class, 'updatePrimaryDomain'])
            ->name('dashboard.settings.domains.primary.update');
        Route::post('dashboard/team/invitations', [DashboardTeamController::class, 'storeInvitation'])
            ->name('dashboard.team.invitations.store');
        Route::patch('dashboard/team/members/{membership}', [DashboardTeamController::class, 'updateMembershipRole'])
            ->name('dashboard.team.members.update');
        Route::post('editor/api/sites/{site}/publish', PrototypeEditorPublishController::class)
            ->name('editor.sites.publish');
        Route::post('editor/api/sites/{site}/pages', [PrototypeEditorPageTreeController::class, 'store'])
            ->name('editor.sites.pages.store');
        Route::post('editor/api/sites/{site}/spaces', [PrototypeEditorSpaceController::class, 'store'])
            ->name('editor.sites.spaces.store');
        Route::get('editor/api/sites/{site:uuid}/spaces/{space:uuid}/state', [PrototypeEditorController::class, 'state'])
            ->whereUuid('site')
            ->whereUuid('space')
            ->name('editor.sites.spaces.state');
        Route::get('preview/sites/{site}/{path?}', DraftDocsPreviewController::class)
            ->where('path', '.*')
            ->name('editor.sites.preview');
        Route::post('editor/api/pages/{page}/autosave', PrototypeEditorAutosaveController::class)
            ->name('editor.pages.autosave');
        Route::post('editor/api/pages/{page}/revisions/{revision}/restore', PrototypeEditorRevisionRestoreController::class)
            ->name('editor.pages.revisions.restore');
        Route::post('editor/api/pages/{page}/ai-write', PrototypeEditorAiWriterController::class)
            ->name('editor.pages.ai-write');
        Route::get('editor/api/pages/{page}/export/{format}', PrototypeEditorExportController::class)
            ->whereIn('format', ['markdown', 'md', 'pdf', 'html', 'json'])
            ->name('editor.pages.export');
        Route::patch('editor/api/pages/{page}', [PrototypeEditorPageTreeController::class, 'update'])
            ->name('editor.pages.tree.update');
        Route::post('editor/api/pages/{page}/move', [PrototypeEditorPageTreeController::class, 'move'])
            ->name('editor.pages.tree.move');
        Route::delete('editor/api/pages/{page}', [PrototypeEditorPageTreeController::class, 'destroy'])
            ->name('editor.pages.destroy');
        Route::post('editor/api/pages/{page}/comments', [PrototypeEditorCommentController::class, 'store'])
            ->name('editor.pages.comments.store');
        Route::patch('editor/api/comments/{comment}/resolve', [PrototypeEditorCommentController::class, 'resolve'])
            ->name('editor.comments.resolve');
        Route::get('editor/api/sites/{site}/media', [PrototypeEditorMediaController::class, 'index'])
            ->name('editor.sites.media.index');
        Route::post('editor/api/sites/{site}/media', [PrototypeEditorMediaController::class, 'store'])
            ->name('editor.sites.media.store');
        Route::get('editor', function (Request $request, PrototypeEditorController $controller) {
            return $controller->entry($request);
        })->name('editor.prototype.entry');
        Route::get('editor/{site:uuid}/{space:uuid}/{pageSlug}', function (Request $request, Site $site, Space $space, string $pageSlug, PrototypeEditorController $controller) {
            return $controller->spacePage($request, $site, $space, $pageSlug);
        })
            ->whereUuid('site')
            ->whereUuid('space')
            ->where('pageSlug', '[A-Za-z0-9_\-\/]+')
            ->name('editor.space.page');
        Route::get('editor/{site:uuid}/{space:uuid}', function (Request $request, Site $site, Space $space, PrototypeEditorController $controller) {
            return $controller->space($request, $site, $space);
        })
            ->whereUuid('site')
            ->whereUuid('space')
            ->name('editor.space');
        Route::get('editor/{space:uuid}', function (Space $space) {
            $space->loadMissing('site');

            return redirect()->route('editor.space', ['site' => $space->site->uuid, 'space' => $space->uuid]);
        })
            ->whereUuid('space')
            ->name('editor.space.legacy');
        Route::get('editor/{path}', PrototypeEditorController::class)
            ->where('path', '.*')
            ->name('editor.prototype');
        Route::get('prototype', function (Request $request, PrototypeEditorController $controller) {
            return $controller($request, 'index.html');
        })->name('prototype.entry');
        Route::get('prototype/{path}', PrototypeEditorController::class)
            ->where('path', '.*')
            ->name('prototype.asset');
    });
});

require __DIR__.'/settings.php';

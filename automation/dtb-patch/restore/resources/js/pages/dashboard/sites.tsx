import { Head, Link, router, useForm } from '@inertiajs/react';
import {
    ArrowLeft,
    ArrowUpRight,
    CheckCircle2,
    Check,
    Download,
    FolderKanban,
    Globe,
    Image,
    LayoutPanelTop,
    Palette,
    Plus,
    ShieldCheck,
    Trash2,
    Type,
    Upload,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent, FormEvent } from 'react';
import {
    AdminCardHeader,
    AdminEmptyState,
    AdminPageHero,
    AdminStatCard,
    AdminStatGrid,
} from '@/components/admin/page-primitives';
import InputError from '@/components/input-error';
import {
    docsThemeAccentOptions,
    docsThemeFontOptions,
    docsThemeLayoutOptions,
    docsThemeOptions,
} from '@/pages/docs/themes/catalog';
import type { DocsThemeAccentId, DocsThemeFontId, DocsThemeId, DocsThemeLayoutId, DocsThemeOptions } from '@/pages/docs/themes/catalog';
import { useAddon } from '@/hooks/use-addons';
import { dashboard } from '@/routes';

const docsThemeCardDescriptions: Record<DocsThemeId, string> = {
    mintlify: 'Focused reader with clean rails and generous whitespace.',
    gitbook: 'Portal-style docs with top navigation and a strong guide rail.',
    fumadocs: 'Compact framework-style reader with dense navigation.',
    laravel: 'Classic Laravel-docs layout with chapter rail and red accents.',
};

const docsThemeAccentLabels: Record<DocsThemeAccentId, string> = {
    theme: 'Default',
    emerald: 'Emerald',
    blue: 'Blue',
    amber: 'Amber',
    violet: 'Violet',
    rose: 'Rose',
};

type Summary = {
    totalSites: number;
    totalSpaces: number;
    totalPages: number;
    totalPublishedPages: number;
};

type SiteListItem = {
    id: number;
    name: string;
    slug: string;
    status: string;
    visibility: string;
    defaultSpaceName: string | null;
    spacesCount: number;
    pagesCount: number;
    domainsCount: number;
    currentReleaseVersion: string | null;
    updatedAt: string | null;
    editorUrl: string;
    detailsUrl: string;
    docsUrl: string | null;
    isSelected: boolean;
};

type SpaceListItem = {
    id: number;
    name: string;
    slug: string;
    icon: string;
    color: string;
    pagesCount: number;
    publishedPagesCount: number;
    unpublishedPagesCount: number;
    isDefault: boolean;
    updatedAt: string | null;
};

type SelectedSite = {
    id: number;
    uuid: string;
    name: string;
    slug: string;
    status: string;
    visibility: string;
    defaultSpaceId: number | null;
    defaultSpaceName: string | null;
    spacesCount: number;
    pagesCount: number;
    publishedPagesCount: number;
    unpublishedPagesCount: number;
    domainsCount: number;
    currentReleaseVersion: string | null;
    currentReleasePublishedAt: string | null;
    createdAt: string | null;
    updatedAt: string | null;
    docsUrl: string | null;
    editorUrl: string;
    fullSiteExportThemedHtmlUrl: string;
    fullSiteExportPlainHtmlUrl: string;
    fullSiteExportPdfUrl: string;
    branding: {
        logoUrl: string | null;
    };
    appearance: {
        docsTheme: DocsThemeId;
        docsThemeOptions: DocsThemeOptions;
    };
    spaces: SpaceListItem[];
};

type DashboardSitesProps = {
    mode: 'index' | 'show';
    organization: {
        name: string;
        slug: string;
    };
    permissions: {
        canManageSites: boolean;
    };
    summary: Summary;
    sites: SiteListItem[];
    selectedSite: SelectedSite | null;
};

function formatDate(value: string | null): string {
    if (!value) {
        return 'Not yet updated';
    }

    return new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
    }).format(new Date(value));
}

export default function DashboardSites({
    mode,
    organization,
    permissions,
    summary,
    sites,
    selectedSite,
}: DashboardSitesProps) {
    const [createSiteOpen, setCreateSiteOpen] = useState(false);
    const [updatingDefaultSpaceId, setUpdatingDefaultSpaceId] = useState<
        number | null
    >(null);

    const createSiteForm = useForm<{
        name: string;
        visibility: 'private' | 'public';
        initialSpaceName: string;
    }>({
        name: '',
        visibility: 'private',
        initialSpaceName: '',
    });

    const createSpaceForm = useForm({
        name: '',
    });

    const handleCreateSite = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();

        createSiteForm.post('/dashboard/sites', {
            preserveScroll: true,
            onSuccess: () => {
                setCreateSiteOpen(false);
                createSiteForm.reset('name', 'initialSpaceName');
                createSiteForm.setData('visibility', 'private');
            },
        });
    };

    const handleCreateSpace = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();

        if (!selectedSite) {
            return;
        }

        createSpaceForm.post(`/dashboard/sites/${selectedSite.id}/spaces`, {
            preserveScroll: true,
            onSuccess: () => createSpaceForm.reset(),
        });
    };

    const handleDefaultSpace = (spaceId: number) => {
        if (!selectedSite) {
            return;
        }

        setUpdatingDefaultSpaceId(spaceId);

        router.patch(
            `/dashboard/sites/${selectedSite.id}/default-space`,
            { spaceId },
            {
                preserveScroll: true,
                onFinish: () => setUpdatingDefaultSpaceId(null),
            },
        );
    };

    const title = mode === 'show' && selectedSite ? selectedSite.name : 'Sites';

    return (
        <>
            <Head title={title} />

            <div className="admin-page-wrap">
                <AdminPageHero
                    eyebrow={mode === 'show' ? 'Site details' : 'Sites'}
                    title={
                        mode === 'show' && selectedSite
                            ? selectedSite.name
                            : 'Sites list.'
                    }
                    description={
                        mode === 'show' && selectedSite ? (
                            <>
                                Manage spaces, default lane, and release status
                                for {selectedSite.name}.
                            </>
                        ) : (
                            <>
                                Open a docs property in the editor or inspect
                                site details for {organization.name}.
                            </>
                        )
                    }
                    actions={
                        <>
                            {mode === 'show' ? (
                                <Link
                                    href="/dashboard/sites"
                                    className="admin-secondary-link"
                                >
                                    <ArrowLeft size={14} /> Sites list
                                </Link>
                            ) : (
                                <Link
                                    href={dashboard().url}
                                    className="admin-secondary-link"
                                >
                                    Back to overview
                                </Link>
                            )}

                            {mode === 'index' && permissions.canManageSites ? (
                                <button
                                    type="button"
                                    className="admin-primary-link"
                                    onClick={() =>
                                        setCreateSiteOpen((open) => !open)
                                    }
                                >
                                    <Plus size={14} />{' '}
                                    {createSiteOpen
                                        ? 'Hide new site'
                                        : 'Add new site'}
                                </button>
                            ) : null}

                            {selectedSite ? (
                                <a
                                    href={selectedSite.editorUrl}
                                    className="admin-primary-link"
                                >
                                    Open in editor <ArrowUpRight size={14} />
                                </a>
                            ) : null}

                            {selectedSite?.docsUrl ? (
                                <a
                                    href={selectedSite.docsUrl}
                                    className="admin-secondary-link"
                                >
                                    View published docs <Globe size={14} />
                                </a>
                            ) : null}

                            {selectedSite?.currentReleaseVersion ? (
                                <>
                                    <a
                                        href={selectedSite.fullSiteExportPlainHtmlUrl}
                                        className="admin-secondary-link"
                                    >
                                        Export plain HTML <Download size={14} />
                                    </a>
                                    <a
                                        href={selectedSite.fullSiteExportThemedHtmlUrl}
                                        className="admin-secondary-link"
                                    >
                                        Export themed HTML <Download size={14} />
                                    </a>
                                    <a
                                        href={selectedSite.fullSiteExportPdfUrl}
                                        className="admin-secondary-link"
                                    >
                                        Export site PDF <Download size={14} />
                                    </a>
                                </>
                            ) : null}
                        </>
                    }
                />

                <AdminStatGrid>
                    <AdminStatCard
                        label="Sites"
                        value={summary.totalSites}
                        meta="Docs properties in this workspace."
                    />
                    <AdminStatCard
                        label="Spaces"
                        value={summary.totalSpaces}
                        meta="Navigation lanes in this workspace."
                    />
                    <AdminStatCard
                        label="Pages"
                        value={summary.totalPages}
                        meta="Draft and published pages in this workspace."
                    />
                    <AdminStatCard
                        label="Published Pages"
                        value={summary.totalPublishedPages}
                        meta="Pages currently available in workspace releases."
                    />
                </AdminStatGrid>

                {mode === 'show' && selectedSite ? (
                    <SiteDetails
                        key={selectedSite.id}
                        permissions={permissions}
                        selectedSite={selectedSite}
                        createSpaceForm={createSpaceForm}
                        updatingDefaultSpaceId={updatingDefaultSpaceId}
                        onCreateSpace={handleCreateSpace}
                        onDefaultSpace={handleDefaultSpace}
                    />
                ) : (
                    <SitesList
                        permissions={permissions}
                        sites={sites}
                        createSiteOpen={createSiteOpen}
                        createSiteForm={createSiteForm}
                        onCreateSite={handleCreateSite}
                        onToggleCreateSite={() =>
                            setCreateSiteOpen((open) => !open)
                        }
                    />
                )}
            </div>
        </>
    );
}

function SitesList({
    permissions,
    sites,
    createSiteOpen,
    createSiteForm,
    onCreateSite,
    onToggleCreateSite,
}: {
    permissions: { canManageSites: boolean };
    sites: SiteListItem[];
    createSiteOpen: boolean;
    createSiteForm: ReturnType<
        typeof useForm<{
            name: string;
            visibility: 'private' | 'public';
            initialSpaceName: string;
        }>
    >;
    onCreateSite: (event: FormEvent<HTMLFormElement>) => void;
    onToggleCreateSite: () => void;
}) {
    return (
        <section className="admin-management-grid">
            <div className="admin-column-stack">
                <section className="admin-surface">
                    <AdminCardHeader
                        label="Create site"
                        title="Add a new docs property"
                        action={
                            <span className="admin-pill admin-pill-accent">
                                <Plus size={12} /> site scaffold
                            </span>
                        }
                    />

                    {permissions.canManageSites ? (
                        createSiteOpen ? (
                            <form className="admin-form-grid" onSubmit={onCreateSite}>
                                <label className="admin-field admin-field-full">
                                    <span>Site name</span>
                                    <input
                                        type="text"
                                        value={createSiteForm.data.name}
                                        onChange={(event) =>
                                            createSiteForm.setData(
                                                'name',
                                                event.target.value,
                                            )
                                        }
                                        className="admin-text-input"
                                        placeholder="Teleman"
                                    />
                                    <InputError message={createSiteForm.errors.name} />
                                </label>

                                <label className="admin-field">
                                    <span>Visibility</span>
                                    <select
                                        value={createSiteForm.data.visibility}
                                        onChange={(event) =>
                                            createSiteForm.setData(
                                                'visibility',
                                                event.target.value as
                                                    | 'private'
                                                    | 'public',
                                            )
                                        }
                                        className="admin-select-input"
                                    >
                                        <option value="private">Private</option>
                                        <option value="public">Public</option>
                                    </select>
                                    <InputError message={createSiteForm.errors.visibility} />
                                </label>

                                <label className="admin-field">
                                    <span>First space</span>
                                    <input
                                        type="text"
                                        value={createSiteForm.data.initialSpaceName}
                                        onChange={(event) =>
                                            createSiteForm.setData(
                                                'initialSpaceName',
                                                event.target.value,
                                            )
                                        }
                                        className="admin-text-input"
                                        placeholder="Getting Started"
                                    />
                                    <InputError message={createSiteForm.errors.initialSpaceName} />
                                </label>

                                <div className="admin-overview-strip admin-site-grid-span">
                                    <div>
                                        <strong>Auto-created scaffold</strong>
                                        <span>New site comes with first space and Quickstart page.</span>
                                    </div>
                                    <div className="admin-chip-row">
                                        <span className="admin-chip">1 site</span>
                                        <span className="admin-chip">1 space</span>
                                        <span className="admin-chip">1 Quickstart page</span>
                                    </div>
                                </div>

                                <div className="admin-form-actions admin-field-full">
                                    <button
                                        type="submit"
                                        className="admin-button admin-button-primary"
                                        disabled={createSiteForm.processing}
                                    >
                                        {createSiteForm.processing
                                            ? 'Creating...'
                                            : 'Create site'}
                                    </button>
                                    <button
                                        type="button"
                                        className="admin-button admin-button-secondary"
                                        onClick={onToggleCreateSite}
                                        disabled={createSiteForm.processing}
                                    >
                                        Cancel
                                    </button>
                                </div>
                            </form>
                        ) : (
                            <div className="admin-overview-strip">
                                <div>
                                    <strong>Need a new site?</strong>
                                    <small>Create new docs property with one click, then open in editor.</small>
                                </div>
                                <div className="admin-form-actions">
                                    <button
                                        type="button"
                                        className="admin-button admin-button-primary"
                                        onClick={onToggleCreateSite}
                                    >
                                        <Plus size={13} /> Add new site
                                    </button>
                                </div>
                            </div>
                        )
                    ) : (
                        <AdminEmptyState icon={<ShieldCheck size={16} />}>
                            Read-only role. Owners and admins can create new sites.
                        </AdminEmptyState>
                    )}
                </section>
            </div>

            <div className="admin-column-stack">
                <section className="admin-surface">
                    <AdminCardHeader
                        label="Sites list"
                        title="Choose a docs property"
                        action={<span className="admin-pill">{sites.length} tracked</span>}
                    />

                    <div className="admin-directory-list admin-site-list">
                        {sites.map((site) => (
                            <article key={site.id} className="admin-directory-item admin-site-card">
                                <div className="admin-directory-head">
                                    <div>
                                        <strong>{site.name}</strong>
                                        <small>{site.slug}</small>
                                    </div>

                                    <div className="admin-pill-row">
                                        <span className="admin-pill">
                                            {site.visibility}
                                        </span>
                                        <span className="admin-pill">{site.status}</span>
                                    </div>
                                </div>

                                <div className="admin-chip-row">
                                    <span className="admin-chip">
                                        {site.spacesCount} spaces
                                    </span>
                                    <span className="admin-chip">
                                        {site.pagesCount} pages
                                    </span>
                                    <span className="admin-chip">
                                        {site.domainsCount} domains
                                    </span>
                                    {site.currentReleaseVersion ? (
                                        <span className="admin-chip">
                                            {site.currentReleaseVersion}
                                        </span>
                                    ) : null}
                                </div>

                                <small className="admin-directory-meta">
                                    Default: {site.defaultSpaceName ?? 'Not set'} · Updated{' '}
                                    {formatDate(site.updatedAt)}
                                </small>

                                <div className="admin-site-card-actions">
                                    <a
                                        href={site.editorUrl}
                                        className="admin-button admin-button-primary"
                                    >
                                        Open in editor <ArrowUpRight size={13} />
                                    </a>
                                    <Link
                                        href={site.detailsUrl}
                                        className="admin-button admin-button-secondary"
                                    >
                                        Details
                                    </Link>
                                    {site.docsUrl ? (
                                        <a
                                            href={site.docsUrl}
                                            className="admin-button admin-button-secondary"
                                        >
                                            Published docs <Globe size={13} />
                                        </a>
                                    ) : null}
                                </div>
                            </article>
                        ))}
                    </div>
                </section>
            </div>
        </section>
    );
}

type SiteDetailsProps = {
    permissions: { canManageSites: boolean };
    selectedSite: SelectedSite;
    createSpaceForm: ReturnType<typeof useForm<{ name: string }>>;
    updatingDefaultSpaceId: number | null;
    onCreateSpace: (event: FormEvent<HTMLFormElement>) => void;
    onDefaultSpace: (spaceId: number) => void;
};

function SiteDetails({
    permissions,
    selectedSite,
    createSpaceForm,
    updatingDefaultSpaceId,
    onCreateSpace,
    onDefaultSpace,
}: SiteDetailsProps) {
    const logoInputRef = useRef<HTMLInputElement>(null);
    const [logoPreviewUrl, setLogoPreviewUrl] = useState<string | null>(null);
    const [logoInputKey, setLogoInputKey] = useState(0);

    const logoForm = useForm<{
        logo: File | null;
        clearLogo: boolean;
    }>({
        logo: null,
        clearLogo: false,
    });

    const appearanceForm = useForm<{
        docsTheme: DocsThemeId;
        docsThemeAccent: DocsThemeAccentId;
        docsThemeFont: DocsThemeFontId;
        docsThemeLayout: DocsThemeLayoutId;
    }>({
        docsTheme: selectedSite.appearance.docsTheme,
        docsThemeAccent: selectedSite.appearance.docsThemeOptions.accentColor,
        docsThemeFont: selectedSite.appearance.docsThemeOptions.fontFamily,
        docsThemeLayout: selectedSite.appearance.docsThemeOptions.layoutWidth,
    });

    const hasDocsThemeAddon = useAddon('docs-theme');
    const availableThemes = docsThemeOptions.filter((t) => t.id !== 'laravel' || hasDocsThemeAddon);
    const selectedTheme = availableThemes.find((theme) => theme.id === appearanceForm.data.docsTheme) ?? availableThemes[0];
    const selectedAccent = docsThemeAccentOptions.find((accent) => accent.id === appearanceForm.data.docsThemeAccent) ?? docsThemeAccentOptions[0];
    const selectedFont = docsThemeFontOptions.find((font) => font.id === appearanceForm.data.docsThemeFont) ?? docsThemeFontOptions[0];
    const selectedLayout = docsThemeLayoutOptions.find((layout) => layout.id === appearanceForm.data.docsThemeLayout) ?? docsThemeLayoutOptions[0];
    const hasLogoChange = logoForm.data.logo !== null || logoForm.data.clearLogo;
    const logoPreview = logoPreviewUrl ?? (logoForm.data.clearLogo ? null : selectedSite.branding.logoUrl);

    useEffect(() => () => {
        if (logoPreviewUrl) {
            URL.revokeObjectURL(logoPreviewUrl);
        }
    }, [logoPreviewUrl]);

    const handleLogoChange = (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0] ?? null;

        logoForm.setData('logo', file);
        logoForm.setData('clearLogo', false);

        setLogoPreviewUrl(file ? URL.createObjectURL(file) : null);
    };

    const handleClearLogo = () => {
        logoForm.setData('logo', null);
        logoForm.setData('clearLogo', true);
        setLogoPreviewUrl(null);
        setLogoInputKey((current) => current + 1);
    };

    const handleLogoSubmit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();

        logoForm.post(`/dashboard/sites/${selectedSite.id}/logo`, {
            preserveScroll: true,
            onSuccess: () => {
                logoForm.reset();
                logoForm.setData('clearLogo', false);
                setLogoPreviewUrl(null);
                setLogoInputKey((current) => current + 1);
            },
        });
    };

    const handleAppearanceSubmit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();

        appearanceForm.patch(`/dashboard/sites/${selectedSite.id}/appearance`, {
            preserveScroll: true,
        });
    };

    return (
        <section className="admin-management-grid">
            <div className="admin-column-stack">
                <section className="admin-surface">
                    <AdminCardHeader
                        label="Site"
                        title="Details"
                        action={
                            <div className="admin-pill-row">
                                <span className="admin-pill admin-pill-accent">
                                    {selectedSite.visibility}
                                </span>
                                <span className="admin-pill">
                                    {selectedSite.status}
                                </span>
                                {selectedSite.currentReleaseVersion ? (
                                    <span className="admin-pill">
                                        {selectedSite.currentReleaseVersion}
                                    </span>
                                ) : null}
                            </div>
                        }
                    />

                    <div className="admin-site-grid">
                        <div>
                            <span className="admin-site-key">Slug</span>
                            <strong>{selectedSite.slug}</strong>
                        </div>
                        <div>
                            <span className="admin-site-key">Default space</span>
                            <strong>
                                {selectedSite.defaultSpaceName ?? 'Not set'}
                            </strong>
                        </div>
                        <div>
                            <span className="admin-site-key">Release</span>
                            <strong>
                                {selectedSite.currentReleaseVersion ??
                                    'No release'}
                            </strong>
                        </div>
                        <div>
                            <span className="admin-site-key">Published</span>
                            <strong>
                                {selectedSite.currentReleasePublishedAt
                                    ? formatDate(
                                          selectedSite.currentReleasePublishedAt,
                                      )
                                    : 'No release yet'}
                            </strong>
                        </div>
                        <div>
                            <span className="admin-site-key">Spaces</span>
                            <strong>{selectedSite.spacesCount}</strong>
                        </div>
                        <div>
                            <span className="admin-site-key">Pages</span>
                            <strong>{selectedSite.pagesCount}</strong>
                        </div>
                        <div>
                            <span className="admin-site-key">Published pages</span>
                            <strong>{selectedSite.publishedPagesCount}</strong>
                        </div>
                        <div>
                            <span className="admin-site-key">Unpublished pages</span>
                            <strong>{selectedSite.unpublishedPagesCount}</strong>
                        </div>
                        <div>
                            <span className="admin-site-key">Domains</span>
                            <strong>{selectedSite.domainsCount}</strong>
                        </div>
                        <div>
                            <span className="admin-site-key">Created</span>
                            <strong>{formatDate(selectedSite.createdAt)}</strong>
                        </div>
                        <div>
                            <span className="admin-site-key">Updated</span>
                            <strong>{formatDate(selectedSite.updatedAt)}</strong>
                        </div>
                        <div className="admin-site-grid-span">
                            <span className="admin-site-key">Site UUID</span>
                            <strong className="admin-site-code">
                                {selectedSite.uuid}
                            </strong>
                        </div>
                        <div>
                            <span className="admin-site-key">Published docs</span>
                            {selectedSite.docsUrl ? (
                                <a
                                    href={selectedSite.docsUrl}
                                    className="admin-site-value-link"
                                >
                                    View published docs
                                </a>
                            ) : (
                                <strong>Not published</strong>
                            )}
                        </div>
                        <div>
                            <span className="admin-site-key">Editor URL</span>
                            <a
                                href={selectedSite.editorUrl}
                                className="admin-site-value-link"
                            >
                                Open editor
                            </a>
                        </div>
                        <div>
                            <span className="admin-site-key">Export</span>
                            {selectedSite.currentReleaseVersion ? (
                                <div className="admin-chip-row">
                                    <a href={selectedSite.fullSiteExportPlainHtmlUrl} className="admin-site-value-link">
                                        Plain HTML
                                    </a>
                                    <a href={selectedSite.fullSiteExportThemedHtmlUrl} className="admin-site-value-link">
                                        Themed HTML
                                    </a>
                                    <a href={selectedSite.fullSiteExportPdfUrl} className="admin-site-value-link">
                                        Full site PDF
                                    </a>
                                </div>
                            ) : (
                                <strong>Publish a release first</strong>
                            )}
                        </div>
                    </div>
                </section>

                <section className="admin-surface">
                    <AdminCardHeader
                        label="Brand"
                        title="Site logo"
                        action={<span className="admin-pill admin-pill-accent"><Image size={12} /> {logoPreview ? 'Custom' : 'Fallback'}</span>}
                    />

                    {permissions.canManageSites ? (
                        <form className="admin-form-grid" onSubmit={handleLogoSubmit}>
                            <div className="admin-overview-strip admin-site-grid-span">
                                <div className="flex min-w-0 items-center gap-4">
                                    <span className="grid h-16 w-16 shrink-0 place-items-center overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] p-2 text-lg font-semibold text-[var(--text-muted)]">
                                        {logoPreview ? (
                                            <img src={logoPreview} alt={`${selectedSite.name} logo`} className="h-full w-full object-contain" />
                                        ) : (
                                            selectedSite.name.trim().charAt(0).toUpperCase()
                                        )}
                                    </span>
                                    <div>
                                        <strong>{selectedSite.name}</strong>
                                        <span>{logoPreview ? 'Logo set for this site.' : 'Docs will use the generated site mark.'}</span>
                                    </div>
                                </div>
                                <div className="admin-chip-row">
                                    <span className="admin-chip">{logoPreview ? 'custom logo' : 'generated mark'}</span>
                                </div>
                            </div>

                            <input
                                key={logoInputKey}
                                ref={logoInputRef}
                                type="file"
                                className="sr-only"
                                accept="image/png,image/jpeg,image/webp"
                                onChange={handleLogoChange}
                            />
                            <InputError message={logoForm.errors.logo} />
                            <InputError message={logoForm.errors.clearLogo} />

                            <div className="admin-form-actions admin-field-full">
                                <button type="button" className="admin-button admin-button-secondary" onClick={() => logoInputRef.current?.click()} disabled={logoForm.processing}>
                                    <Upload size={13} /> {logoPreview ? 'Change logo' : 'Upload logo'}
                                </button>
                                {logoPreview ? (
                                    <button type="button" className="admin-button admin-button-secondary" onClick={handleClearLogo} disabled={logoForm.processing}>
                                        <Trash2 size={13} /> Remove logo
                                    </button>
                                ) : null}
                                <button type="submit" className="admin-button admin-button-primary" disabled={logoForm.processing || !hasLogoChange}>
                                    {logoForm.processing ? 'Saving...' : 'Save logo'}
                                </button>
                            </div>
                        </form>
                    ) : (
                        <AdminEmptyState icon={<ShieldCheck size={16} />}>
                            Owners and admins can update the site logo.
                        </AdminEmptyState>
                    )}
                </section>

                <section className="admin-surface">
                    <AdminCardHeader
                        label="Docs theme"
                        title="Reader appearance"
                        action={<span className="admin-pill admin-pill-accent"><Palette size={12} /> {selectedTheme.name}</span>}
                    />

                    {permissions.canManageSites ? (
                        <form className="mt-4 grid gap-4" onSubmit={handleAppearanceSubmit}>
                            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-subtle)] p-3">
                                <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_176px]">
                                    <div className="min-w-0">
                                        <span className="mb-2 inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--bg-elevated)] px-2.5 py-1 text-xs font-semibold text-[var(--text-muted)]">
                                            <Palette size={13} /> Active reader
                                        </span>
                                        <strong className="block text-base text-[var(--text)]">{selectedTheme.name}</strong>
                                        <p className="mt-1 text-sm leading-6 text-[var(--text-muted)]">
                                            {selectedAccent.name} accent, {selectedFont.name} type, {selectedLayout.name.toLowerCase()} width.
                                        </p>
                                        <div className="mt-3 flex flex-wrap gap-2">
                                            <div className="rounded-full border border-[var(--border)] bg-[var(--bg-elevated)] px-2.5 py-1 text-xs font-medium text-[var(--text-muted)]">{selectedTheme.name}</div>
                                            <div className="rounded-full border border-[var(--border)] bg-[var(--bg-elevated)] px-2.5 py-1 text-xs font-medium text-[var(--text-muted)]">{selectedLayout.name}</div>
                                        </div>
                                    </div>

                                    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] p-2 shadow-sm" aria-hidden="true">
                                        <div className="mb-2 flex items-center justify-between gap-2">
                                            <div className="h-2 w-12 rounded-full" style={{ background: selectedAccent.swatch }} />
                                            <div className="h-2 w-7 rounded-full bg-[var(--border)]" />
                                        </div>
                                        <div className="grid h-[86px] grid-cols-[34px_minmax(0,1fr)] gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-subtle)] p-2">
                                            <div className="space-y-1.5 border-r border-[var(--border)] pr-2">
                                                <div className="h-2 rounded-full bg-[var(--border)]" />
                                                <div className="h-2 rounded-full bg-[var(--border)]" />
                                                <div className="h-2 rounded-full" style={{ background: selectedAccent.swatch }} />
                                            </div>
                                            <div className="space-y-2">
                                                <div className="h-3 w-3/4 rounded-full bg-[var(--text)] opacity-80" />
                                                <div className="h-2 rounded-full bg-[var(--border)]" />
                                                <div className="h-2 w-5/6 rounded-full bg-[var(--border)]" />
                                                <div className={`h-8 rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] ${appearanceForm.data.docsThemeLayout === 'boxed' ? 'mx-auto w-4/5' : 'w-full'}`} />
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="admin-field admin-field-full">
                                <span>Theme template</span>
                                <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(180px,1fr))]">
                                    {availableThemes.map((theme) => {
                                        const isSelected = appearanceForm.data.docsTheme === theme.id;

                                        return (
                                            <button
                                                key={theme.id}
                                                type="button"
                                                className={`group flex min-h-[190px] flex-col justify-between overflow-hidden rounded-lg border p-3 text-left transition ${
                                                    isSelected
                                                        ? 'border-[#1f4c40] bg-[rgba(31,76,64,0.07)] shadow-[0_16px_42px_-32px_rgba(31,76,64,0.65)] ring-1 ring-[#1f4c40]/20'
                                                        : 'border-[var(--border)] bg-[var(--bg-elevated)] hover:border-[var(--border-strong)] hover:bg-[var(--bg-subtle)]'
                                                }`}
                                                onClick={() => appearanceForm.setData('docsTheme', theme.id)}
                                                aria-pressed={isSelected}
                                            >
                                                <div className="flex items-start justify-between gap-3">
                                                    <div className="min-w-0">
                                                        <strong className="block text-sm font-semibold text-[var(--text)]">{theme.name}</strong>
                                                        <p className="mt-1 text-xs leading-5 text-[var(--text-muted)]">{docsThemeCardDescriptions[theme.id]}</p>
                                                    </div>
                                                    <div className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border ${isSelected ? 'border-[#1f4c40] bg-[#1f4c40] text-white' : 'border-[var(--border)] text-transparent group-hover:text-[var(--text-muted)]'}`}>
                                                        <Check size={13} />
                                                    </div>
                                                </div>

                                                <div className="mt-4 rounded-md border border-black/10 bg-white/70 p-2 shadow-sm" aria-hidden="true">
                                                    <div className="mb-2 flex items-center gap-1.5">
                                                        {theme.swatches.map((color) => (
                                                            <div
                                                                key={`${theme.id}-${color}`}
                                                                className="h-4 flex-1 rounded border border-black/10"
                                                                style={{ background: color }}
                                                            />
                                                        ))}
                                                    </div>
                                                    <div className="grid h-14 grid-cols-[26px_minmax(0,1fr)] gap-2 rounded border border-[var(--border)] bg-[var(--bg-subtle)] p-1.5">
                                                        <div className="space-y-1 border-r border-[var(--border)] pr-1.5">
                                                            <div className="h-1.5 rounded-full bg-[var(--border)]" />
                                                            <div className="h-1.5 rounded-full bg-[var(--border)]" />
                                                            <div className="h-1.5 rounded-full" style={{ background: theme.swatches[2] }} />
                                                        </div>
                                                        <div className="space-y-1.5">
                                                            <div className="h-2 w-2/3 rounded-full bg-[var(--text)] opacity-70" />
                                                            <div className="h-1.5 rounded-full bg-[var(--border)]" />
                                                            <div className="h-1.5 w-4/5 rounded-full bg-[var(--border)]" />
                                                            <div className="h-4 rounded border border-[var(--border)] bg-[var(--bg-elevated)]" />
                                                        </div>
                                                    </div>
                                                </div>
                                                <small className="mt-3 block text-[11px] font-semibold text-[var(--text-muted)]">{theme.name} style</small>
                                            </button>
                                        );
                                    })}
                                </div>
                                <InputError message={appearanceForm.errors.docsTheme} />
                            </div>

                            <div className="admin-field admin-field-full">
                                <span>Accent color</span>
                                <div className="grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(118px,1fr))]">
                                    {docsThemeAccentOptions.map((accent) => {
                                        const isSelected = appearanceForm.data.docsThemeAccent === accent.id;
                                        const label = docsThemeAccentLabels[accent.id];

                                        return (
                                            <button
                                                key={accent.id}
                                                type="button"
                                                className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-left text-sm transition ${
                                                    isSelected
                                                        ? 'border-[#1f4c40] bg-[rgba(31,76,64,0.07)] text-[var(--text)] ring-1 ring-[#1f4c40]/20'
                                                        : 'border-[var(--border)] bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:border-[var(--border-strong)] hover:text-[var(--text)]'
                                                }`}
                                                onClick={() => appearanceForm.setData('docsThemeAccent', accent.id)}
                                                aria-pressed={isSelected}
                                            >
                                                <div className="h-6 w-6 shrink-0 rounded-full border border-black/10" style={{ background: accent.swatch }} aria-hidden="true" />
                                                <strong className="truncate font-medium">{label}</strong>
                                                {isSelected ? <Check className="ml-auto h-4 w-4 text-[#1f4c40]" /> : null}
                                            </button>
                                        );
                                    })}
                                </div>
                                <InputError message={appearanceForm.errors.docsThemeAccent} />
                            </div>

                            <div className="admin-field admin-field-full">
                                <span>Font family</span>
                                <div className="grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(118px,1fr))]">
                                    {docsThemeFontOptions.map((font) => {
                                        const isSelected = appearanceForm.data.docsThemeFont === font.id;

                                        return (
                                            <button
                                                key={font.id}
                                                type="button"
                                                className={`rounded-lg border px-3 py-3 text-left transition ${
                                                    isSelected
                                                        ? 'border-[#1f4c40] bg-[rgba(31,76,64,0.07)] ring-1 ring-[#1f4c40]/20'
                                                        : 'border-[var(--border)] bg-[var(--bg-elevated)] hover:border-[var(--border-strong)] hover:bg-[var(--bg-subtle)]'
                                                }`}
                                                onClick={() => appearanceForm.setData('docsThemeFont', font.id)}
                                                aria-pressed={isSelected}
                                            >
                                                <div className="mb-2 flex items-center justify-between gap-2 text-sm font-semibold text-[var(--text)]">
                                                    <div className="inline-flex items-center gap-2"><Type size={14} /> {font.name}</div>
                                                    {isSelected ? <Check className="h-4 w-4 text-[#1f4c40]" /> : null}
                                                </div>
                                                <div className="block text-sm text-[var(--text-muted)]" style={{ fontFamily: font.css }}>The quick docs page</div>
                                            </button>
                                        );
                                    })}
                                </div>
                                <InputError message={appearanceForm.errors.docsThemeFont} />
                            </div>

                            <div className="admin-field admin-field-full">
                                <span>Layout width</span>
                                <div className="grid gap-1 rounded-lg border border-[var(--border)] bg-[var(--bg-subtle)] p-1 sm:grid-cols-2">
                                    {docsThemeLayoutOptions.map((layout) => {
                                        const isSelected = appearanceForm.data.docsThemeLayout === layout.id;

                                        return (
                                            <button
                                                key={layout.id}
                                                type="button"
                                                className={`rounded-md px-3 py-2.5 text-left transition ${
                                                    isSelected
                                                        ? 'bg-[var(--bg-elevated)] text-[var(--text)] shadow-sm ring-1 ring-[#1f4c40]/25'
                                                        : 'text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text)]'
                                                }`}
                                                onClick={() => appearanceForm.setData('docsThemeLayout', layout.id)}
                                                aria-pressed={isSelected}
                                            >
                                                <div className="mb-2 flex items-center justify-between gap-2 text-sm font-semibold">
                                                    <div className="inline-flex items-center gap-2"><LayoutPanelTop size={14} /> {layout.name}</div>
                                                    {isSelected ? <Check className="h-4 w-4 text-[#1f4c40]" /> : null}
                                                </div>
                                                <div className="flex h-7 items-center rounded border border-[var(--border)] bg-[var(--bg-subtle)] p-1" aria-hidden="true">
                                                    <div className={`h-full rounded bg-[#1f4c40]/15 ring-1 ring-[#1f4c40]/20 ${layout.id === 'boxed' ? 'mx-auto w-2/3' : 'w-full'}`} />
                                                </div>
                                            </button>
                                        );
                                    })}
                                </div>
                                <InputError message={appearanceForm.errors.docsThemeLayout} />
                            </div>

                            <div className="admin-form-actions admin-field-full">
                                <button type="submit" className="admin-button admin-button-primary" disabled={appearanceForm.processing}>
                                    {appearanceForm.processing ? 'Saving...' : 'Save reader appearance'}
                                </button>
                            </div>
                        </form>
                    ) : (
                        <AdminEmptyState icon={<ShieldCheck size={16} />}>
                            Owners and admins can change the docs theme and available reader options.
                        </AdminEmptyState>
                    )}
                </section>
            </div>

            <div className="admin-column-stack">
                <section className="admin-surface">
                    <AdminCardHeader
                        label="Spaces"
                        title="Navigation lanes"
                        action={
                            <span className="admin-pill">
                                {selectedSite.spaces.length} spaces
                            </span>
                        }
                    />

                    {permissions.canManageSites ? (
                        <form
                            className="admin-form-grid admin-form-grid-inline"
                            onSubmit={onCreateSpace}
                        >
                            <label className="admin-field admin-field-grow">
                                <span>New space</span>
                                <input
                                    type="text"
                                    value={createSpaceForm.data.name}
                                    onChange={(event) =>
                                        createSpaceForm.setData(
                                            'name',
                                            event.target.value,
                                        )
                                    }
                                    className="admin-text-input"
                                    placeholder="API Reference"
                                />
                                <InputError
                                    message={createSpaceForm.errors.name}
                                />
                            </label>

                            <div className="admin-form-actions admin-form-actions-inline">
                                <button
                                    type="submit"
                                    className="admin-button admin-button-primary"
                                    disabled={createSpaceForm.processing}
                                >
                                    {createSpaceForm.processing
                                        ? 'Adding...'
                                        : 'Add space'}
                                </button>
                            </div>
                        </form>
                    ) : (
                        <AdminEmptyState icon={<ShieldCheck size={16} />}>
                            Read-only role. Owners and admins manage spaces.
                        </AdminEmptyState>
                    )}

                    <div className="admin-space-list">
                        {selectedSite.spaces.map((space) => (
                            <div key={space.id} className="admin-space-card">
                                <div className="admin-space-head">
                                    <div className="admin-list-leading">
                                        <span
                                            className="admin-space-icon"
                                            style={{ backgroundColor: space.color }}
                                        >
                                            <FolderKanban size={14} />
                                        </span>
                                        <div>
                                            <strong>{space.name}</strong>
                                            <small>{space.slug}</small>
                                        </div>
                                    </div>

                                    <div className="admin-inline-actions">
                                        {space.isDefault ? (
                                            <span className="admin-pill admin-pill-accent">
                                                <CheckCircle2 size={12} />
                                                default
                                            </span>
                                        ) : permissions.canManageSites ? (
                                            <button
                                                type="button"
                                                className="admin-button admin-button-secondary"
                                                onClick={() =>
                                                    onDefaultSpace(space.id)
                                                }
                                                disabled={
                                                    updatingDefaultSpaceId !== null
                                                }
                                            >
                                                {updatingDefaultSpaceId === space.id
                                                    ? 'Updating...'
                                                    : 'Make default'}
                                            </button>
                                        ) : null}
                                    </div>
                                </div>

                                <div className="admin-chip-row">
                                    <span className="admin-chip">
                                        {space.pagesCount} pages
                                    </span>
                                    <span className="admin-chip">
                                        {space.publishedPagesCount} published
                                    </span>
                                    {space.unpublishedPagesCount > 0 ? (
                                        <span className="admin-chip">
                                            {space.unpublishedPagesCount}{' '}
                                            unpublished
                                        </span>
                                    ) : null}
                                    <span className="admin-chip">
                                        Updated {formatDate(space.updatedAt)}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </section>
            </div>
        </section>
    );
}

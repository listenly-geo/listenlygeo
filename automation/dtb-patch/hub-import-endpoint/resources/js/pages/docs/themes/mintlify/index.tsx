import { BookOpen, ChevronLeft, ChevronRight, FileText, Menu, Search, X } from 'lucide-react';
import { useState } from 'react';
import { BlockRenderer, DocsLink, PlatformBrandingBadge, docsBlockKey, docsHomeHref, docsHref } from '../shared';
import type { DocsNavigationNode, DocsSite, DocsThemeDefinition, DocsThemeProps, NavigationGroup } from '../types';

function NavigationTree({
    nodes,
    site,
    currentPath,
}: {
    nodes: DocsNavigationNode[];
    site: DocsSite;
    currentPath: string;
}) {
    return (
        <ul className="space-y-1">
            {nodes.map((node) => {
                const isActive = node.path === currentPath;
                const isBranch = node.children.length > 0;

                return (
                    <li key={node.path}>
                        <DocsLink
                            href={docsHref(site, node.path)}
                            className={`group flex items-center gap-2 rounded-md px-2.5 py-2 text-[13px] font-medium transition ${
                                isActive
                                    ? 'bg-[var(--docs-accent-soft)] text-[var(--docs-accent-text)] ring-1 ring-[var(--docs-accent-ring)]'
                                    : 'text-[var(--docs-muted)] hover:bg-[var(--docs-surface-muted)] hover:text-[var(--docs-text)]'
                            }`}
                        >
                            <FileText className={`h-3.5 w-3.5 shrink-0 ${isActive ? 'text-[var(--docs-accent)]' : 'text-[var(--docs-faint)] group-hover:text-[var(--docs-muted)]'}`} />
                            <span className="truncate">{node.title}</span>
                            {isBranch ? <ChevronRight className={`ml-auto h-3.5 w-3.5 ${isActive ? 'text-[var(--docs-accent)]' : 'text-[var(--docs-faint)]'}`} /> : null}
                        </DocsLink>
                        {node.children.length > 0 ? (
                            <div className="mt-1 ml-4 border-l border-[var(--docs-border)] pl-3">
                                <NavigationTree nodes={node.children} site={site} currentPath={currentPath} />
                            </div>
                        ) : null}
                    </li>
                );
            })}
        </ul>
    );
}

function DocsBrand({ site }: { site: DocsSite }) {
    const brandInitial = (site.brandName || site.name || 'D').trim().charAt(0).toUpperCase() || 'D';

    return (
        <DocsLink href={docsHomeHref(site)} className="flex min-w-0 items-center gap-3">
            <span className={`grid h-8 w-8 shrink-0 place-items-center overflow-hidden rounded-lg text-sm font-bold shadow-sm ${site.logoUrl ? 'border border-[var(--docs-border)] bg-[var(--docs-surface)] p-1' : 'bg-[var(--docs-brand)] text-[var(--docs-brand-text)]'}`}>
                {site.logoUrl ? <img src={site.logoUrl} alt="" className="h-full w-full object-contain" /> : brandInitial}
            </span>
            <span className="min-w-0">
                <span className="block truncate text-sm font-semibold text-[var(--docs-text)]">{site.brandName}</span>
                {site.tagline ? <span className="hidden truncate text-xs text-[var(--docs-muted)] sm:block">{site.tagline}</span> : null}
            </span>
        </DocsLink>
    );
}

function DocsSidebar({
    groups,
    site,
    currentPath,
    query,
    onQueryChange,
}: {
    groups: NavigationGroup[];
    site: DocsSite;
    currentPath: string;
    query: string;
    onQueryChange: (query: string) => void;
}) {
    const hasResults = groups.some((group) => group.nodes.length > 0);

    return (
        <div className="flex h-full flex-col">
            <div className="border-b border-[var(--docs-border)] px-5 py-4">
                <label className="relative block">
                    <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-[var(--docs-faint)]" />
                    <input
                        type="search"
                        value={query}
                        onChange={(event) => onQueryChange(event.target.value)}
                        placeholder="Search docs"
                        className="h-10 w-full rounded-lg border border-[var(--docs-border)] bg-[var(--docs-surface-muted)] pr-3 pl-9 text-sm text-[var(--docs-text)] outline-none transition placeholder:text-[var(--docs-faint)] focus:border-[var(--docs-accent)] focus:bg-[var(--docs-surface)] focus:ring-4 focus:ring-[var(--docs-accent-ring)]"
                    />
                </label>
            </div>

            <nav className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 py-5">
                {hasResults ? (
                    groups.map((group) => (
                        <section key={group.label} className="space-y-2.5">
                            {group.label ? <h2 className="px-2.5 text-xs font-semibold tracking-[0.12em] text-[var(--docs-faint)] uppercase">{group.label}</h2> : null}
                            <NavigationTree nodes={group.nodes} site={site} currentPath={currentPath} />
                        </section>
                    ))
                ) : (
                    <div className="rounded-lg border border-dashed border-[var(--docs-border)] bg-[var(--docs-surface-muted)] px-4 py-5 text-sm text-[var(--docs-muted)]">
                        No matching pages.
                    </div>
                )}
            </nav>
            <PlatformBrandingBadge site={site} className="mx-5 mb-5" />
        </div>
    );
}

function MintlifyTheme({
    site,
    release,
    page,
    previousPage,
    nextPage,
    theme,
    rootStyle,
    filteredNavigation,
    navigationQuery,
    setNavigationQuery,
    headings,
    publishedDate,
    publishedDateTime,
}: DocsThemeProps) {
    const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
    const isFullWidth = site.docsThemeOptions?.layoutWidth === 'full';
    const headingIds = new Map(headings.map((heading) => [heading.blockKey, heading.id]));

    return (
        <div className="min-h-screen bg-[var(--docs-bg)] text-[var(--docs-text)]" data-docs-theme={theme.id} style={rootStyle}>
            <header className="sticky top-0 z-40 border-b border-[var(--docs-border)] bg-[var(--docs-header)] backdrop-blur-xl">
                <div className={`mx-auto flex h-16 items-center gap-4 px-4 sm:px-6 lg:px-8 ${isFullWidth ? 'max-w-none' : 'max-w-[1440px]'}`}>
                    <button
                        type="button"
                        className="inline-grid h-9 w-9 place-items-center rounded-lg border border-[var(--docs-border)] text-[var(--docs-muted)] transition hover:bg-[var(--docs-surface-muted)] md:hidden"
                        onClick={() => setIsMobileNavOpen(true)}
                        aria-label="Open documentation navigation"
                    >
                        <Menu className="h-4 w-4" />
                    </button>

                    <div className="w-full max-w-[260px] shrink-0">
                        <DocsBrand site={site} />
                    </div>

                    <div className="ml-auto flex items-center gap-3 text-sm">
                        <span className="hidden rounded-full border border-[var(--docs-border)] bg-[var(--docs-surface-muted)] px-3 py-1 text-[var(--docs-muted)] sm:inline-flex">
                            {release.version}
                        </span>
                        {publishedDate ? <span className="hidden text-[var(--docs-muted)] md:inline">Updated {publishedDate}</span> : null}
                        <span className="rounded-full bg-[var(--docs-accent-soft)] px-3 py-1 text-xs font-semibold text-[var(--docs-accent-text)] ring-1 ring-[var(--docs-accent-ring)]">
                            {release.environment}
                        </span>
                    </div>
                </div>
            </header>

            {isMobileNavOpen ? (
                <div className="fixed inset-0 z-50 md:hidden">
                    <button
                        type="button"
                        className="absolute inset-0 bg-slate-950/30"
                        onClick={() => setIsMobileNavOpen(false)}
                        aria-label="Close documentation navigation"
                    />
                    <aside className="relative flex h-full w-[min(86vw,340px)] flex-col border-r border-[var(--docs-border)] bg-[var(--docs-surface)] shadow-2xl">
                        <div className="flex h-16 items-center justify-between border-b border-[var(--docs-border)] px-5">
                            <DocsBrand site={site} />
                            <button
                                type="button"
                                className="inline-grid h-9 w-9 place-items-center rounded-lg border border-[var(--docs-border)] text-[var(--docs-muted)] transition hover:bg-[var(--docs-surface-muted)]"
                                onClick={() => setIsMobileNavOpen(false)}
                                aria-label="Close documentation navigation"
                            >
                                <X className="h-4 w-4" />
                            </button>
                        </div>
                        <DocsSidebar
                            groups={filteredNavigation}
                            site={site}
                            currentPath={page.path}
                            query={navigationQuery}
                            onQueryChange={setNavigationQuery}
                        />
                    </aside>
                </div>
            ) : null}

            <div className={`mx-auto grid md:grid-cols-[280px_minmax(0,1fr)] ${isFullWidth ? 'max-w-none' : 'max-w-[1440px]'}`}>
                <aside className="sticky top-16 hidden h-[calc(100vh-4rem)] border-r border-[var(--docs-border)] bg-[var(--docs-surface)] md:block">
                    <DocsSidebar
                        groups={filteredNavigation}
                        site={site}
                        currentPath={page.path}
                        query={navigationQuery}
                        onQueryChange={setNavigationQuery}
                    />
                </aside>

                <main className="min-w-0">
                    <div className={`mx-auto grid grid-cols-1 gap-12 px-5 py-10 sm:px-8 md:px-10 xl:gap-16 xl:px-14 ${isFullWidth ? 'max-w-none xl:grid-cols-[minmax(0,1fr)_260px]' : 'max-w-[1180px] xl:grid-cols-[minmax(0,760px)_220px]'}`}>
                        <article className="min-w-0 pb-16">
                            <div className="mb-8 flex flex-wrap items-center gap-2 text-sm text-[var(--docs-muted)]">
                                <BookOpen className="h-4 w-4 text-[var(--docs-faint)]" />
                                <span>{page.spaceName ?? site.brandName}</span>
                                <ChevronRight className="h-3.5 w-3.5 text-[var(--docs-faint)]" />
                                <span className="truncate text-[var(--docs-text)]">{page.title}</span>
                            </div>

                            <header className="mb-10 border-b border-[var(--docs-border)] pb-10">
                                <div className="mb-4 inline-flex items-center rounded-full bg-[var(--docs-accent-soft)] px-3 py-1 text-xs font-semibold text-[var(--docs-accent-text)] ring-1 ring-[var(--docs-accent-ring)]">
                                    {page.spaceName ?? site.brandName} / {release.environment}
                                </div>
                                <h1 className="max-w-3xl text-4xl font-bold text-[var(--docs-text)] sm:text-5xl">
                                    {page.title}
                                </h1>
                                {page.subtitle ? <p className="mt-5 max-w-2xl text-lg leading-8 text-[var(--docs-muted)]">{page.subtitle}</p> : null}
                            </header>

                            <div className="space-y-7">
                                {page.blocks.map((block, index) => {
                                    const blockKey = docsBlockKey(block, index);
                                    const headingId = block.kind === 'h2' || block.kind === 'h3'
                                        ? (headingIds.get(blockKey) ?? null)
                                        : null;

                                    return (
                                        <section key={blockKey} id={headingId ?? undefined} className="scroll-mt-28 space-y-4">
                                            <BlockRenderer block={block} />
                                        </section>
                                    );
                                })}
                            </div>

                            <div className="mt-14 grid gap-4 border-t border-[var(--docs-border)] pt-8 sm:grid-cols-2">
                                {previousPage ? (
                                    <DocsLink href={docsHref(site, previousPage.path)} className="group rounded-lg border border-[var(--docs-border)] bg-[var(--docs-surface)] px-5 py-4 transition hover:border-[var(--docs-accent-ring)] hover:shadow-sm">
                                        <div className="flex items-center gap-2 text-sm font-medium text-[var(--docs-muted)]">
                                            <ChevronLeft className="h-4 w-4" />
                                            Previous
                                        </div>
                                        <div className="mt-2 text-base font-semibold text-[var(--docs-text)] group-hover:text-[var(--docs-accent-text)]">{previousPage.title}</div>
                                    </DocsLink>
                                ) : <div />}
                                {nextPage ? (
                                    <DocsLink href={docsHref(site, nextPage.path)} className="group rounded-lg border border-[var(--docs-border)] bg-[var(--docs-surface)] px-5 py-4 text-right transition hover:border-[var(--docs-accent-ring)] hover:shadow-sm">
                                        <div className="flex items-center justify-end gap-2 text-sm font-medium text-[var(--docs-muted)]">
                                            Next
                                            <ChevronRight className="h-4 w-4" />
                                        </div>
                                        <div className="mt-2 text-base font-semibold text-[var(--docs-text)] group-hover:text-[var(--docs-accent-text)]">{nextPage.title}</div>
                                    </DocsLink>
                                ) : null}
                            </div>
                        </article>

                        <aside className="hidden xl:block">
                            <div className="sticky top-24 max-h-[calc(100vh-7rem)] overflow-y-auto border-l border-[var(--docs-border)] pl-6">
                                <div className="text-sm font-semibold text-[var(--docs-text)]">On this page</div>
                                <ul className="mt-4 space-y-2.5">
                                    {headings.length > 0 ? headings.map((heading) => (
                                        <li key={heading.id}>
                                            <a href={`#${heading.id}`} className={`block text-sm leading-6 text-[var(--docs-muted)] transition hover:text-[var(--docs-text)] ${heading.level === 'h3' ? 'pl-4' : ''}`}>
                                                {heading.label}
                                            </a>
                                        </li>
                                    )) : <li className="text-sm text-[var(--docs-muted)]">No sections yet.</li>}
                                </ul>

                                <div className="mt-8 border-t border-[var(--docs-border)] pt-6 text-sm text-[var(--docs-muted)]">
                                    <div className="font-medium text-[var(--docs-text)]">Release</div>
                                    <div className="mt-2 inline-flex rounded-md border border-[var(--docs-border)] bg-[var(--docs-surface-muted)] px-2.5 py-1 font-medium text-[var(--docs-text)]">{release.version}</div>
                                    {publishedDateTime ? <p className="mt-3 leading-6">Published {publishedDateTime}</p> : null}
                                </div>
                            </div>
                        </aside>
                    </div>
                </main>
            </div>
        </div>
    );
}

export const mintlifyTheme: DocsThemeDefinition = {
    id: 'mintlify',
    name: 'Mintlify',
    description: 'Modern product docs with a centered content column, clean rails, and emerald accents.',
    swatches: ['#ffffff', '#f8fafc', '#059669'],
    styles: {
        '--docs-bg': '#ffffff',
        '--docs-header': 'rgba(255, 255, 255, 0.92)',
        '--docs-surface': '#ffffff',
        '--docs-surface-muted': '#f8fafc',
        '--docs-border': '#e2e8f0',
        '--docs-text': '#0f172a',
        '--docs-muted': '#64748b',
        '--docs-faint': '#94a3b8',
        '--docs-accent': '#059669',
        '--docs-accent-soft': '#ecfdf5',
        '--docs-accent-text': '#047857',
        '--docs-accent-ring': '#a7f3d0',
        '--docs-brand': '#0f172a',
        '--docs-brand-text': '#ffffff',
        '--docs-code-bg': '#0b1020',
        '--docs-code-text': '#f8fafc',
    },
    component: MintlifyTheme,
};

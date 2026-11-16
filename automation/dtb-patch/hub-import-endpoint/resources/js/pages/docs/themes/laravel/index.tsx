import { ChevronLeft, ChevronRight, List, Menu, Monitor, Search, X } from 'lucide-react';
import { useState } from 'react';
import { BlockRenderer, DocsLink, PlatformBrandingBadge, docsBlockKey, docsHomeHref, docsHref } from '../shared';
import type { DocsNavigationNode, DocsSite, DocsThemeDefinition, DocsThemeProps, NavigationGroup } from '../types';

// ─── Navigation tree ──────────────────────────────────────────────────────────

function NavTree({
    nodes,
    site,
    currentPath,
    depth = 0,
}: {
    nodes: DocsNavigationNode[];
    site: DocsSite;
    currentPath: string;
    depth?: number;
}) {
    return (
        <ul className={depth > 0 ? 'ml-3 border-l border-[var(--docs-border)] pl-3' : ''}>
            {nodes.map((node) => {
                const isActive = node.path === currentPath;

                return (
                    <li key={node.path}>
                        <DocsLink
                            href={docsHref(site, node.path)}
                            className={`block truncate py-1 text-sm leading-6 transition ${
                                isActive
                                    ? 'font-medium text-[var(--docs-accent)]'
                                    : 'text-[var(--docs-muted)] hover:text-[var(--docs-text)]'
                            }`}
                        >
                            {node.title}
                        </DocsLink>
                        {node.children.length > 0 && (
                            <NavTree nodes={node.children} site={site} currentPath={currentPath} depth={depth + 1} />
                        )}
                    </li>
                );
            })}
        </ul>
    );
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

function Sidebar({
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
    onQueryChange: (q: string) => void;
}) {
    const hasResults = groups.some((g) => g.nodes.length > 0);

    return (
        <div className="flex h-full flex-col overflow-y-auto">
            {/* Search */}
            <div className="px-4 pt-5 pb-4">
                <label className="relative block">
                    <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-[var(--docs-faint)]" />
                    <input
                        type="search"
                        value={query}
                        onChange={(e) => onQueryChange(e.target.value)}
                        placeholder="Search"
                        className="h-9 w-full rounded-md border border-[var(--docs-border)] bg-[var(--docs-surface-muted)] pr-3 pl-9 text-sm text-[var(--docs-text)] outline-none transition placeholder:text-[var(--docs-faint)] focus:border-[var(--docs-accent)] focus:ring-2 focus:ring-[var(--docs-accent-ring)]"
                    />
                    <kbd className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 hidden rounded border border-[var(--docs-border)] bg-[var(--docs-surface-muted)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--docs-faint)] sm:inline-flex">
                        ⌘K
                    </kbd>
                </label>
            </div>

            {/* Nav groups */}
            <nav className="flex-1 space-y-5 px-4 pb-6">
                {hasResults ? groups.map((group) => (
                    <section key={group.label}>
                        {group.label ? (
                            <h2 className="mb-2 text-xs font-bold tracking-wider text-[var(--docs-text)] uppercase">
                                {group.label}
                            </h2>
                        ) : null}
                        <NavTree nodes={group.nodes} site={site} currentPath={currentPath} />
                    </section>
                )) : (
                    <p className="text-sm text-[var(--docs-muted)]">No matching pages.</p>
                )}
            </nav>

            <PlatformBrandingBadge site={site} className="mx-4 mb-5" />
        </div>
    );
}

// ─── Brand ────────────────────────────────────────────────────────────────────

function Brand({ site }: { site: DocsSite }) {
    const initial = (site.brandName || site.name || 'D').trim().charAt(0).toUpperCase();

    return (
        <DocsLink href={docsHomeHref(site)} className="flex min-w-0 items-center gap-2.5">
            <span className={`grid h-7 w-7 shrink-0 place-items-center overflow-hidden rounded-md text-[13px] font-bold ${site.logoUrl ? 'border border-[var(--docs-border)] bg-[var(--docs-surface)] p-0.5' : 'bg-[var(--docs-accent)] text-white'}`}>
                {site.logoUrl ? <img src={site.logoUrl} alt="" className="h-full w-full object-contain" /> : initial}
            </span>
            <span className="truncate text-sm font-semibold text-[var(--docs-text)]">{site.brandName}</span>
        </DocsLink>
    );
}

// ─── Main theme component ─────────────────────────────────────────────────────

function LaravelTheme({
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
}: DocsThemeProps) {
    const [mobileNavOpen, setMobileNavOpen] = useState(false);
    const isFullWidth = site.docsThemeOptions?.layoutWidth === 'full';
    const headingIds = new Map(headings.map((heading) => [heading.blockKey, heading.id]));

    return (
        <div
            className="min-h-screen bg-[var(--docs-bg)] text-[var(--docs-text)]"
            data-docs-theme={theme.id}
            style={rootStyle}
        >
            {/* ── Top navigation bar ── */}
            <header className="sticky top-0 z-40 border-b border-[var(--docs-border)] bg-[var(--docs-header)]">
                <div className={`mx-auto flex h-14 items-center gap-4 px-4 sm:px-6 ${isFullWidth ? 'max-w-none' : 'max-w-screen-xl'}`}>
                    {/* Mobile hamburger */}
                    <button
                        type="button"
                        className="inline-grid h-8 w-8 place-items-center rounded text-[var(--docs-muted)] transition hover:bg-[var(--docs-surface-muted)] lg:hidden"
                        onClick={() => setMobileNavOpen(true)}
                        aria-label="Open navigation"
                    >
                        <Menu className="h-4 w-4" />
                    </button>

                    {/* Brand */}
                    <div className="shrink-0">
                        <Brand site={site} />
                    </div>

                    <div className="ml-auto flex items-center gap-3">
                        {/* Version badge */}
                        <div className="flex items-center gap-1 rounded-md border border-[var(--docs-border)] bg-[var(--docs-surface-muted)] px-2.5 py-1 text-xs font-medium text-[var(--docs-muted)]">
                            {release.version}
                            <ChevronRight className="h-3 w-3 rotate-90" />
                        </div>
                        <Monitor className="h-4 w-4 hidden text-[var(--docs-faint)] sm:block" />
                    </div>
                </div>
            </header>

            {/* ── Mobile nav overlay ── */}
            {mobileNavOpen && (
                <div className="fixed inset-0 z-50 lg:hidden">
                    <button
                        type="button"
                        className="absolute inset-0 bg-black/30"
                        onClick={() => setMobileNavOpen(false)}
                        aria-label="Close navigation"
                    />
                    <aside className="relative flex h-full w-[min(86vw,300px)] flex-col border-r border-[var(--docs-border)] bg-[var(--docs-surface)]">
                        <div className="flex h-14 items-center justify-between border-b border-[var(--docs-border)] px-4">
                            <Brand site={site} />
                            <button
                                type="button"
                                className="inline-grid h-8 w-8 place-items-center rounded text-[var(--docs-muted)] hover:bg-[var(--docs-surface-muted)]"
                                onClick={() => setMobileNavOpen(false)}
                                aria-label="Close navigation"
                            >
                                <X className="h-4 w-4" />
                            </button>
                        </div>
                        <Sidebar
                            groups={filteredNavigation}
                            site={site}
                            currentPath={page.path}
                            query={navigationQuery}
                            onQueryChange={setNavigationQuery}
                        />
                    </aside>
                </div>
            )}

            {/* ── Body: sidebar + content + toc ── */}
            <div className={`mx-auto flex ${isFullWidth ? 'max-w-none' : 'max-w-screen-xl'}`}>
                {/* Left sidebar */}
                <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-64 shrink-0 border-r border-[var(--docs-border)] bg-[var(--docs-surface)] overflow-y-auto lg:block">
                    <Sidebar
                        groups={filteredNavigation}
                        site={site}
                        currentPath={page.path}
                        query={navigationQuery}
                        onQueryChange={setNavigationQuery}
                    />
                </aside>

                {/* Main content */}
                <main className="min-w-0 flex-1">
                    <div className={`mx-auto grid grid-cols-1 gap-10 px-6 py-10 sm:px-8 md:px-10 ${isFullWidth ? 'max-w-none xl:grid-cols-[minmax(0,1fr)_240px]' : 'max-w-4xl xl:grid-cols-[minmax(0,1fr)_220px]'}`}>
                        {/* Article */}
                        <article className="min-w-0 pb-16">
                            <h1 className="mb-4 text-4xl font-bold tracking-tight text-[var(--docs-text)]">
                                {page.title}
                            </h1>
                            {page.subtitle ? (
                                <p className="mb-8 text-lg text-[var(--docs-muted)]">{page.subtitle}</p>
                            ) : null}

                            <div className="prose-laravel space-y-6">
                                {page.blocks.map((block, index) => {
                                    const blockKey = docsBlockKey(block, index);
                                    const headingId = block.kind === 'h2' || block.kind === 'h3'
                                        ? (headingIds.get(blockKey) ?? null)
                                        : null;

                                    return (
                                        <section
                                            key={blockKey}
                                            id={headingId ?? undefined}
                                            className="scroll-mt-20"
                                        >
                                            <BlockRenderer block={block} />
                                        </section>
                                    );
                                })}
                            </div>

                            {/* Prev / Next navigation */}
                            <div className="mt-12 grid gap-4 border-t border-[var(--docs-border)] pt-8 sm:grid-cols-2">
                                {previousPage ? (
                                    <DocsLink
                                        href={docsHref(site, previousPage.path)}
                                        className="group flex items-center gap-3 rounded-lg border border-[var(--docs-border)] px-4 py-3 text-sm transition hover:border-[var(--docs-accent)] hover:bg-[var(--docs-surface-muted)]"
                                    >
                                        <ChevronLeft className="h-4 w-4 text-[var(--docs-faint)] transition group-hover:text-[var(--docs-accent)]" />
                                        <div>
                                            <div className="text-xs text-[var(--docs-muted)]">Previous</div>
                                            <div className="font-medium text-[var(--docs-text)] group-hover:text-[var(--docs-accent)]">{previousPage.title}</div>
                                        </div>
                                    </DocsLink>
                                ) : <div />}
                                {nextPage ? (
                                    <DocsLink
                                        href={docsHref(site, nextPage.path)}
                                        className="group flex items-center justify-end gap-3 rounded-lg border border-[var(--docs-border)] px-4 py-3 text-sm text-right transition hover:border-[var(--docs-accent)] hover:bg-[var(--docs-surface-muted)]"
                                    >
                                        <div>
                                            <div className="text-xs text-[var(--docs-muted)]">Next</div>
                                            <div className="font-medium text-[var(--docs-text)] group-hover:text-[var(--docs-accent)]">{nextPage.title}</div>
                                        </div>
                                        <ChevronRight className="h-4 w-4 text-[var(--docs-faint)] transition group-hover:text-[var(--docs-accent)]" />
                                    </DocsLink>
                                ) : null}
                            </div>

                            {publishedDate ? (
                                <p className="mt-6 text-xs text-[var(--docs-faint)]">Updated {publishedDate}</p>
                            ) : null}
                        </article>

                        {/* Right TOC */}
                        <aside className="hidden xl:block">
                            <div className="sticky top-20">
                                <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--docs-muted)]">
                                    <List className="h-3.5 w-3.5" />
                                    On this page
                                </div>
                                <ul className="space-y-2">
                                    {headings.length > 0 ? headings.map((heading) => (
                                        <li key={heading.id}>
                                            <a
                                                href={`#${heading.id}`}
                                                className={`block text-sm leading-6 text-[var(--docs-muted)] transition hover:text-[var(--docs-accent)] ${heading.level === 'h3' ? 'pl-4' : ''}`}
                                            >
                                                {heading.label}
                                            </a>
                                        </li>
                                    )) : (
                                        <li className="text-sm text-[var(--docs-faint)]">No sections.</li>
                                    )}
                                </ul>
                            </div>
                        </aside>
                    </div>
                </main>
            </div>
        </div>
    );
}

// ─── Theme export ─────────────────────────────────────────────────────────────

export const laravelTheme: DocsThemeDefinition = {
    id: 'laravel',
    name: 'Laravel',
    description: 'Classic Laravel-docs layout with a left chapter rail, inline search, right TOC, and signature red accents.',
    swatches: ['#ffffff', '#f9f9f9', '#FF2D20'],
    styles: {
        '--docs-bg': '#ffffff',
        '--docs-header': 'rgba(255, 255, 255, 0.95)',
        '--docs-surface': '#ffffff',
        '--docs-surface-muted': '#f9f9f9',
        '--docs-border': '#e5e7eb',
        '--docs-text': '#111827',
        '--docs-muted': '#6b7280',
        '--docs-faint': '#9ca3af',
        '--docs-accent': '#FF2D20',
        '--docs-accent-soft': '#fff1f0',
        '--docs-accent-text': '#b91c1c',
        '--docs-accent-ring': '#fecaca',
        '--docs-brand': '#FF2D20',
        '--docs-brand-text': '#ffffff',
        '--docs-code-bg': '#1e1e2e',
        '--docs-code-text': '#f8f8f2',
    },
    component: LaravelTheme,
};

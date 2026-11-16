import { ChevronLeft, ChevronRight, Copy, FileText, Menu, PanelLeft, Search, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { BlockRenderer, DocsLink, PlatformBrandingBadge, copyCurrentPage, docsBlockKey, docsHomeHref, docsHref } from '../shared';
import type { DocsNavigationNode, DocsSite, DocsThemeDefinition, DocsThemeProps, NavigationGroup } from '../types';

function Brand({ site }: { site: DocsSite }) {
    return (
        <DocsLink href={docsHomeHref(site)} className="flex min-w-0 items-center gap-2.5">
            {site.logoUrl ? (
                <img src={site.logoUrl} alt="" className="h-7 w-7 shrink-0 rounded-md border border-[var(--docs-border)] bg-[var(--docs-surface)] object-contain p-1 shadow-sm" />
            ) : (
                <span className="h-4 w-4 shrink-0 rounded-full bg-[linear-gradient(135deg,var(--docs-accent)_0%,var(--docs-accent-ring)_100%)] shadow-sm" />
            )}
            <span className="truncate text-sm font-semibold text-[var(--docs-text)]">{site.brandName}</span>
        </DocsLink>
    );
}

function hasPath(nodes: DocsNavigationNode[], targetPath: string): boolean {
    return nodes.some((node) => node.path === targetPath || hasPath(node.children, targetPath));
}

function NavigationNode({ node, site, currentPath }: { node: DocsNavigationNode; site: DocsSite; currentPath: string }) {
    const isActive = node.path === currentPath;
    const hasChildren = node.children.length > 0;
    const shouldStartExpanded = isActive || hasPath(node.children, currentPath);
    const [isExpanded, setIsExpanded] = useState(shouldStartExpanded);

    useEffect(() => {
        if (shouldStartExpanded) {
            setIsExpanded(true);
        }
    }, [shouldStartExpanded]);

    const expandIconClass = useMemo(
        () => `ml-auto h-3.5 w-3.5 text-[var(--docs-faint)] transition-transform ${isExpanded ? 'rotate-90' : ''}`,
        [isExpanded],
    );

    return (
        <li>
            <div className="flex items-center gap-1">
                {hasChildren ? (
                    <button
                        type="button"
                        onClick={() => setIsExpanded((value) => !value)}
                        className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-[var(--docs-faint)] transition hover:bg-[var(--docs-surface-muted)] hover:text-[var(--docs-text)]"
                        aria-label={isExpanded ? `Collapse ${node.title}` : `Expand ${node.title}`}
                        aria-expanded={isExpanded}
                    >
                        <ChevronRight className={expandIconClass} />
                    </button>
                ) : <span className="h-7 w-7 shrink-0" />}

                <DocsLink
                    href={docsHref(site, node.path)}
                    className={`min-w-0 flex-1 rounded-md px-2.5 py-2 text-sm transition ${
                        isActive
                            ? 'bg-[var(--docs-accent-soft)] font-medium text-[var(--docs-accent-text)]'
                            : 'text-[var(--docs-muted)] hover:bg-[var(--docs-surface-muted)] hover:text-[var(--docs-text)]'
                    }`}
                >
                    <span className="flex items-center gap-2">
                        <FileText className={`h-4 w-4 shrink-0 ${isActive ? 'text-[var(--docs-accent)]' : 'text-[var(--docs-faint)]'}`} />
                        <span className="truncate">{node.title}</span>
                    </span>
                </DocsLink>
            </div>

            {hasChildren && isExpanded ? (
                <div className="mt-1 ml-8 border-l border-[var(--docs-border)] pl-2">
                    <NavigationTree nodes={node.children} site={site} currentPath={currentPath} />
                </div>
            ) : null}
        </li>
    );
}

function NavigationTree({ nodes, site, currentPath }: { nodes: DocsNavigationNode[]; site: DocsSite; currentPath: string }) {
    return (
        <ul className="space-y-1">
            {nodes.map((node) => (
                <NavigationNode key={node.path} node={node} site={site} currentPath={currentPath} />
            ))}
        </ul>
    );
}

function Sidebar({
    groups,
    site,
    currentPath,
    query,
    onQueryChange,
    currentSection,
    releaseVersion,
}: {
    groups: NavigationGroup[];
    site: DocsSite;
    currentPath: string;
    query: string;
    onQueryChange: (query: string) => void;
    currentSection: string;
    releaseVersion: string;
}) {
    return (
        <div className="flex h-full flex-col bg-[var(--docs-sidebar)]">
            <div className="flex h-14 items-center justify-between border-b border-[var(--docs-border)] px-4">
                <Brand site={site} />
                <PanelLeft className="h-4 w-4 text-[var(--docs-muted)]" />
            </div>

            <div className="space-y-3 border-b border-[var(--docs-border)] p-4">
                <label className="relative block">
                    <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-[var(--docs-faint)]" />
                    <input
                        type="search"
                        value={query}
                        onChange={(event) => onQueryChange(event.target.value)}
                        placeholder="Search"
                        className="h-9 w-full rounded-md border border-[var(--docs-border)] bg-[var(--docs-surface)] pr-16 pl-9 text-sm text-[var(--docs-text)] outline-none transition placeholder:text-[var(--docs-faint)] focus:border-[var(--docs-accent)] focus:ring-2 focus:ring-[var(--docs-accent-ring)]"
                    />
                    <span className="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 rounded border border-[var(--docs-border)] px-1.5 py-0.5 font-mono text-xs text-[var(--docs-muted)]">Ctrl K</span>
                </label>

                <div className="rounded-md border border-[var(--docs-border)] bg-[var(--docs-surface-muted)] px-3 py-2.5 text-sm text-[var(--docs-text)]">
                    <div className="font-medium">{currentSection}</div>
                    <div className="mt-1 text-xs text-[var(--docs-muted)]">Release {releaseVersion}</div>
                </div>
            </div>

            <nav className="min-h-0 flex-1 overflow-y-auto px-4 py-5">
                {groups.length ? groups.map((group) => (
                    <section key={group.label} className="mb-7">
                        {group.label ? <h2 className="mb-2 px-2.5 text-[13px] font-medium text-[var(--docs-text)]">{group.label}</h2> : null}
                        <NavigationTree nodes={group.nodes} site={site} currentPath={currentPath} />
                    </section>
                )) : (
                    <div className="rounded-md border border-dashed border-[var(--docs-border)] bg-[var(--docs-surface)] px-4 py-5 text-sm text-[var(--docs-muted)]">
                        No matching pages.
                    </div>
                )}
            </nav>
            <PlatformBrandingBadge site={site} className="mx-4 mb-4" />
        </div>
    );
}

function FumadocsTheme({
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
}: DocsThemeProps) {
    const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
    const isFullWidth = site.docsThemeOptions?.layoutWidth === 'full';
    const headingIds = new Map(headings.map((heading) => [heading.blockKey, heading.id]));

    return (
        <div className="min-h-screen bg-[var(--docs-bg)] text-[var(--docs-text)]" data-docs-theme={theme.id} style={rootStyle}>
            <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-[var(--docs-border)] bg-[var(--docs-header)] px-4 backdrop-blur-xl lg:hidden">
                <button type="button" className="grid h-9 w-9 place-items-center rounded-md border border-[var(--docs-border)] text-[var(--docs-muted)]" onClick={() => setIsMobileNavOpen(true)} aria-label="Open documentation navigation">
                    <Menu className="h-4 w-4" />
                </button>
                <Brand site={site} />
                <span className="h-9 w-9" />
            </header>

            {isMobileNavOpen ? (
                <div className="fixed inset-0 z-50 lg:hidden">
                    <button type="button" className="absolute inset-0 bg-black/30" onClick={() => setIsMobileNavOpen(false)} aria-label="Close documentation navigation" />
                    <aside className="relative h-full w-[min(88vw,320px)] border-r border-[var(--docs-border)] shadow-2xl">
                        <button type="button" className="absolute top-2 right-2 z-10 grid h-9 w-9 place-items-center rounded-md border border-[var(--docs-border)] bg-[var(--docs-surface)] text-[var(--docs-muted)]" onClick={() => setIsMobileNavOpen(false)} aria-label="Close documentation navigation">
                            <X className="h-4 w-4" />
                        </button>
                        <Sidebar groups={filteredNavigation} site={site} currentPath={page.path} query={navigationQuery} onQueryChange={setNavigationQuery} currentSection={page.spaceName ?? site.brandName} releaseVersion={release.version} />
                    </aside>
                </div>
            ) : null}

            <div className={`mx-auto grid lg:grid-cols-[268px_minmax(0,1fr)] ${isFullWidth ? 'max-w-none xl:grid-cols-[268px_minmax(0,1fr)_280px]' : 'max-w-[1440px] xl:grid-cols-[268px_minmax(0,820px)_260px]'}`}>
                <aside className="sticky top-0 hidden h-screen border-r border-[var(--docs-border)] lg:block">
                    <Sidebar groups={filteredNavigation} site={site} currentPath={page.path} query={navigationQuery} onQueryChange={setNavigationQuery} currentSection={page.spaceName ?? site.brandName} releaseVersion={release.version} />
                </aside>

                <main className="min-w-0 px-6 py-10 sm:px-8 lg:px-10 xl:px-14">
                    <article className={`mx-auto pb-20 ${isFullWidth ? 'max-w-none' : 'max-w-[780px]'}`}>
                        <header className="mb-9 border-b border-[var(--docs-border)] pb-7">
                            <div className="mb-4 text-sm font-medium text-[var(--docs-accent-text)]">{page.spaceName ?? site.brandName}</div>
                            <div className="flex flex-wrap items-start justify-between gap-4">
                                <div className="min-w-0">
                                    <h1 className="text-4xl font-semibold tracking-tight text-[var(--docs-text)] sm:text-5xl">{page.title}</h1>
                                    {page.subtitle ? <p className="mt-4 text-lg leading-8 text-[var(--docs-muted)]">{page.subtitle}</p> : null}
                                </div>
                                <div className="flex shrink-0 items-center gap-2">
                                    <button type="button" onClick={copyCurrentPage} className="inline-flex h-9 items-center gap-2 rounded-md border border-[var(--docs-border)] bg-[var(--docs-surface-muted)] px-3 text-sm font-medium text-[var(--docs-text)] transition hover:bg-[var(--docs-surface)]">
                                        <Copy className="h-4 w-4" /> Copy link
                                    </button>
                                </div>
                            </div>
                        </header>

                        <div className="mb-8 flex flex-wrap items-center gap-2 text-sm text-[var(--docs-muted)]">
                            <span className="rounded-md border border-[var(--docs-border)] bg-[var(--docs-surface-muted)] px-2.5 py-1 font-medium">{release.version}</span>
                            <span className="rounded-md bg-[var(--docs-accent-soft)] px-2.5 py-1 font-medium text-[var(--docs-accent-text)]">{release.environment}</span>
                        </div>

                        <div className="space-y-7">
                            {page.blocks.map((block, index) => {
                                const blockKey = docsBlockKey(block, index);
                                const headingId = block.kind === 'h2' || block.kind === 'h3'
                                    ? (headingIds.get(blockKey) ?? null)
                                    : null;

                                return (
                                    <section key={blockKey} id={headingId ?? undefined} className="scroll-mt-16 space-y-4">
                                        <BlockRenderer block={block} />
                                    </section>
                                );
                            })}
                        </div>

                        <div className="mt-14 grid gap-4 border-t border-[var(--docs-border)] pt-8 sm:grid-cols-2">
                            {previousPage ? (
                                <DocsLink href={docsHref(site, previousPage.path)} className="rounded-md border border-[var(--docs-border)] bg-[var(--docs-surface)] p-4 transition hover:border-[var(--docs-accent)] hover:bg-[var(--docs-surface-muted)]">
                                    <span className="flex items-center gap-2 text-sm text-[var(--docs-muted)]"><ChevronLeft className="h-4 w-4" /> Previous</span>
                                    <strong className="mt-2 block text-[var(--docs-text)]">{previousPage.title}</strong>
                                </DocsLink>
                            ) : <div />}
                            {nextPage ? (
                                <DocsLink href={docsHref(site, nextPage.path)} className="rounded-md border border-[var(--docs-border)] bg-[var(--docs-surface)] p-4 text-right transition hover:border-[var(--docs-accent)] hover:bg-[var(--docs-surface-muted)]">
                                    <span className="flex items-center justify-end gap-2 text-sm text-[var(--docs-muted)]">Next <ChevronRight className="h-4 w-4" /></span>
                                    <strong className="mt-2 block text-[var(--docs-text)]">{nextPage.title}</strong>
                                </DocsLink>
                            ) : null}
                        </div>
                    </article>
                </main>

                <aside className="hidden xl:block">
                    <div className="sticky top-10 mx-6 max-h-[calc(100vh-5rem)] overflow-y-auto border-l border-[var(--docs-border)] pl-5">
                        <div className="mb-4 text-sm font-semibold text-[var(--docs-muted)]">On this page</div>
                        <ul className="space-y-2">
                            {headings.length ? headings.map((heading, index) => (
                                <li key={heading.id} className="relative">
                                    <span className={`absolute top-0 bottom-0 -left-5 w-px ${index === 0 ? 'bg-[var(--docs-accent)]' : 'bg-transparent'}`} />
                                    <a href={`#${heading.id}`} className={`block py-1 text-sm transition hover:text-[var(--docs-text)] ${index === 0 ? 'font-medium text-[var(--docs-accent-text)]' : 'text-[var(--docs-muted)]'} ${heading.level === 'h3' ? 'pl-4' : ''}`}>
                                        {heading.label}
                                    </a>
                                </li>
                            )) : <li className="text-sm text-[var(--docs-muted)]">No sections yet.</li>}
                        </ul>
                    </div>
                </aside>
            </div>
        </div>
    );
}

export const fumadocsTheme: DocsThemeDefinition = {
    id: 'fumadocs',
    name: 'Fumadocs',
    description: 'A compact framework-style reader with a fixed left workspace, neutral surfaces, and amber highlights.',
    swatches: ['#f7f7f6', '#ffffff', '#d28a00'],
    styles: {
        '--docs-bg': '#f7f7f6',
        '--docs-header': 'rgba(247, 247, 246, 0.94)',
        '--docs-sidebar': '#eeeeed',
        '--docs-surface': '#ffffff',
        '--docs-surface-muted': '#f2f2f1',
        '--docs-border': '#dededc',
        '--docs-text': '#050505',
        '--docs-muted': '#70706d',
        '--docs-faint': '#9a9a96',
        '--docs-accent': '#d28a00',
        '--docs-accent-soft': '#f2e8d5',
        '--docs-accent-text': '#b87500',
        '--docs-accent-ring': '#e8c67d',
        '--docs-brand': '#171717',
        '--docs-brand-text': '#ffffff',
        '--docs-code-bg': '#111111',
        '--docs-code-text': '#fbfaf7',
    },
    component: FumadocsTheme,
};

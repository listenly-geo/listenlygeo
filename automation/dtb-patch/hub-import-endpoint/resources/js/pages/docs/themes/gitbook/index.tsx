import { BookOpen, ChevronLeft, ChevronRight, CircleHelp, Clipboard, Menu, Search, X, Zap } from 'lucide-react';
import { useMemo, useState } from 'react';
import { BlockRenderer, DocsLink, PlatformBrandingBadge, copyCurrentPage, docsBlockKey, docsHomeHref, docsHref } from '../shared';
import type { DocsNavigationNode, DocsSite, DocsThemeDefinition, DocsThemeProps, NavigationGroup } from '../types';

function hasPath(nodes: DocsNavigationNode[], targetPath: string): boolean {
    return nodes.some((node) => node.path === targetPath || hasPath(node.children, targetPath));
}

function Brand({ site }: { site: DocsSite }) {
    return (
        <DocsLink href={docsHomeHref(site)} className="flex min-w-0 items-center gap-2.5 text-[var(--docs-text)]">
            <span className={`grid h-8 w-8 shrink-0 place-items-center overflow-hidden rounded-md ${site.logoUrl ? 'border border-[var(--docs-border)] bg-[var(--docs-surface)] p-1' : 'bg-[var(--docs-brand)] text-[var(--docs-brand-text)]'}`}>
                {site.logoUrl ? <img src={site.logoUrl} alt="" className="h-full w-full object-contain" /> : <BookOpen className="h-4 w-4" />}
            </span>
            <span className="truncate text-lg font-bold tracking-tight">{site.brandName}</span>
        </DocsLink>
    );
}

function NavigationTree({ nodes, site, currentPath }: { nodes: DocsNavigationNode[]; site: DocsSite; currentPath: string }) {
    return (
        <ul className="space-y-0.5">
            {nodes.map((node) => {
                const isActive = node.path === currentPath;
                const hasChildren = node.children.length > 0;

                return (
                    <li key={node.path}>
                        <DocsLink
                            href={docsHref(site, node.path)}
                            className={`group relative flex min-h-9 items-center gap-3 rounded-md px-3 py-2 text-sm transition ${
                                isActive
                                    ? 'bg-[var(--docs-accent-soft)] font-semibold text-[var(--docs-accent-text)] before:absolute before:top-1.5 before:bottom-1.5 before:left-0 before:w-0.5 before:rounded-full before:bg-[var(--docs-accent)]'
                                    : 'text-[var(--docs-muted)] hover:bg-[var(--docs-surface-muted)] hover:text-[var(--docs-text)]'
                            }`}
                        >
                            <Zap className={`h-4 w-4 shrink-0 ${isActive ? 'text-[var(--docs-accent)]' : 'text-[var(--docs-faint)]'}`} />
                            <span className="truncate">{node.title}</span>
                            {hasChildren ? <ChevronRight className="ml-auto h-3.5 w-3.5 text-[var(--docs-faint)]" /> : null}
                        </DocsLink>
                        {hasChildren ? (
                            <div className="mt-1 ml-5 border-l border-[var(--docs-border)] pl-2">
                                <NavigationTree nodes={node.children} site={site} currentPath={currentPath} />
                            </div>
                        ) : null}
                    </li>
                );
            })}
        </ul>
    );
}

function Sidebar({ groups, site, currentPath }: { groups: NavigationGroup[]; site: DocsSite; currentPath: string }) {
    return (
        <div className="flex h-full flex-col">
            <nav className="min-h-0 flex-1 overflow-y-auto px-5 py-7">
                {groups.length ? groups.map((group) => (
                    <section key={group.label} className="mb-8">
                        {group.label ? <h2 className="mb-3 px-3 text-xs font-bold tracking-[0.08em] text-[var(--docs-text)] uppercase">{group.label}</h2> : null}
                        <NavigationTree nodes={group.nodes} site={site} currentPath={currentPath} />
                    </section>
                )) : (
                    <div className="rounded-lg border border-dashed border-[var(--docs-border)] bg-[var(--docs-surface-muted)] px-4 py-5 text-sm text-[var(--docs-muted)]">
                        No matching pages.
                    </div>
                )}
            </nav>
            <PlatformBrandingBadge site={site} className="mx-5 mb-5" />
        </div>
    );
}

function GitBookTheme({
    site,
    release,
    page,
    previousPage,
    nextPage,
    theme,
    rootStyle,
    groupedNavigation,
    filteredNavigation,
    navigationQuery,
    setNavigationQuery,
    headings,
    publishedDate,
}: DocsThemeProps) {
    const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
    const isFullWidth = site.docsThemeOptions?.layoutWidth === 'full';
    const sectionTabs = useMemo(
        () => groupedNavigation
            .filter((group) => group.nodes.length > 0)
            .map((group) => ({
                label: group.label,
                path: group.nodes[0].path,
                isActive: hasPath(group.nodes, page.path),
            })),
        [groupedNavigation, page.path],
    );
    const headingIds = new Map(headings.map((heading) => [heading.blockKey, heading.id]));

    return (
        <div className="min-h-screen bg-[var(--docs-bg)] text-[var(--docs-text)]" data-docs-theme={theme.id} style={rootStyle}>
            <header className="sticky top-0 z-40 border-b border-[var(--docs-border)] bg-[var(--docs-header)] backdrop-blur-xl">
                <div className={`mx-auto flex h-16 items-center gap-4 px-5 lg:px-8 ${isFullWidth ? 'max-w-none' : 'max-w-[1500px]'}`}>
                    <button
                        type="button"
                        className="grid h-10 w-10 place-items-center rounded-lg border border-[var(--docs-border)] text-[var(--docs-muted)] lg:hidden"
                        onClick={() => setIsMobileNavOpen(true)}
                        aria-label="Open documentation navigation"
                    >
                        <Menu className="h-4 w-4" />
                    </button>

                    <div className="w-[220px] shrink-0">
                        <Brand site={site} />
                    </div>

                    <label className="relative hidden max-w-[520px] flex-1 lg:block">
                        <Search className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-[var(--docs-faint)]" />
                        <input
                            type="search"
                            value={navigationQuery}
                            onChange={(event) => setNavigationQuery(event.target.value)}
                            placeholder="Search..."
                            className="h-11 w-full rounded-full border border-[var(--docs-border)] bg-[var(--docs-surface)] pr-20 pl-10 text-sm text-[var(--docs-text)] outline-none transition placeholder:text-[var(--docs-faint)] focus:border-[var(--docs-accent)] focus:ring-4 focus:ring-[var(--docs-accent-ring)]"
                        />
                        <span className="pointer-events-none absolute top-1/2 right-3 hidden -translate-y-1/2 rounded-md border border-[var(--docs-border)] px-1.5 py-0.5 font-mono text-xs text-[var(--docs-faint)] sm:inline">Ctrl K</span>
                    </label>

                    <div className="ml-auto hidden items-center gap-2 text-sm md:flex">
                        <button type="button" onClick={copyCurrentPage} className="inline-flex h-10 items-center gap-2 rounded-full border border-[var(--docs-border)] px-4 font-medium text-[var(--docs-muted)] transition hover:text-[var(--docs-text)]">
                            <Clipboard className="h-4 w-4" /> Copy link
                        </button>
                        <span className="rounded-full border border-[var(--docs-border)] bg-[var(--docs-surface)] px-3 py-2 font-medium text-[var(--docs-muted)]">{release.version}</span>
                        <span className="rounded-full bg-[var(--docs-accent-soft)] px-3 py-2 font-semibold text-[var(--docs-accent-text)]">{release.environment}</span>
                        {publishedDate ? <span className="hidden text-[var(--docs-muted)] xl:inline">Updated {publishedDate}</span> : null}
                    </div>
                </div>

                <div className={`mx-auto flex h-12 items-center justify-between border-t border-[var(--docs-border)] px-5 lg:px-8 ${isFullWidth ? 'max-w-none' : 'max-w-[1500px]'}`}>
                    {sectionTabs.length > 0 ? (
                        <nav className="flex min-w-0 gap-8 overflow-x-auto text-sm font-medium text-[var(--docs-muted)]">
                            {sectionTabs.map((tab) => (
                                <DocsLink
                                    key={tab.label}
                                    href={docsHref(site, tab.path)}
                                    className={tab.isActive ? 'border-b-2 border-[var(--docs-accent)] py-3 text-[var(--docs-accent-text)]' : 'py-3 hover:text-[var(--docs-text)]'}
                                >
                                    {tab.label}
                                </DocsLink>
                            ))}
                        </nav>
                    ) : <span />}
                </div>
            </header>

            {isMobileNavOpen ? (
                <div className="fixed inset-0 z-50 lg:hidden">
                    <button type="button" className="absolute inset-0 bg-black/35" onClick={() => setIsMobileNavOpen(false)} aria-label="Close documentation navigation" />
                    <aside className="relative flex h-full w-[min(88vw,340px)] flex-col border-r border-[var(--docs-border)] bg-[var(--docs-surface)] shadow-2xl">
                        <div className="flex h-16 items-center justify-between border-b border-[var(--docs-border)] px-5">
                            <Brand site={site} />
                            <button type="button" className="grid h-9 w-9 place-items-center rounded-lg border border-[var(--docs-border)] text-[var(--docs-muted)]" onClick={() => setIsMobileNavOpen(false)} aria-label="Close documentation navigation">
                                <X className="h-4 w-4" />
                            </button>
                        </div>
                        <div className="border-b border-[var(--docs-border)] px-5 py-4">
                            <label className="relative block">
                                <Search className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-[var(--docs-faint)]" />
                                <input
                                    type="search"
                                    value={navigationQuery}
                                    onChange={(event) => setNavigationQuery(event.target.value)}
                                    placeholder="Search..."
                                    className="h-11 w-full rounded-full border border-[var(--docs-border)] bg-[var(--docs-surface)] pr-4 pl-10 text-sm text-[var(--docs-text)] outline-none transition placeholder:text-[var(--docs-faint)] focus:border-[var(--docs-accent)] focus:ring-4 focus:ring-[var(--docs-accent-ring)]"
                                />
                            </label>
                        </div>
                        <Sidebar groups={filteredNavigation} site={site} currentPath={page.path} />
                    </aside>
                </div>
            ) : null}

            <div className={`mx-auto grid lg:grid-cols-[320px_minmax(0,1fr)] ${isFullWidth ? 'max-w-none xl:grid-cols-[320px_minmax(0,1fr)_300px]' : 'max-w-[1500px] xl:grid-cols-[320px_minmax(0,800px)_260px]'}`}>
                <aside className="sticky top-28 hidden h-[calc(100vh-7rem)] border-r border-[var(--docs-border)] bg-[var(--docs-surface)] lg:block">
                    <Sidebar groups={filteredNavigation} site={site} currentPath={page.path} />
                </aside>

                <main className="min-w-0 px-6 py-10 sm:px-10 lg:px-14">
                    <article className={`mx-auto pb-20 ${isFullWidth ? 'max-w-none' : 'max-w-[780px]'}`}>
                        <div className="mb-4 text-xs font-semibold tracking-[0.08em] text-[var(--docs-muted)] uppercase">{page.spaceName ?? site.brandName}</div>
                        <header className="mb-10">
                            <div className="flex items-start gap-5">
                                <span className="mt-1 hidden h-14 w-14 shrink-0 items-center justify-center rounded-lg text-[var(--docs-accent)] sm:flex">
                                    <Zap className="h-12 w-12 stroke-[1.4]" />
                                </span>
                                <div className="min-w-0">
                                    <h1 className="text-4xl font-semibold tracking-tight text-[var(--docs-text)] sm:text-5xl">{page.title}</h1>
                                    {page.subtitle ? <p className="mt-4 text-xl leading-8 text-[var(--docs-muted)]">{page.subtitle}</p> : null}
                                </div>
                            </div>
                        </header>

                        <div className="mb-8 flex flex-wrap items-center gap-3 border-b border-[var(--docs-border)] pb-6 text-sm text-[var(--docs-muted)]">
                            <button type="button" onClick={copyCurrentPage} className="inline-flex items-center gap-2 rounded-full border border-[var(--docs-border)] bg-[var(--docs-surface)] px-3 py-2 font-medium transition hover:text-[var(--docs-text)]">
                                <Clipboard className="h-4 w-4" /> Copy link
                            </button>
                            <span className="rounded-full border border-[var(--docs-border)] bg-[var(--docs-surface-muted)] px-3 py-2 font-medium">{release.version}</span>
                            <span className="rounded-full bg-[var(--docs-accent-soft)] px-3 py-2 font-semibold text-[var(--docs-accent-text)]">{release.environment}</span>
                        </div>

                        <div className="space-y-7">
                            {page.blocks.map((block, index) => {
                                const blockKey = docsBlockKey(block, index);
                                const headingId = block.kind === 'h2' || block.kind === 'h3'
                                    ? (headingIds.get(blockKey) ?? null)
                                    : null;

                                return (
                                    <section key={blockKey} id={headingId ?? undefined} className="scroll-mt-36 space-y-4">
                                        <BlockRenderer block={block} />
                                    </section>
                                );
                            })}
                        </div>

                        <div className="mt-14 grid gap-4 border-t border-[var(--docs-border)] pt-8 sm:grid-cols-2">
                            {previousPage ? (
                                <DocsLink href={docsHref(site, previousPage.path)} className="rounded-lg border border-[var(--docs-border)] bg-[var(--docs-surface)] p-5 transition hover:border-[var(--docs-accent)] hover:shadow-sm">
                                    <span className="flex items-center gap-2 text-sm text-[var(--docs-muted)]"><ChevronLeft className="h-4 w-4" /> Previous</span>
                                    <strong className="mt-2 block text-[var(--docs-text)]">{previousPage.title}</strong>
                                </DocsLink>
                            ) : <div />}
                            {nextPage ? (
                                <DocsLink href={docsHref(site, nextPage.path)} className="rounded-lg border border-[var(--docs-border)] bg-[var(--docs-surface)] p-5 text-right transition hover:border-[var(--docs-accent)] hover:shadow-sm">
                                    <span className="flex items-center justify-end gap-2 text-sm text-[var(--docs-muted)]">Next <ChevronRight className="h-4 w-4" /></span>
                                    <strong className="mt-2 block text-[var(--docs-text)]">{nextPage.title}</strong>
                                </DocsLink>
                            ) : null}
                        </div>
                    </article>
                </main>

                <aside className="hidden xl:block">
                    <div className="sticky top-32 mx-6 max-h-[calc(100vh-9rem)] overflow-y-auto border-l border-[var(--docs-border)] pl-5">
                        <div className="mb-4 flex items-center gap-2 text-xs font-bold tracking-[0.08em] text-[var(--docs-muted)] uppercase"><CircleHelp className="h-4 w-4" /> On this page</div>
                        <ul className="space-y-3">
                            {headings.length ? headings.map((heading) => (
                                <li key={heading.id}>
                                    <a href={`#${heading.id}`} className={`block border-l-2 border-transparent py-0.5 text-sm text-[var(--docs-muted)] transition hover:border-[var(--docs-accent)] hover:text-[var(--docs-accent-text)] ${heading.level === 'h3' ? 'pl-5' : 'pl-3'}`}>
                                        {heading.label}
                                    </a>
                                </li>
                            )) : <li className="text-sm text-[var(--docs-muted)]">No sections yet.</li>}
                        </ul>

                        <div className="mt-8 border-t border-[var(--docs-border)] pt-6 text-sm text-[var(--docs-muted)]">
                            <div className="font-medium text-[var(--docs-text)]">Release</div>
                            <div className="mt-2 inline-flex rounded-md border border-[var(--docs-border)] bg-[var(--docs-surface)] px-2.5 py-1 font-medium text-[var(--docs-text)]">{release.version}</div>
                            {publishedDate ? <p className="mt-3">Published {publishedDate}</p> : null}
                        </div>
                    </div>
                </aside>
            </div>
        </div>
    );
}

export const gitbookTheme: DocsThemeDefinition = {
    id: 'gitbook',
    name: 'GitBook',
    description: 'A broad documentation portal layout with top navigation, orange accents, and a strong left guide rail.',
    swatches: ['#ffffff', '#f7f7f5', '#ff4f1f'],
    styles: {
        '--docs-bg': '#ffffff',
        '--docs-header': 'rgba(255, 255, 255, 0.94)',
        '--docs-surface': '#ffffff',
        '--docs-surface-muted': '#f7f7f5',
        '--docs-border': '#e6e1dc',
        '--docs-text': '#242426',
        '--docs-muted': '#707176',
        '--docs-faint': '#a2a2a6',
        '--docs-accent': '#ff4f1f',
        '--docs-accent-soft': '#fff1eb',
        '--docs-accent-text': '#e63d12',
        '--docs-accent-ring': '#ffc5b0',
        '--docs-brand': '#242426',
        '--docs-brand-text': '#ffffff',
        '--docs-code-bg': '#171717',
        '--docs-code-text': '#f8f5f2',
    },
    component: GitBookTheme,
};

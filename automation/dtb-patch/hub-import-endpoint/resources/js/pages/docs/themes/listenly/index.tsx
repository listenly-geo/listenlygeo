import { useState } from 'react';
import { BlockRenderer, DocsLink, docsBlockKey, docsHomeHref, docsHref, stripHtml } from '../shared';
import type { DocsNavigationNode, DocsThemeDefinition, DocsThemeProps } from '../types';

const LISTENLY_URL = 'https://listenly.org';

function flattenAnswers(nodes: DocsNavigationNode[]): DocsNavigationNode[] {
    return nodes.flatMap((node) => [node, ...flattenAnswers(node.children)]);
}

function ListenlyHome({ site, navigation, rootStyle }: DocsThemeProps) {
    const [query, setQuery] = useState('');
    const ctaHref = site.primaryDomain ? `https://${site.primaryDomain}` : '#';
    const answers = flattenAnswers(navigation).filter((node) => node.path !== 'quickstart');
    const filtered = answers.filter((node) => stripHtml(node.title).toLowerCase().includes(query.trim().toLowerCase()));
    const groups = filtered.reduce<Record<string, DocsNavigationNode[]>>((acc, node) => {
        const key = node.spaceName ?? 'Expert answers';
        (acc[key] ??= []).push(node);

        return acc;
    }, {});

    return (
        <div style={rootStyle} className="min-h-screen bg-[var(--docs-bg)] text-[var(--docs-text)]">
            <header className="sticky top-0 z-20 border-b border-white/10 bg-black/90 backdrop-blur">
                <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-5 py-4">
                    <DocsLink href={docsHomeHref(site)} className="flex items-center gap-3 no-underline">
                        <span className="grid h-8 w-8 place-items-center overflow-hidden rounded-lg bg-[var(--docs-accent)] text-sm font-bold text-white">
                            {site.brandName.charAt(0).toUpperCase()}
                        </span>
                        <span className="text-[15px] font-semibold text-[var(--docs-text)]">{site.brandName}</span>
                    </DocsLink>
                    <a href={ctaHref} target="_blank" rel="noreferrer" className="rounded-full bg-[var(--docs-text)] px-4 py-2 text-[13px] font-semibold text-black no-underline transition hover:opacity-85">
                        Discover our offer
                    </a>
                </div>
            </header>

            <main className="mx-auto max-w-3xl px-5 pt-12 pb-24">
                <h1 className="text-[34px] leading-[1.15] font-semibold tracking-[-0.015em] sm:text-[42px]">Expert answers</h1>
                {site.tagline ? <p className="mt-3 text-[16px] text-[var(--docs-muted)]">{site.tagline}</p> : null}

                <input
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search the answers"
                    className="mt-8 w-full rounded-full border border-white/10 bg-[var(--docs-surface)] px-5 py-3 text-[15px] text-[var(--docs-text)] outline-none placeholder:text-[var(--docs-faint)] focus:border-[var(--docs-accent)]"
                />

                <div className="mt-10 space-y-10">
                    {Object.entries(groups).map(([group, nodes]) => (
                        <section key={group}>
                            <p className="mb-3 text-[12px] font-semibold tracking-[0.14em] text-[var(--docs-faint)] uppercase">{group}</p>
                            <ul className="divide-y divide-white/10 overflow-hidden rounded-2xl border border-white/10 bg-[var(--docs-surface)]">
                                {nodes.map((node) => (
                                    <li key={node.path}>
                                        <DocsLink href={docsHref(site, node.path)} className="block px-5 py-4 text-[16px] font-medium text-[var(--docs-text)] no-underline transition hover:bg-white/5">
                                            {stripHtml(node.title)}
                                        </DocsLink>
                                    </li>
                                ))}
                            </ul>
                        </section>
                    ))}
                    {filtered.length === 0 ? <p className="text-[15px] text-[var(--docs-muted)]">No answer matches this search.</p> : null}
                </div>

                <footer className="mt-16 border-t border-white/10 pt-6 text-[13px] text-[var(--docs-muted)]">
                    <a href={LISTENLY_URL} target="_blank" rel="noreferrer" className="text-[var(--docs-accent)] no-underline hover:opacity-75">
                        Explore more expert answers on Listenly →
                    </a>
                </footer>
            </main>
        </div>
    );
}

function ListenlyArticle(props: DocsThemeProps) {
    if (props.page.path === '') {
        return <ListenlyHome {...props} />;
    }
    const { site, page, previousPage, nextPage, rootStyle } = props;
    const ctaHref = site.primaryDomain ? `https://${site.primaryDomain}` : '#';
    const homeHref = docsHomeHref(site);
    const plainTitle = stripHtml(page.title);

    return (
        <div style={rootStyle} className="min-h-screen bg-[var(--docs-bg)] text-[var(--docs-text)]">
            <header className="sticky top-0 z-20 border-b border-white/10 bg-black/90 backdrop-blur">
                <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-5 py-4">
                    <DocsLink href={homeHref} className="flex items-center gap-3 no-underline">
                        <span className="grid h-8 w-8 place-items-center overflow-hidden rounded-lg bg-[var(--docs-accent)] text-sm font-bold text-white">
                            {site.brandName.charAt(0).toUpperCase()}
                        </span>
                        <span className="text-[15px] font-semibold text-[var(--docs-text)]">{site.brandName}</span>
                    </DocsLink>
                    <a
                        href={ctaHref}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-full bg-[var(--docs-text)] px-4 py-2 text-[13px] font-semibold text-black no-underline transition hover:opacity-85"
                    >
                        Discover our offer
                    </a>
                </div>
            </header>

            <main className="mx-auto max-w-3xl px-5 pt-12 pb-24">
                <p className="mb-4 text-[12px] font-semibold tracking-[0.14em] text-[var(--docs-faint)] uppercase">
                    {page.spaceName ?? 'Expert answers'}
                </p>
                <h1 className="text-[34px] leading-[1.15] font-semibold tracking-[-0.015em] text-[var(--docs-text)] sm:text-[42px]">
                    {plainTitle}
                </h1>
                {page.subtitle ? (
                    <p className="mt-4 text-[16px] text-[var(--docs-muted)]">{stripHtml(page.subtitle)}</p>
                ) : null}

                <div className="mt-10 space-y-6 text-[17px] leading-[1.75] text-[#D2D2D7] [&_a]:text-[var(--docs-accent)] [&_a]:no-underline">
                    {page.blocks.map((block, index) => (
                        <BlockRenderer key={docsBlockKey(block, index)} block={block} />
                    ))}
                </div>

                <div className="mt-14 rounded-2xl border border-white/10 bg-[var(--docs-surface)] p-6">
                    <p className="text-[18px] font-semibold text-[var(--docs-text)]">Want this applied to your business?</p>
                    <p className="mt-2 text-[15px] text-[var(--docs-muted)]">Talk to {site.brandName} about the next step.</p>
                    <a
                        href={ctaHref}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-5 inline-block rounded-full bg-[var(--docs-accent)] px-5 py-2.5 text-[14px] font-semibold text-white no-underline transition hover:opacity-85"
                    >
                        Discover our offer
                    </a>
                </div>

                <nav className="mt-12 grid gap-3 sm:grid-cols-2">
                    {previousPage ? (
                        <DocsLink href={docsHref(site, previousPage.path)} className="rounded-xl border border-white/10 bg-[var(--docs-surface)] p-4 no-underline">
                            <span className="text-[12px] text-[var(--docs-faint)]">Previous answer</span>
                            <span className="mt-1 block text-[14px] font-medium text-[var(--docs-text)]">{stripHtml(previousPage.title)}</span>
                        </DocsLink>
                    ) : <span />}
                    {nextPage ? (
                        <DocsLink href={docsHref(site, nextPage.path)} className="rounded-xl border border-white/10 bg-[var(--docs-surface)] p-4 text-right no-underline">
                            <span className="text-[12px] text-[var(--docs-faint)]">Next answer</span>
                            <span className="mt-1 block text-[14px] font-medium text-[var(--docs-text)]">{stripHtml(nextPage.title)}</span>
                        </DocsLink>
                    ) : null}
                </nav>

                <footer className="mt-16 border-t border-white/10 pt-6 text-[13px] text-[var(--docs-muted)]">
                    <a href={LISTENLY_URL} target="_blank" rel="noreferrer" className="text-[var(--docs-accent)] no-underline hover:opacity-75">
                        Explore more expert answers on Listenly →
                    </a>
                </footer>
            </main>
        </div>
    );
}

export const listenlyTheme: DocsThemeDefinition = {
    id: 'listenly',
    name: 'Listenly',
    description: 'Dark expert-answer hub with an article layout, a Listenly audio player and a clear call to action.',
    swatches: ['#000000', '#1C1C1E', '#2997FF'],
    styles: {
        '--docs-bg': '#000000',
        '--docs-header': 'rgba(0, 0, 0, 0.9)',
        '--docs-surface': '#1C1C1E',
        '--docs-surface-muted': '#2C2C2E',
        '--docs-border': 'rgba(255, 255, 255, 0.12)',
        '--docs-text': '#F5F5F7',
        '--docs-muted': '#86868B',
        '--docs-faint': '#6E6E73',
        '--docs-accent': '#2997FF',
        '--docs-accent-soft': 'rgba(41, 151, 255, 0.14)',
        '--docs-accent-text': '#2997FF',
        '--docs-accent-ring': 'rgba(41, 151, 255, 0.4)',
        '--docs-brand': '#2997FF',
        '--docs-brand-text': '#ffffff',
        '--docs-code-bg': '#1C1C1E',
        '--docs-code-text': '#F5F5F7',
    },
    component: ListenlyArticle,
};

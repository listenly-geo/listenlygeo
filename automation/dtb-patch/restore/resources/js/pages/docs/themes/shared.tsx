import DOMPurify from 'dompurify';
import { Link } from '@inertiajs/react';
import type { ElementType, ReactNode } from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import type { DocsBlock, DocsNavigationNode, DocsSite, DocsHeading, NavigationGroup } from './types';

const renderKatexMarkup = (value: string, displayMode = true) => {
    const expression = value.trim();

    if (!expression) {
        return null;
    }

    try {
        return katex.renderToString(expression, {
            displayMode,
            throwOnError: false,
        });
    } catch {
        return null;
    }
};

function DocsMathBlock({ expression }: { expression: string }) {
    const markup = renderKatexMarkup(expression);

    return markup ? (
        <div className="overflow-x-auto rounded-lg border border-black/10 bg-[var(--docs-code-bg)] px-5 py-4 text-[15px] text-[var(--docs-code-text)]" dangerouslySetInnerHTML={{ __html: markup }} />
    ) : (
        <div className="rounded-lg border border-black/20 bg-[var(--docs-code-bg)] px-5 py-4 font-mono text-[15px] text-[var(--docs-code-text)]">
            {expression}
        </div>
    );
}

export const stripHtml = (value: string | undefined | null) =>
    (value ?? '').replace(/<[^>]*>/g, '').trim();

const docsHtmlSanitizerOptions = {
    ALLOWED_TAGS: [
        'a',
        'abbr',
        'b',
        'blockquote',
        'br',
        'code',
        'del',
        'div',
        'em',
        'i',
        'kbd',
        'li',
        'mark',
        'ol',
        'p',
        'pre',
        's',
        'span',
        'strong',
        'sub',
        'sup',
        'u',
        'ul',
    ],
    ALLOWED_ATTR: ['href', 'rel', 'target', 'title'],
    ALLOW_DATA_ATTR: false,
};

export const sanitizeDocsHtml = (value: string | undefined | null) => {
    const html = String(value ?? '');

    if (!html.trim()) {
        return '';
    }

    return DOMPurify.sanitize(html, docsHtmlSanitizerOptions);
};

export const slugify = (value: string) =>
    stripHtml(value)
        .normalize('NFKD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .replace(/[^\p{Letter}\p{Number}]+/gu, '-')
        .replace(/^-+|-+$/g, '');

export const docsBlockKey = (block: DocsBlock, index: number) =>
    block.id ?? `${block.kind}-${index}`;

export const docsHref = (site: DocsSite, path: string) => `${(site.basePath ?? `/docs/${site.slug}`).replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`;

export const docsHomeHref = (site: DocsSite) => site.basePath ?? `/docs/${site.slug}`;

const normalizeEmbedUrl = (value: string | null | undefined) => {
    const raw = String(value ?? '').trim();

    if (!raw) {
        return null;
    }

    try {
        return new URL(raw).toString();
    } catch {
        if (/^(mailto:|tel:|https?:\/\/)/i.test(raw)) {
            return raw;
        }

        return `https://${raw}`;
    }
};

const extractYouTubeId = (value: string | null | undefined) => {
    const normalizedUrl = normalizeEmbedUrl(value);

    if (!normalizedUrl) {
        return null;
    }

    try {
        const url = new URL(normalizedUrl);
        const host = url.hostname.replace(/^www\./i, '').toLowerCase();

        if (host === 'youtube.com' || host === 'm.youtube.com') {
            const videoId = url.searchParams.get('v');

            if (videoId) {
                return videoId;
            }

            const segments = url.pathname.split('/').filter(Boolean);

            if (segments[0] === 'embed' || segments[0] === 'shorts' || segments[0] === 'live') {
                return segments[1] ?? null;
            }
        }

        if (host === 'youtu.be') {
            return url.pathname.split('/').filter(Boolean)[0] ?? null;
        }
    } catch {
        return null;
    }

    return null;
};

export function DocsLink({ href, className, children }: { href: string; className?: string; children: ReactNode }) {
    return (
        <Link href={href} className={className}>
            {children}
        </Link>
    );
}

export const formatDate = (value: string | null, includeTime = false) => {
    if (!value) {
        return null;
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return null;
    }

    return includeTime
        ? date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
        : date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
};

export const filterNavigation = (nodes: DocsNavigationNode[], query: string, searchDocumentsByPath?: Record<string, string>): DocsNavigationNode[] => {
    const needle = query.trim().toLowerCase();

    if (!needle) {
        return nodes;
    }

    return nodes
        .map((node) => {
            const children = filterNavigation(node.children, query, searchDocumentsByPath);
            const searchText = `${node.title} ${node.path} ${node.spaceName ?? ''} ${searchDocumentsByPath?.[node.path] ?? ''}`;
            const matches = searchText.toLowerCase().includes(needle);

            return matches || children.length > 0 ? { ...node, children } : null;
        })
        .filter((node): node is DocsNavigationNode => node !== null);
};

export const groupNavigation = (navigation: DocsNavigationNode[]): NavigationGroup[] => {
    const groups = new Map<string, DocsNavigationNode[]>();

    for (const node of navigation) {
        const key = node.spaceName ?? '';
        const existing = groups.get(key) ?? [];
        existing.push(node);
        groups.set(key, existing);
    }

    return Array.from(groups.entries()).map(([label, nodes]) => ({ label, nodes }));
};

export const extractHeadings = (blocks: DocsBlock[]): DocsHeading[] => {
    const seenHeadingIds = new Map<string, number>();

    return blocks.flatMap((block, index) => {
        if (block.kind !== 'h2' && block.kind !== 'h3') {
            return [];
        }

        const label = stripHtml(block.text ?? block.title ?? '');

        if (!label) {
            return [];
        }

        const baseId = slugify(label) || `section-${index + 1}`;
        const duplicateCount = (seenHeadingIds.get(baseId) ?? 0) + 1;

        seenHeadingIds.set(baseId, duplicateCount);

        return [{
            blockKey: docsBlockKey(block, index),
            id: duplicateCount === 1 ? baseId : `${baseId}-${duplicateCount}`,
            label,
            level: block.kind,
        }];
    });
};

export const copyCurrentPage = () => {
    if (typeof window === 'undefined' || !navigator.clipboard) {
        return;
    }

    void navigator.clipboard.writeText(window.location.href);
};

export function PlatformBrandingBadge({ site, className = '' }: { site: DocsSite; className?: string }) {
    const branding = site.platformBranding;

    if (!branding?.enabled) {
        return null;
    }

    const initial = (branding.name || 'D').trim().charAt(0).toUpperCase() || 'D';

    return (
        <a
            href={branding.url}
            target="_blank"
            rel="noreferrer"
            className={`flex items-center gap-2 rounded-lg border border-[var(--docs-border)] bg-[var(--docs-surface-muted)] px-3 py-2 text-xs text-[var(--docs-muted)] transition hover:border-[var(--docs-accent-ring)] hover:text-[var(--docs-text)] ${className}`}
        >
            <span className="grid h-6 w-6 shrink-0 place-items-center overflow-hidden rounded-md bg-[var(--docs-surface)] text-[11px] font-bold text-[var(--docs-accent-text)] ring-1 ring-[var(--docs-border)]">
                {branding.logoUrl ? <img src={branding.logoUrl} alt="" className="h-full w-full object-contain p-0.5" /> : initial}
            </span>
            <span className="min-w-0 truncate">
                Powered by <strong className="font-semibold text-[var(--docs-text)]">{branding.name}</strong>
            </span>
        </a>
    );
}

export function HtmlBlock({
    html,
    className,
    as: Tag = 'div',
}: {
    html: string | undefined | null;
    className?: string;
    as?: ElementType;
}) {
    const Component = Tag;
    const sanitizedHtml = sanitizeDocsHtml(html);

    return (
        <Component
            className={className}
            dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
        />
    );
}

function TabsBlock({ block }: { block: DocsBlock }) {
    const tabs = block.tabs ?? [];
    const [activeTabId, setActiveTabId] = useState(tabs[0]?.id ?? 'tab-0');
    const activeTab =
        tabs.find((tab) => (tab.id ?? 'tab-0') === activeTabId) ?? tabs[0] ?? null;

    if (!activeTab) {
        return null;
    }

    return (
        <section className="overflow-hidden rounded-lg border border-[var(--docs-border)] bg-[var(--docs-surface)]">
            <div className="flex flex-wrap gap-2 border-b border-[var(--docs-border)] bg-[var(--docs-surface-muted)] px-4 py-3">
                {tabs.map((tab, index) => {
                    const tabId = tab.id ?? `tab-${index}`;

                    return (
                        <button
                            key={tabId}
                            type="button"
                            onClick={() => setActiveTabId(tabId)}
                            className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                                tabId === activeTabId
                                    ? 'bg-[var(--docs-accent)] text-white shadow-sm'
                                    : 'text-[var(--docs-muted)] hover:bg-[var(--docs-surface)] hover:text-[var(--docs-text)]'
                            }`}
                        >
                            {tab.label}
                        </button>
                    );
                })}
            </div>
            <div className="bg-[var(--docs-code-bg)] px-5 py-4 text-sm text-[var(--docs-code-text)]">
                <div className="mb-3 flex items-center justify-between text-xs font-medium uppercase tracking-[0.18em] text-white/55">
                    <span>{activeTab.lang ?? 'snippet'}</span>
                    <span>{block.title ?? 'Example'}</span>
                </div>
                <pre className="overflow-x-auto font-mono text-[13px] leading-6 whitespace-pre-wrap">
                    <code>{activeTab.code}</code>
                </pre>
            </div>
        </section>
    );
}

export function BlockRenderer({ block }: { block: DocsBlock }) {
    switch (block.kind) {
        case 'h1':
            return (
                <HtmlBlock
                    as="h1"
                    html={block.text}
                    className="text-4xl font-semibold text-[var(--docs-text)] lg:text-5xl"
                />
            );
        case 'h2':
            return (
                <HtmlBlock
                    as="h2"
                    html={block.text}
                    className="scroll-mt-28 border-t border-[var(--docs-border)] pt-10 text-2xl font-semibold text-[var(--docs-text)]"
                />
            );
        case 'h3':
            return (
                <HtmlBlock
                    as="h3"
                    html={block.text}
                    className="scroll-mt-28 text-xl font-semibold text-[var(--docs-text)]"
                />
            );
        case 'p':
            return (
                <HtmlBlock
                    as="div"
                    html={block.html}
                    className="prose prose-slate max-w-none text-[16px] leading-7 text-[var(--docs-text)] prose-a:font-medium prose-a:text-[var(--docs-accent-text)] prose-a:no-underline hover:prose-a:text-[var(--docs-accent)] prose-code:rounded-md prose-code:bg-[var(--docs-surface-muted)] prose-code:px-1.5 prose-code:py-0.5 prose-code:text-[var(--docs-text)] prose-code:before:content-none prose-code:after:content-none prose-pre:bg-transparent"
                />
            );
        case 'quote':
            return (
                <blockquote className="rounded-lg border border-[var(--docs-border)] border-l-4 border-l-[var(--docs-accent)] bg-[var(--docs-surface-muted)] px-5 py-4 text-lg leading-8 text-[var(--docs-muted)]">
                    <HtmlBlock html={block.html} className="space-y-4" />
                </blockquote>
            );
        case 'divider':
            return <hr className="border-[var(--docs-border)]" />;
        case 'code':
            return (
                <section className="overflow-hidden rounded-lg border border-black/20 bg-[var(--docs-code-bg)] shadow-sm">
                    <div className="flex items-center justify-between border-b border-white/10 bg-white/5 px-5 py-3 text-xs font-medium uppercase tracking-[0.16em] text-white/55">
                        <span>{block.lang ?? 'code'}</span>
                        <span>{block.filename ?? 'snippet'}</span>
                    </div>
                    <pre className="overflow-x-auto px-5 py-5 font-mono text-[13px] leading-6 whitespace-pre-wrap text-[var(--docs-code-text)]">
                        <code>{block.code ?? ''}</code>
                    </pre>
                </section>
            );
        case 'api':
            return (
                <section className="rounded-lg border border-[var(--docs-border)] bg-[var(--docs-surface)] p-5 shadow-sm">
                    <div className="mb-4 flex flex-wrap items-center gap-3">
                        <span className="rounded-md bg-[var(--docs-accent)] px-2.5 py-1 text-xs font-semibold tracking-[0.12em] text-white uppercase">
                            {block.method ?? 'GET'}
                        </span>
                        <code className="rounded-md bg-[var(--docs-surface-muted)] px-2.5 py-1 font-mono text-sm text-[var(--docs-text)]">{block.path}</code>
                    </div>
                    {block.desc ? <p className="mb-5 text-[15px] leading-7 text-[var(--docs-muted)]">{block.desc}</p> : null}
                    {block.params && block.params.length > 0 ? (
                        <div className="overflow-hidden rounded-lg border border-[var(--docs-border)]">
                            <table className="min-w-full divide-y divide-[var(--docs-border)] text-left text-sm">
                                <thead className="bg-[var(--docs-surface-muted)] text-[var(--docs-muted)]">
                                    <tr>
                                        <th className="px-4 py-3 font-medium">Parameter</th>
                                        <th className="px-4 py-3 font-medium">Type</th>
                                        <th className="px-4 py-3 font-medium">Description</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-[var(--docs-border)] bg-[var(--docs-surface)] text-[var(--docs-muted)]">
                                    {block.params.map((param) => (
                                        <tr key={`${param.name}-${param.type}`}>
                                            <td className="px-4 py-3 font-medium">{param.name}</td>
                                            <td className="px-4 py-3 font-mono text-xs uppercase tracking-[0.12em] text-[var(--docs-faint)]">{param.type}</td>
                                            <td className="px-4 py-3">{param.desc}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : null}
                </section>
            );
        case 'callout': {
            const palette = {
                info: 'border-[var(--docs-accent-ring)] bg-[var(--docs-accent-soft)] text-[var(--docs-accent-text)]',
                warn: 'border-amber-200 bg-amber-50 text-amber-900',
                ok: 'border-[var(--docs-accent-ring)] bg-[var(--docs-accent-soft)] text-[var(--docs-accent-text)]',
                danger: 'border-rose-200 bg-rose-50 text-rose-900',
            } as const;
            const variant = block.variant && block.variant in palette ? block.variant as keyof typeof palette : 'info';

            return (
                <section className={`rounded-lg border px-5 py-4 ${palette[variant]}`}>
                    {block.title ? <HtmlBlock html={block.title} className="mb-2 text-sm font-semibold" /> : null}
                    <HtmlBlock html={block.text} className="prose max-w-none text-[15px] leading-7 prose-p:my-0" />
                </section>
            );
        }
        case 'figure':
            return (
                <figure className="overflow-hidden rounded-lg border border-[var(--docs-border)] bg-[var(--docs-surface)]">
                    {block.src ? (
                        <img src={block.src} alt={block.alt ?? ''} className="max-h-[520px] w-full object-cover" />
                    ) : (
                        <div className="flex min-h-56 items-center justify-center bg-[var(--docs-surface-muted)] text-sm font-medium tracking-[0.12em] text-[var(--docs-faint)] uppercase">Image</div>
                    )}
                    {block.caption ? <figcaption className="border-t border-[var(--docs-border)] px-5 py-3 text-sm text-[var(--docs-muted)]"><HtmlBlock html={block.caption} /></figcaption> : null}
                </figure>
            );
        case 'table':
            return (
                <div className="overflow-hidden rounded-lg border border-[var(--docs-border)] bg-[var(--docs-surface)]">
                    <table className="min-w-full divide-y divide-[var(--docs-border)] text-left text-sm">
                        <thead className="bg-[var(--docs-surface-muted)] text-[var(--docs-muted)]">
                            <tr>
                                {(block.headers ?? []).map((header) => (
                                    <th key={header} className="px-4 py-3 font-medium">{header}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--docs-border)] text-[var(--docs-muted)]">
                            {(block.rows ?? []).map((row, index) => (
                                <tr key={`row-${index}`}>
                                    {row.map((cell, cellIndex) => (
                                        <td key={`cell-${index}-${cellIndex}`} className="px-4 py-3">{cell}</td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            );
        case 'tabs':
            return <TabsBlock block={block} />;
        case 'expand':
            return (
                <details className="rounded-lg border border-[var(--docs-border)] bg-[var(--docs-surface)] px-5 py-4">
                    <summary className="cursor-pointer list-none text-base font-semibold text-[var(--docs-text)]">{block.title ?? 'More details'}</summary>
                    <div className="mt-4 text-[15px] leading-7 text-[var(--docs-muted)]">{block.body}</div>
                </details>
            );
        case 'cards':
            return (
                <div className="grid gap-4 md:grid-cols-2">
                    {(block.items ?? []).map((item, index) => (
                        <article key={item.id ?? `${item.title ?? 'card'}-${index}`} className="rounded-lg border border-[var(--docs-border)] bg-[var(--docs-surface)] p-5 transition hover:border-[var(--docs-accent-ring)] hover:shadow-sm">
                            <div className="mb-3 text-xs font-semibold tracking-[0.12em] text-[var(--docs-accent-text)] uppercase">{item.ico ?? 'Doc'}</div>
                            <h4 className="text-lg font-semibold text-[var(--docs-text)]">{item.title}</h4>
                            {item.desc ? <p className="mt-2 text-[15px] leading-7 text-[var(--docs-muted)]">{item.desc}</p> : null}
                        </article>
                    ))}
                </div>
            );
        case 'math':
            return <DocsMathBlock expression={block.expr?.raw ?? ''} />;
        case 'embed': {
            const normalizedUrl = normalizeEmbedUrl(block.url);
            const youtubeId = extractYouTubeId(block.url);
            const directVideoUrl = (() => {
                if (!normalizedUrl) return null;
                if (String(block.mimeType ?? '').startsWith('video/')) return normalizedUrl;
                try {
                    const u = new URL(normalizedUrl);
                    return /\.(mp4|webm|ogg)$/i.test(u.pathname) ? normalizedUrl : null;
                } catch {
                    return null;
                }
            })();
            const pdfUrl = (() => {
                if (!normalizedUrl) return null;
                if (String(block.mimeType ?? '') === 'application/pdf') return normalizedUrl;
                try {
                    const u = new URL(normalizedUrl);
                    return /\.pdf$/i.test(u.pathname) ? normalizedUrl : null;
                } catch {
                    return null;
                }
            })();
            if (youtubeId) {
                return (
                    <div style={{ position: 'relative', paddingBottom: '56.25%', height: 0, overflow: 'hidden', borderRadius: 8, margin: '8px 0' }}>
                        <iframe
                            src={`https://www.youtube.com/embed/${youtubeId}`}
                            style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', border: 0 }}
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                            allowFullScreen
                        />
                    </div>
                );
            }
            if (directVideoUrl) {
                return (
                    <div style={{ margin: '8px 0', overflow: 'hidden', borderRadius: 8, border: '1px solid var(--docs-border)', background: 'var(--docs-code-bg)' }}>
                        <video
                            src={directVideoUrl}
                            controls
                            playsInline
                            preload="metadata"
                            style={{ display: 'block', width: '100%', maxHeight: 480, background: '#020617' }}
                        />
                    </div>
                );
            }
            if (pdfUrl) {
                return (
                    <div style={{ margin: '8px 0', overflow: 'hidden', borderRadius: 8, border: '1px solid var(--docs-border)', background: 'var(--docs-surface)' }}>
                        <iframe src={pdfUrl} title={block.title ?? 'Embedded document'} style={{ display: 'block', width: '100%', minHeight: 480, border: 0 }} />
                    </div>
                );
            }
            return (
                <a href={block.url} target="_blank" rel="noreferrer" className="block rounded-lg border border-[var(--docs-border)] bg-[var(--docs-surface)] p-5 transition hover:border-[var(--docs-accent-ring)] hover:shadow-sm">
                    <div className="text-xs font-semibold tracking-[0.12em] text-[var(--docs-faint)] uppercase">{block.source ?? 'Embed'}</div>
                    <div className="mt-2 text-lg font-semibold text-[var(--docs-text)]">{block.title ?? 'Embedded content'}</div>
                    {block.url ? <div className="mt-2 break-all text-sm text-[var(--docs-accent-text)]">{block.url}</div> : null}
                </a>
            );
        }
        case 'checklist':
            return (
                <ul className="space-y-3 rounded-lg border border-[var(--docs-border)] bg-[var(--docs-surface)] p-5">
                    {(block.items ?? []).map((item, index) => (
                        <li key={item.id ?? `${item.text ?? 'task'}-${index}`} className="flex items-start gap-3 text-[15px] leading-7 text-[var(--docs-muted)]">
                            <span className={`mt-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[9px] font-semibold ${item.done ? 'border-[var(--docs-accent)] bg-[var(--docs-accent)] text-white' : 'border-[var(--docs-border)] bg-[var(--docs-surface)] text-transparent'}`}>
                                {item.done ? 'OK' : ''}
                            </span>
                            <span className={item.done ? 'line-through opacity-70' : ''}>{item.text}</span>
                        </li>
                    ))}
                </ul>
            );
        default:
            return (
                <div className="rounded-lg border border-dashed border-[var(--docs-border)] bg-[var(--docs-surface-muted)] px-5 py-4 text-sm text-[var(--docs-muted)]">
                    Unsupported block type: <span className="font-mono">{block.kind}</span>
                </div>
            );
    }
}

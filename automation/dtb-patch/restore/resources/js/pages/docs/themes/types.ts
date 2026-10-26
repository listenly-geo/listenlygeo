import type { ComponentType, CSSProperties } from 'react';
import type { DocsThemeId, DocsThemeOptions } from './catalog';

export type DocsSite = {
    name: string;
    slug: string;
    visibility: string;
    brandName: string;
    tagline: string | null;
    seoTitle: string | null;
    seoDescription: string | null;
    logoUrl?: string | null;
    docsTheme?: DocsThemeId | string | null;
    docsThemeOptions?: Partial<DocsThemeOptions> | null;
    platformBranding?: {
        enabled: boolean;
        name: string;
        logoUrl: string | null;
        url: string;
    };
    primaryDomain: string | null;
    basePath?: string;
};

export type DocsRelease = {
    id: number | null;
    version: string;
    environment: string;
    publishedAt: string | null;
};

export type DocsNavigationNode = {
    title: string;
    path: string;
    spaceName: string | null;
    children: DocsNavigationNode[];
};

export type DocsPageLink = {
    title: string;
    path: string;
    spaceName: string | null;
};

export type DocsSearchIndexEntry = {
    title: string;
    path: string;
    spaceName: string | null;
    searchDocument: string | null;
};

export type DocsBlock = {
    id?: string;
    kind: string;
    html?: string;
    text?: string;
    title?: string;
    subtitle?: string;
    caption?: string;
    alt?: string;
    src?: string;
    lang?: string;
    filename?: string;
    code?: string;
    variant?: string;
    method?: string;
    path?: string;
    desc?: string;
    params?: Array<{ name: string; type: string; desc: string }>;
    headers?: string[];
    rows?: string[][];
    tabs?: Array<{ id?: string; label: string; lang?: string; code: string }>;
    body?: string;
    items?: Array<{ id?: string; ico?: string; title?: string; desc?: string; text?: string; done?: boolean }>;
    expr?: { raw?: string };
    source?: string;
    url?: string;
    mimeType?: string;
};

export type PublishedPage = {
    title: string;
    subtitle: string | null;
    path: string;
    blocks: DocsBlock[];
    spaceName: string | null;
};

export type DocsShowProps = {
    site: DocsSite;
    release: DocsRelease;
    navigation: DocsNavigationNode[];
    searchIndex: DocsSearchIndexEntry[];
    page: PublishedPage;
    previousPage: DocsPageLink | null;
    nextPage: DocsPageLink | null;
};

export type NavigationGroup = {
    label: string;
    nodes: DocsNavigationNode[];
};

export type DocsHeading = {
    blockKey: string;
    id: string;
    label: string;
    level: string;
};

export type DocsThemeMetadata = {
    id: DocsThemeId;
    name: string;
    description: string;
    swatches: string[];
    styles: CSSProperties & Record<string, string>;
};

export type DocsThemeProps = DocsShowProps & {
    theme: DocsThemeMetadata;
    rootStyle: CSSProperties;
    groupedNavigation: NavigationGroup[];
    filteredNavigation: NavigationGroup[];
    navigationQuery: string;
    setNavigationQuery: (query: string) => void;
    headings: DocsHeading[];
    publishedDate: string | null;
    publishedDateTime: string | null;
};

export type DocsThemeDefinition = DocsThemeMetadata & {
    component: ComponentType<DocsThemeProps>;
};

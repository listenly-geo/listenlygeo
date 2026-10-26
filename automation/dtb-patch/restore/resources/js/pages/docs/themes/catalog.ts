export type DocsThemeId = 'mintlify' | 'gitbook' | 'fumadocs' | 'laravel';
export type DocsThemeAccentId = 'theme' | 'emerald' | 'blue' | 'amber' | 'violet' | 'rose';
export type DocsThemeFontId = 'inter' | 'system' | 'serif' | 'mono';
export type DocsThemeLayoutId = 'boxed' | 'full';

export type DocsThemeOptions = {
    accentColor: DocsThemeAccentId;
    fontFamily: DocsThemeFontId;
    layoutWidth: DocsThemeLayoutId;
};

export type DocsThemeOption = {
    id: DocsThemeId;
    name: string;
    description: string;
    swatches: string[];
};

export const docsThemeOptions: DocsThemeOption[] = [
    {
        id: 'mintlify',
        name: 'Mintlify',
        description: 'Modern product docs with a centered content column, clean rails, and emerald accents.',
        swatches: ['#ffffff', '#f8fafc', '#059669'],
    },
    {
        id: 'gitbook',
        name: 'GitBook',
        description: 'A broad documentation portal layout with top navigation, orange accents, and a strong left guide rail.',
        swatches: ['#ffffff', '#f7f7f5', '#ff4f1f'],
    },
    {
        id: 'fumadocs',
        name: 'Fumadocs',
        description: 'A compact framework-style reader with a fixed left workspace, neutral surfaces, and amber highlights.',
        swatches: ['#f7f7f6', '#ffffff', '#d28a00'],
    },
    {
        id: 'laravel',
        name: 'Laravel',
        description: 'Classic Laravel-docs layout with a left chapter rail, inline search, right TOC, and signature red accents.',
        swatches: ['#ffffff', '#f9f9f9', '#FF2D20'],
    },
];

export const docsThemeIds = docsThemeOptions.map((theme) => theme.id);

export const normalizeDocsTheme = (theme: DocsThemeId | string | null | undefined): DocsThemeId => (
    docsThemeIds.includes(theme as DocsThemeId) ? theme as DocsThemeId : 'mintlify'
);

export const docsThemeAccentOptions: Array<{
    id: DocsThemeAccentId;
    name: string;
    swatch: string;
    styles?: Record<string, string>;
}> = [
    { id: 'theme', name: 'Theme default', swatch: 'linear-gradient(135deg, #059669, #ff4f1f, #d28a00)' },
    {
        id: 'emerald',
        name: 'Emerald',
        swatch: '#059669',
        styles: {
            '--docs-accent': '#059669',
            '--docs-accent-soft': '#ecfdf5',
            '--docs-accent-text': '#047857',
            '--docs-accent-ring': '#a7f3d0',
        },
    },
    {
        id: 'blue',
        name: 'Blue',
        swatch: '#2563eb',
        styles: {
            '--docs-accent': '#2563eb',
            '--docs-accent-soft': '#eff6ff',
            '--docs-accent-text': '#1d4ed8',
            '--docs-accent-ring': '#bfdbfe',
        },
    },
    {
        id: 'amber',
        name: 'Amber',
        swatch: '#d97706',
        styles: {
            '--docs-accent': '#d97706',
            '--docs-accent-soft': '#fffbeb',
            '--docs-accent-text': '#b45309',
            '--docs-accent-ring': '#fde68a',
        },
    },
    {
        id: 'violet',
        name: 'Violet',
        swatch: '#7c3aed',
        styles: {
            '--docs-accent': '#7c3aed',
            '--docs-accent-soft': '#f5f3ff',
            '--docs-accent-text': '#6d28d9',
            '--docs-accent-ring': '#ddd6fe',
        },
    },
    {
        id: 'rose',
        name: 'Rose',
        swatch: '#e11d48',
        styles: {
            '--docs-accent': '#e11d48',
            '--docs-accent-soft': '#fff1f2',
            '--docs-accent-text': '#be123c',
            '--docs-accent-ring': '#fecdd3',
        },
    },
];

export const docsThemeFontOptions: Array<{
    id: DocsThemeFontId;
    name: string;
    css: string;
}> = [
    { id: 'inter', name: 'Inter', css: 'Inter, ui-sans-serif, system-ui, sans-serif' },
    { id: 'system', name: 'System', css: 'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' },
    { id: 'serif', name: 'Serif', css: 'Georgia, Cambria, "Times New Roman", serif' },
    { id: 'mono', name: 'Mono', css: '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace' },
];

export const docsThemeLayoutOptions: Array<{
    id: DocsThemeLayoutId;
    name: string;
    description: string;
}> = [
    { id: 'boxed', name: 'Boxed', description: 'Keep the reader content centered with comfortable line length.' },
    { id: 'full', name: 'Full width', description: 'Stretch the reader shell and content area across wider screens.' },
];

export const defaultDocsThemeOptions: DocsThemeOptions = {
    accentColor: 'theme',
    fontFamily: 'inter',
    layoutWidth: 'boxed',
};

export const normalizeDocsThemeOptions = (options: Partial<DocsThemeOptions> | null | undefined): DocsThemeOptions => {
    const accentColor = options?.accentColor;
    const fontFamily = options?.fontFamily;
    const layoutWidth = options?.layoutWidth;

    return {
        accentColor: docsThemeAccentOptions.some((option) => option.id === accentColor) ? accentColor as DocsThemeAccentId : defaultDocsThemeOptions.accentColor,
        fontFamily: docsThemeFontOptions.some((option) => option.id === fontFamily) ? fontFamily as DocsThemeFontId : defaultDocsThemeOptions.fontFamily,
        layoutWidth: docsThemeLayoutOptions.some((option) => option.id === layoutWidth) ? layoutWidth as DocsThemeLayoutId : defaultDocsThemeOptions.layoutWidth,
    };
};

export const resolveDocsThemeOptionStyles = (options: Partial<DocsThemeOptions> | null | undefined): Record<string, string> => {
    const normalized = normalizeDocsThemeOptions(options);
    const accentOption = docsThemeAccentOptions.find((option) => option.id === normalized.accentColor);

    return accentOption?.styles ?? {};
};

export const resolveDocsThemeFontFamily = (options: Partial<DocsThemeOptions> | null | undefined): string => {
    const normalized = normalizeDocsThemeOptions(options);

    return docsThemeFontOptions.find((option) => option.id === normalized.fontFamily)?.css ?? docsThemeFontOptions[0].css;
};

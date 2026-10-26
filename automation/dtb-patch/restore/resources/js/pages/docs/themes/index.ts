import { docsThemeOptions, normalizeDocsTheme } from './catalog';
import type { DocsThemeId } from './catalog';
import { fumadocsTheme } from './fumadocs';
import { gitbookTheme } from './gitbook';
import { laravelTheme } from './laravel';
import { mintlifyTheme } from './mintlify';
import type { DocsThemeDefinition } from './types';

export { docsThemeOptions, normalizeDocsTheme };
export type { DocsThemeId } from './catalog';
export type { DocsShowProps } from './types';

export const docsThemeDefinitions: Record<DocsThemeId, DocsThemeDefinition> = {
    mintlify: mintlifyTheme,
    gitbook: gitbookTheme,
    fumadocs: fumadocsTheme,
    laravel: laravelTheme,
};

export const resolveDocsTheme = (theme: DocsThemeId | string | null | undefined): DocsThemeDefinition => (
    docsThemeDefinitions[normalizeDocsTheme(theme)]
);

export const docsThemeMetadata = docsThemeOptions.map((option) => {
    const definition = docsThemeDefinitions[option.id];

    return {
        id: definition.id,
        name: definition.name,
        description: definition.description,
        swatches: definition.swatches,
    };
});

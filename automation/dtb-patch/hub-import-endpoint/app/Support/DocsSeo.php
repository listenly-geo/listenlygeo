<?php

namespace App\Support;

use Illuminate\Support\Arr;
use Illuminate\Support\Str;

/**
 * Indexation des pages publiees de l'Index (15/11/2026) : titre, description, adresse officielle (canonical),
 * donnees structurees, et texte lisible SANS JavaScript (robots des IA). Tout est calcule cote serveur.
 */
class DocsSeo
{
    /** Adresse publique d'une page. Le domaine du client n'est utilise que si l'app sait servir ce domaine (config app.docs_custom_domains). */
    public static function pageUrl(array $site, string $path): string
    {
        $path = trim($path, '/');
        $host = (bool) config('app.docs_custom_domains', false) ? ($site['primaryDomain'] ?? null) : null;
        if ($host) {
            return 'https://'.$host.($path === '' ? '/' : '/'.$path);
        }
        $url = rtrim((string) config('app.url'), '/').'/docs/'.$site['slug'];

        return $path === '' ? $url : $url.'/'.$path;
    }

    /** @return array{title:string, head:string, noscript:string} */
    public static function build(array $payload, bool $noindex = false): array
    {
        $site = (array) ($payload['site'] ?? []);
        $page = (array) ($payload['page'] ?? []);
        $release = (array) ($payload['release'] ?? []);
        $brand = trim((string) ($site['brandName'] ?? $site['name'] ?? ''));
        $path = trim((string) ($page['path'] ?? ''), '/');
        $isHome = $path === '';
        $url = self::pageUrl($site, $path);
        $blocks = self::plain((array) ($page['blocks'] ?? []));

        $pageTitle = trim((string) ($page['title'] ?? $brand));
        if ($isHome) {
            $title = trim((string) ($site['seoTitle'] ?? '')) ?: trim($brand.(($site['tagline'] ?? '') !== '' ? ' - '.$site['tagline'] : ''));
        } else {
            $title = Str::length($pageTitle.' | '.$brand) <= 70 ? $pageTitle.' | '.$brand : $pageTitle;
        }

        $description = trim((string) ($page['subtitle'] ?? ''));
        if ($description === '') {
            foreach ($blocks as $b) {
                if (($b['k'] ?? '') === 'p' && Str::length($b['t']) > 40 && ! Str::startsWith($b['t'], 'Based on an episode')) {
                    $description = $b['t'];
                    break;
                }
            }
        }
        if ($description === '' && $isHome) {
            $description = trim((string) ($site['seoDescription'] ?? '')) ?: trim((string) ($site['tagline'] ?? ''));
        }
        $description = Str::limit(preg_replace('/\s+/u', ' ', $description) ?? '', 155, '…');

        $published = $release['publishedAt'] ?? null;
        $lang = str_replace('_', '-', app()->getLocale());
        $org = ['@type' => 'Organization', 'name' => $brand];
        $crumbs = [['@type' => 'ListItem', 'position' => 1, 'name' => $brand, 'item' => self::pageUrl($site, '')]];
        if (! $isHome) {
            $crumbs[] = ['@type' => 'ListItem', 'position' => 2, 'name' => $pageTitle, 'item' => $url];
        }
        $graph = [
            $isHome
                ? ['@type' => 'CollectionPage', 'name' => $title, 'description' => $description, 'url' => $url, 'inLanguage' => $lang]
                : array_filter([
                    '@type' => 'Article',
                    'headline' => Str::limit($pageTitle, 110, ''),
                    'description' => $description,
                    'mainEntityOfPage' => $url,
                    'url' => $url,
                    'inLanguage' => $lang,
                    'datePublished' => $published,
                    'dateModified' => $published,
                    'author' => $org,
                    'publisher' => $org,
                ]),
            ['@type' => 'BreadcrumbList', 'itemListElement' => $crumbs],
        ];
        $ld = json_encode(['@context' => 'https://schema.org', '@graph' => $graph], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT);

        $e = fn (string $v): string => htmlspecialchars($v, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
        $head = '<meta name="description" content="'.$e($description).'">'."\n"
            .'<link rel="canonical" href="'.$e($url).'">'."\n"
            .'<meta name="robots" content="'.($noindex ? 'noindex,follow' : 'index,follow,max-image-preview:large,max-snippet:-1').'">'."\n"
            .'<meta property="og:type" content="'.($isHome ? 'website' : 'article').'">'."\n"
            .'<meta property="og:title" content="'.$e($title).'">'."\n"
            .'<meta property="og:description" content="'.$e($description).'">'."\n"
            .'<meta property="og:url" content="'.$e($url).'">'."\n"
            .'<meta property="og:site_name" content="'.$e($brand).'">'."\n"
            .'<meta name="twitter:card" content="summary">'."\n"
            .'<script type="application/ld+json">'.$ld.'</script>';

        return ['title' => $title, 'head' => $head, 'noscript' => self::noscript($site, $pageTitle, $blocks, (array) ($payload['navigation'] ?? []), $e)];
    }

    /** Texte simple des blocs : [['k' => 'h2|p|li', 't' => '...']]. */
    public static function plain(array $blocks): array
    {
        $out = [];
        $clean = function ($raw): string {
            $raw = str_ireplace(['</p>', '<br>', '<br/>', '<br />', '</li>'], "\n", (string) $raw);

            return trim(preg_replace('/[ \t]+/u', ' ', html_entity_decode(strip_tags($raw), ENT_QUOTES | ENT_HTML5, 'UTF-8')) ?? '');
        };
        foreach ($blocks as $b) {
            if (! is_array($b)) {
                continue;
            }
            $kind = (string) ($b['kind'] ?? '');
            if (preg_match('/^h[1-6]$/', $kind) === 1) {
                $t = $clean($b['text'] ?? '');
                if ($t !== '') {
                    $out[] = ['k' => $kind, 't' => $t];
                }
            } elseif (isset($b['items']) && is_array($b['items'])) {
                foreach ($b['items'] as $it) {
                    $t = $clean(is_array($it) ? ($it['text'] ?? '') : $it);
                    if ($t !== '') {
                        $out[] = ['k' => 'li', 't' => $t];
                    }
                }
            } elseif ($kind === 'listenly-audio') {
                continue;
            } else {
                foreach (preg_split('/\n+/u', $clean($b['html'] ?? $b['text'] ?? '')) ?: [] as $line) {
                    if (trim($line) !== '') {
                        $out[] = ['k' => 'p', 't' => trim($line)];
                    }
                }
            }
        }

        return $out;
    }

    private static function noscript(array $site, string $pageTitle, array $blocks, array $navigation, callable $e): string
    {
        $html = '<main><h1>'.$e($pageTitle).'</h1>';
        $openList = false;
        foreach ($blocks as $b) {
            if ($b['k'] === 'li') {
                if (! $openList) {
                    $html .= '<ul>';
                    $openList = true;
                }
                $html .= '<li>'.$e($b['t']).'</li>';
                continue;
            }
            if ($openList) {
                $html .= '</ul>';
                $openList = false;
            }
            $tag = $b['k'] === 'p' ? 'p' : $b['k'];
            $html .= '<'.$tag.'>'.$e($b['t']).'</'.$tag.'>';
        }
        if ($openList) {
            $html .= '</ul>';
        }
        $links = [];
        $walk = function (array $nodes) use (&$walk, &$links, $site): void {
            foreach ($nodes as $n) {
                if (count($links) >= 300) {
                    return;
                }
                if (! empty($n['path'])) {
                    $links[] = '<li><a href="'.htmlspecialchars(self::pageUrl($site, (string) $n['path']), ENT_QUOTES, 'UTF-8').'">'.htmlspecialchars((string) ($n['title'] ?? $n['path']), ENT_QUOTES, 'UTF-8').'</a></li>';
                }
                $walk((array) ($n['children'] ?? []));
            }
        };
        $walk($navigation);
        if ($links !== []) {
            $html .= '<nav><h2>More answers</h2><ul>'.implode('', $links).'</ul></nav>';
        }

        return $html.'</main>';
    }
}

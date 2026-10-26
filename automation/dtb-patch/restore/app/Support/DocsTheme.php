<?php

namespace App\Support;

final class DocsTheme
{
    public const DEFAULT = 'mintlify';

    public const DEFAULT_ACCENT_COLOR = 'theme';

    public const DEFAULT_FONT_FAMILY = 'inter';

    public const DEFAULT_LAYOUT_WIDTH = 'boxed';

    private const IDS = [
        'mintlify',
        'gitbook',
        'fumadocs',
        'laravel',
    ];

    private const ACCENT_COLORS = [
        'theme',
        'emerald',
        'blue',
        'amber',
        'violet',
        'rose',
    ];

    private const FONT_FAMILIES = [
        'inter',
        'system',
        'serif',
        'mono',
    ];

    private const LAYOUT_WIDTHS = [
        'boxed',
        'full',
    ];

    /**
     * @return array<int, string>
     */
    public static function ids(): array
    {
        return self::IDS;
    }

    /**
     * @return array<int, string>
     */
    public static function accentColors(): array
    {
        return self::ACCENT_COLORS;
    }

    /**
     * @return array<int, string>
     */
    public static function fontFamilies(): array
    {
        return self::FONT_FAMILIES;
    }

    /**
     * @return array<int, string>
     */
    public static function layoutWidths(): array
    {
        return self::LAYOUT_WIDTHS;
    }

    public static function normalize(?string $theme): string
    {
        return in_array($theme, self::IDS, true) ? $theme : self::DEFAULT;
    }

    /**
     * @return array{accent_color: string, font_family: string, layout_width: string}
     */
    public static function normalizeOptions(mixed $options): array
    {
        $options = is_array($options) ? $options : [];
        $accentColor = $options['accent_color'] ?? null;
        $fontFamily = $options['font_family'] ?? null;
        $layoutWidth = $options['layout_width'] ?? null;

        return [
            'accent_color' => in_array($accentColor, self::ACCENT_COLORS, true) ? $accentColor : self::DEFAULT_ACCENT_COLOR,
            'font_family' => in_array($fontFamily, self::FONT_FAMILIES, true) ? $fontFamily : self::DEFAULT_FONT_FAMILY,
            'layout_width' => in_array($layoutWidth, self::LAYOUT_WIDTHS, true) ? $layoutWidth : self::DEFAULT_LAYOUT_WIDTH,
        ];
    }

    /**
     * @return array{accentColor: string, fontFamily: string, layoutWidth: string}
     */
    public static function optionsPayload(mixed $options): array
    {
        $normalized = self::normalizeOptions($options);

        return [
            'accentColor' => $normalized['accent_color'],
            'fontFamily' => $normalized['font_family'],
            'layoutWidth' => $normalized['layout_width'],
        ];
    }
}

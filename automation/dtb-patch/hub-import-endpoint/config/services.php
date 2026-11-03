<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Third Party Services
    |--------------------------------------------------------------------------
    |
    | This file is for storing the credentials for third party services such
    | as Mailgun, Postmark, AWS and more. This file provides the de facto
    | location for this type of information, allowing packages to have
    | a conventional file to locate the various service credentials.
    |
    */

    'postmark' => [
        'key' => env('POSTMARK_API_KEY'),
    ],

    'resend' => [
        'key' => env('RESEND_API_KEY'),
    ],

    'ses' => [
        'key' => env('AWS_ACCESS_KEY_ID'),
        'secret' => env('AWS_SECRET_ACCESS_KEY'),
        'region' => env('AWS_DEFAULT_REGION', 'us-east-1'),
    ],

    'slack' => [
        'notifications' => [
            'bot_user_oauth_token' => env('SLACK_BOT_USER_OAUTH_TOKEN'),
            'channel' => env('SLACK_BOT_USER_DEFAULT_CHANNEL'),
        ],
    ],

    'openrouter' => [
        'api_key' => env('OPENROUTER_API_KEY'),
        'base_url' => env('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1'),
        'model' => env('OPENROUTER_MODEL', 'poolside/laguna-m.1:free'),
        'fallback_models' => array_values(array_filter(array_map(
            static fn (string $value): string => trim($value),
            explode(',', (string) env('OPENROUTER_FALLBACK_MODELS', 'poolside/laguna-xs.2:free'))
        ))),
        'site_url' => env('OPENROUTER_SITE_URL', env('APP_URL')),
        'app_name' => env('OPENROUTER_APP_NAME', env('APP_NAME', 'DocTheBuilder')),
        'fake' => env('OPENROUTER_FAKE_RESPONSES', false),
    ],

    'openai' => [
        'api_key' => env('OPENAI_API_KEY'),
        'base_url' => env('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
        'model' => env('OPENAI_MODEL', 'gpt-4o-mini'),
        'fallback_models' => array_values(array_filter(array_map(
            static fn (string $value): string => trim($value),
            explode(',', (string) env('OPENAI_FALLBACK_MODELS', 'gpt-4.1-mini'))
        ))),
    ],

    'textcortex' => [
        'api_key' => env('TEXTCORTEX_API_KEY'),
        'base_url' => env('TEXTCORTEX_BASE_URL', 'https://api.textcortex.com/v1'),
        'model' => env('TEXTCORTEX_MODEL', 'gemini-2-5-flash'),
    ],

    'ai_writer' => [
        'provider' => env('AI_WRITER_PROVIDER', 'openrouter'),
        'fake' => env('AI_WRITER_FAKE_RESPONSES', env('OPENROUTER_FAKE_RESPONSES', false)),
    ],

    'hub_import' => [
        'token' => env('HUB_IMPORT_TOKEN'),
    ],

    'stripe' => [
        'secret' => env('STRIPE_SECRET'),
        'webhook_secret' => env('STRIPE_WEBHOOK_SECRET'),
        'currency' => env('STRIPE_CURRENCY', 'usd'),
        'api_base' => env('STRIPE_API_BASE', 'https://api.stripe.com/v1'),
    ],

];

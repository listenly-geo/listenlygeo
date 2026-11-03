<?php

namespace App\Console\Commands;

use App\Actions\Docs\AutosavePageRevision;
use App\Actions\Docs\ManagePrototypePageTree;
use App\Actions\Docs\PublishSiteRelease;
use App\Models\Page;
use App\Models\Site;
use App\Models\User;
use Illuminate\Console\Command;
use Illuminate\Support\Str;

/**
 * Crée (ou met à jour) les pages de réponse d'un hub à partir d'un fichier JSON.
 *
 * Format attendu :
 * {
 *   "podcast": "Heroic Investing",
 *   "listenly_show_url": "https://listenly.org/...",
 *   "answers": [
 *     {
 *       "question": "What cash reserve should you keep?",
 *       "answer": "Keep 4 percent of the purchase price...",
 *       "episode": "282: The Free Lunch Metric Revisited",
 *       "guest": "David Porter",
 *       "audio_url": "https://traffic.libsyn.com/....mp3",
 *       "start_sec": 795,
 *       "listenly_url": "https://listenly.org/podcast-btb/m/heroic-investing-show/a6f3074a9a",
 *       "topic": "Risk"
 *     }
 *   ]
 * }
 */
class ImportHubAnswers extends Command
{
    protected $signature = 'hub:import
        {site : UUID ou slug du site}
        {file : Chemin du fichier JSON}
        {--user= : E-mail de l\'utilisateur qui signe les pages}
        {--publish : Publie une nouvelle version après l\'import}
        {--dry-run : Affiche ce qui serait créé sans rien écrire}';

    protected $description = 'Importe les réponses d\'un podcast comme pages de hub (format article)';

    public function handle(
        ManagePrototypePageTree $pages,
        AutosavePageRevision $autosave,
        PublishSiteRelease $publish,
    ): int {
        $site = Site::query()
            ->where('uuid', $this->argument('site'))
            ->orWhere('slug', $this->argument('site'))
            ->first();

        if (! $site) {
            $this->error('Site introuvable.');

            return self::FAILURE;
        }

        $user = User::query()->where('email', $this->option('user') ?: 'etienne.cugnet@marketforge.fr')->first();

        if (! $user) {
            $this->error('Utilisateur introuvable : vérifiez --user.');

            return self::FAILURE;
        }

        $data = json_decode((string) file_get_contents($this->argument('file')), true);

        if (! is_array($data) || empty($data['answers']) || ! is_array($data['answers'])) {
            $this->error('Fichier invalide : il faut une liste "answers".');

            return self::FAILURE;
        }

        $created = 0;
        $updated = 0;
        $skipped = 0;

        foreach ($data['answers'] as $index => $item) {
            $question = trim((string) ($item['question'] ?? ''));
            $answer = trim((string) ($item['answer'] ?? ''));

            if ($question === '' || mb_strlen($answer) < 200) {
                // Règle de qualité : une page sans réponse complète n'est pas publiée.
                $skipped++;
                $this->warn("Ignorée (réponse trop courte ou question vide) : #{$index}");

                continue;
            }

            if ($this->option('dry-run')) {
                $this->line("[dry-run] {$question}");
                $created++;

                continue;
            }

            $existing = Page::query()
                ->where('site_id', $site->id)
                ->where('title', Str::limit($question, 200, ''))
                ->first();

            $page = $existing ?: Page::query()->findOrFail(
                $pages->create($site, $user)['dbId'],
            );

            if ($existing) {
                $updated++;
            } else {
                $created++;
            }

            $blocks = $this->blocksFor($item, $data);

            $autosave($page, $user, [
                'title' => $question,
                'subtitle' => (string) ($item['guest'] ?? ''),
                'blocks' => $blocks,
                'editorMeta' => ['readTime' => $this->readTime($answer)],
            ]);
        }

        // Retire la page d'exemple du logiciel, seulement si des réponses ont été importées.
        if (! $this->option('dry-run') && ($created + $updated) > 0) {
            Page::query()->where('site_id', $site->id)->where('path', 'quickstart')->get()->each->delete();
        }

        $this->info("Pages créées : {$created} · mises à jour : {$updated} · ignorées : {$skipped}");

        if ($this->option('publish') && ! $this->option('dry-run')) {
            $release = $publish($site, $user, ['environment' => 'production', 'message' => 'Import '.now()->toDateString()]);
            $this->info('Version publiée : '.($release['version'] ?? 'ok'));
        }

        return self::SUCCESS;
    }

    /**
     * @return array<int, array<string, mixed>>
     */
    private function blocksFor(array $item, array $data): array
    {
        $blocks = [];
        $paragraphs = array_values(array_filter(
            preg_split('/\n\s*\n/', trim((string) $item['answer'])) ?: [],
            fn (string $p): bool => trim($p) !== '',
        ));

        // 1. Chapeau : premier paragraphe de la reponse, en lead.
        if ($paragraphs !== []) {
            $blocks[] = [
                'id' => 'p_'.Str::random(8),
                'kind' => 'p',
                'html' => '<strong>'.e(trim(array_shift($paragraphs))).'</strong>',
            ];
        }

        // 2. Extrait audio de l'episode (lecteur du Hub).
        if (! empty($item['audio_url'])) {
            $blocks[] = [
                'id' => 'a_'.Str::random(8),
                'kind' => 'listenly-audio',
                'audioUrl' => (string) $item['audio_url'],
                'startSec' => (int) ($item['start_sec'] ?? 0),
                'episode' => (string) ($item['episode'] ?? ''),
                'podcast' => (string) ($data['podcast'] ?? ''),
                'listenlyUrl' => (string) ($item['listenly_url'] ?? ($data['listenly_show_url'] ?? '')),
            ];
        }

        // 3. Developpement : le reste de la reponse, sous un titre de section.
        if ($paragraphs !== []) {
            $blocks[] = ['id' => 'h_'.Str::random(8), 'kind' => 'h2', 'text' => e('Développement')];
            foreach ($paragraphs as $paragraph) {
                $blocks[] = ['id' => 'p_'.Str::random(8), 'kind' => 'p', 'html' => e(trim($paragraph))];
            }
        }

        // 4. Citation de l'intervenant, si fournie.
        if (! empty($item['quote'])) {
            $blocks[] = ['id' => 'q_'.Str::random(8), 'kind' => 'quote', 'html' => e((string) $item['quote'])];
        }

        // 5. Encart CTA vers le site du client (ou la cible indiquee).
        $cta = trim((string) ($item['cta_url'] ?? $data['cta_url'] ?? ''));
        if ($cta !== '' && preg_match('#^https?://#i', $cta)) {
            $ctaText = trim((string) ($item['cta_text'] ?? $data['cta_text'] ?? 'En savoir plus sur ce sujet'));
            $blocks[] = [
                'id' => 'c_'.Str::random(8),
                'kind' => 'callout',
                'variant' => 'info',
                'text' => '<a href="'.e($cta).'">'.e($ctaText).' &rarr;</a>',
            ];
        }

        return $blocks;
    }

    private function readTime(string $text): string
    {
        $minutes = max(1, (int) ceil(str_word_count($text) / 220));

        return $minutes.' min';
    }
}

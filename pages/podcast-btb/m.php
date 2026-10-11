<?php
/**
 * Page "moment" rendue cote serveur : listenly.fr/podcast-btb/m/<podcast>/<id>
 * Reprend l'accueil (m-template.html) et remplace titre, canonical, balisage Google, puis ecrit
 * la question + reponse + horaire en texte. Le lecteur est deja place au bon moment (sans lecture auto).
 * Donnees : data/moments/<podcast>.json (ecrit par moments_index.py). Aucun fichier par moment.
 * Lecture seule, aucun acces hors de data/moments/.
 */
$slug = preg_replace('/[^a-z0-9\-]/i', '', $_GET['p'] ?? '');
$mid  = preg_replace('/[^a-f0-9]/i', '', $_GET['m'] ?? '');
$base = __DIR__;

function gone($code, $msg) {
    http_response_code($code);
    header('Content-Type: text/plain; charset=utf-8');
    header('X-Robots-Tag: noindex');
    echo $msg;
    exit;
}

if ($slug === '' || $mid === '') gone(404, 'Not found');
$file = $base . '/data/moments/' . $slug . '.json';
if (!is_file($file)) gone(404, 'Not found');
$d = json_decode(file_get_contents($file), true);
$e = $d['entries'][$mid] ?? null;
if (!is_array($e)) gone(404, 'Not found');
$tpl = @file_get_contents($base . '/m-template.html');
if ($tpl === false) gone(500, 'Template missing');

$h = function ($s) { return htmlspecialchars((string)$s, ENT_QUOTES | ENT_HTML5, 'UTF-8'); };
$q   = trim($e['q'] ?? '');
$a   = trim($e['a'] ?? '');
$t   = max(0, (int)($e['t'] ?? 0));
$ts  = floor($t / 60) . ':' . str_pad((string)($t % 60), 2, '0', STR_PAD_LEFT);
$pod = $d['podcast'] ?? $slug;
$epi = $e['e'] ?? '';
$who = $e['x'] ?? '';
$epUrl = (preg_match('#^https://listenly\.fr/#', $e['l'] ?? '')) ? $e['l'] : '';
$hub = (preg_match('#^/podcast-btb/[a-z0-9\-]+\.html$#i', $d['hub'] ?? '')) ? 'https://listenly.fr' . $d['hub'] : '';
$audio = (preg_match('#^https?://#', $e['u'] ?? '')) ? $e['u'] : '';
if ($q === '' || $audio === '') gone(404, 'Not found');

$url = 'https://listenly.fr/podcast-btb/m/' . $slug . '/' . $mid;
// Page fine (pas de vraie reponse, pas d'horaire ou pas de nom d'invite) : accessible mais jamais indexee.
$thin = (mb_strlen($a) < 80 || $t <= 0 || trim($who) === '');
$title = $t > 0 ? $q . ' — answer at ' . $ts . ' | Listenly' : $q . ' | Listenly';
$desc  = $t > 0 ? $q . ' Answered at ' . $ts . ' in ' . $epi . ' (' . $pod . '). Listen from the exact moment.'
                : $q . ' Answered in ' . $epi . ' (' . $pod . ').';
$ld = ['@context' => 'https://schema.org', '@type' => 'Question', 'name' => $q, 'url' => $url,
  'acceptedAnswer' => ['@type' => 'Answer', 'text' => $a !== '' ? $a : $q, 'url' => $url],
  'about' => ['@type' => 'PodcastEpisode', 'name' => $epi, 'url' => $epUrl,
    'partOfSeries' => ['@type' => 'PodcastSeries', 'name' => $pod, 'url' => $d['show'] ?? '']]];
$ldJson = str_replace('</', '<\/', json_encode($ld, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

$tpl = preg_replace('#<title>.*?</title>#s', '<title>' . $h($title) . '</title>', $tpl, 1);
$tpl = preg_replace('#<meta name="description"[^>]*>#', '<meta name="description" content="' . $h($desc) . '">', $tpl, 1);
$tpl = str_replace('<link rel="canonical" href="https://listenly.fr/">', '<link rel="canonical" href="' . $h($url) . '">', $tpl);
$tpl = str_replace('<meta property="og:url" content="https://listenly.fr/">', '<meta property="og:url" content="' . $h($url) . '">', $tpl);
$tpl = preg_replace('#<meta property="og:title"[^>]*>#', '<meta property="og:title" content="' . $h($q) . '">', $tpl, 1);
$tpl = preg_replace('#<script type="application/ld\+json">.*?</script>#s', '<script type="application/ld+json">' . $ldJson . '</script>', $tpl, 1);

$card = '<div class="result-card"><h2 class="rc-question" style="font-size:22px">' . $h($q) . '</h2>'
  . '<p class="rc-excerpt">' . ($t > 0 ? '<strong style="color:#F5F5F7">Answer at ' . $h($ts) . '</strong> · ' : '') . $h($epi)
  . ($a !== '' ? '<br><br>' . $h($a) : '') . '</p>'
  . '<div class="rc-meta"><span class="rc-source"><strong>' . $h($who !== '' ? $who : 'Unknown') . '</strong> on ' . $h($pod) . '</span>'
  . '<span style="display:inline-flex;gap:14px;align-items:center;flex-wrap:wrap;">'
  . ($epUrl ? '<a href="' . $h($epUrl) . '" class="rc-play" style="text-decoration:none;">Episode page →</a>' : '')
  . ($hub ? '<a href="' . $h($hub) . '" class="rc-play" style="text-decoration:none;">All answers from this podcast →</a>' : '')
  . '<button class="rc-play" id="momentPlay">▶ Listen' . ($t > 0 ? ' at ' . $h($ts) : '') . '</button></span></div></div>';

$R = ['audio_url' => $audio, 'start_seconds' => $t, 'episode' => $epi, 'expert' => $who, 'podcast' => $pod];
$Rjson = str_replace('</', '<\/', json_encode($R, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
$boot = '<script>(function(){var R=' . $Rjson . ';'
  . "document.getElementById('momentPlay').addEventListener('click',function(){playAnswer(R,this);});"
  . "pbAudio.src=R.audio_url;pbTitle.textContent=R.episode;pbSub.textContent=(R.expert||'Unknown')+' on '+R.podcast;"
  . "playerBar.classList.add('active');updatePlayerBodyPadding();"
  . "pbAudio.addEventListener('loadedmetadata',function f(){pbAudio.currentTime=R.start_seconds;pbAudio.removeEventListener('loadedmetadata',f);});pbAudio.load();})();</script>";

$tpl = str_replace('<!--MOMENT_CARD-->', $card, $tpl);
$tpl = str_replace('<!--MOMENT_BOOT-->', $boot, $tpl);

if ($thin) {
    header('X-Robots-Tag: noindex, follow');
    $tpl = str_replace('</head>', '<meta name="robots" content="noindex,follow"></head>', $tpl);
}
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: public, max-age=3600');
echo $tpl;

<?php
/**
 * Page "moment" rendue cote serveur : listenly.org/podcast-btb/m/<podcast>/<id>
 * Reprend l'accueil (m-template.html) et remplace titre, H1, canonical, balisage Google, puis ecrit
 * la reponse complete, les chiffres, la citation, les personnes citees et les autres reponses du meme episode.
 * Le lecteur est deja place au bon moment (sans lecture auto).
 * Donnees : data/moments/<podcast>.json (ecrit par moments_index.py). Aucun fichier par moment.
 * Regle "page fine -> noindex" : la meme que generate_moments_sitemap.py (a garder identique).
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
function wc($s) { return count(preg_split('/\s+/u', trim((string)$s), -1, PREG_SPLIT_NO_EMPTY)); }
function mmss($t) { return floor($t / 60) . ':' . str_pad((string)($t % 60), 2, '0', STR_PAD_LEFT); }

if ($slug === '' || $mid === '') gone(404, 'Not found');
$file = $base . '/data/moments/' . $slug . '.json';
if (!is_file($file)) gone(404, 'Not found');
$d = json_decode(file_get_contents($file), true);
$e = $d['entries'][$mid] ?? null;
if (!is_array($e)) gone(404, 'Not found');
$mscores = @json_decode(@file_get_contents($base . '/data/moments_scores.json'), true) ?: [];
// (format plat : cle = slug/id) -> normalise
$mscores = ['entries' => $mscores];
$tpl = @file_get_contents($base . '/m-template.html');
if ($tpl === false) gone(500, 'Template missing');

$h = function ($s) { return htmlspecialchars((string)$s, ENT_QUOTES | ENT_HTML5, 'UTF-8'); };
$q   = trim($e['q'] ?? '');
$t   = max(0, (int)($e['t'] ?? 0));
$te  = (int)($e['te'] ?? 0);
$ts  = mmss($t);
$pod = $d['podcast'] ?? $slug;
$epi = $e['e'] ?? '';
$who = trim($e['x'] ?? '');
$role = trim($e['gt'] ?? '');
$epUrl = (preg_match('#^https://listenly\.fr/#', $e['l'] ?? '')) ? $e['l'] : '';
$hub = (preg_match('#^/podcast-btb/[a-z0-9\-]+\.html$#i', $d['hub'] ?? '')) ? 'https://listenly.org' . $d['hub'] : '';
$audio = (preg_match('#^https?://#', $e['u'] ?? '')) ? $e['u'] : '';
if ($q === '' || $audio === '') gone(404, 'Not found');

// Reponse : paragraphes complets si connus, sinon le texte court
$paras = [];
if (!empty($e['f']) && is_array($e['f'])) { foreach ($e['f'] as $p) { $p = trim(preg_replace('/\s+([.,;:!?])/u', '$1', (string)$p)); if ($p !== '') $paras[] = $p; } }
if (!$paras && trim($e['a'] ?? '') !== '') $paras[] = trim($e['a']);
$answerText = implode(' ', $paras);
$stats = array_values(array_filter(array_map('trim', (array)($e['ks'] ?? []))));
$ents  = array_values(array_filter(array_map('trim', (array)($e['en'] ?? []))));
$quote = trim($e['rq'] ?? '');

// Autres reponses du meme episode (maillage interne), uniquement celles qui ont une vraie reponse et un horaire
$related = [];
foreach ($d['entries'] as $oid => $o) {
    if ($oid === $mid || !is_array($o) || ($o['e'] ?? '') !== $epi) continue;
    if ((int)($o['t'] ?? 0) <= 0 || mb_strlen(trim($o['a'] ?? '')) < 80 || trim($o['q'] ?? '') === '') continue;
    $related[] = ['id' => $oid, 't' => (int)$o['t'], 'q' => trim($o['q'])];
}
usort($related, function ($a, $b) { return $a['t'] <=> $b['t']; });

// Regle de richesse (identique a generate_moments_sitemap.py) : une page trop fine reste accessible mais en noindex
$score = wc($answerText) + wc(implode(' ', $stats)) + wc($quote) + 8 * min(count($related), 4);
$thin = (wc($answerText) < 25 || $score < 90 || $t <= 0 || $who === '');
// Moteur autonome (15/10/2026) : seule la porte d'entree (2 paragraphes + score >= 70) est indexable.
$mscore = $mscores['entries'][$slug . '/' . $mid] ?? null;
if (is_array($mscore) && empty($mscore['gate'])) { $thin = true; }

$url = 'https://listenly.org/podcast-btb/m/' . $slug . '/' . $mid;
$title = $t > 0 ? $q . ' — answer at ' . $ts . ' | Listenly' : $q . ' | Listenly';
// Titre SEO affine (data/titres_seo.json, cle slug/id) : seul le <title> change, le H1 reste la question
$ovr = @json_decode(@file_get_contents($base . '/data/titres_seo.json'), true)['titres'] ?? [];
if (!empty($ovr[$slug . '/' . $mid])) { $title = $ovr[$slug . '/' . $mid]; }
$desc  = $t > 0 ? $q . ' Answered at ' . $ts . ' in ' . $epi . ' (' . $pod . '). Listen from the exact moment.'
                : $q . ' Answered in ' . $epi . ' (' . $pod . ').';
$ans = ['@type' => 'Answer', 'text' => mb_substr($answerText !== '' ? $answerText : $q, 0, 1800), 'url' => $url];
if ($who !== '') { $ans['author'] = ['@type' => 'Person', 'name' => $who] + ($role !== '' ? ['jobTitle' => $role] : []); }
$ld = ['@context' => 'https://schema.org', '@type' => 'Question', 'publisher' => ['@type' => 'Organization', 'name' => 'Listenly', 'url' => 'https://listenly.org/', 'description' => 'Annuaire de podcasts B2B : trouvez le moment exact d\'un épisode où un expert répond à votre question.'], 'name' => $q, 'url' => $url, 'acceptedAnswer' => $ans,
  'about' => ['@type' => 'PodcastEpisode', 'name' => $epi, 'url' => $epUrl,
    'partOfSeries' => ['@type' => 'PodcastSeries', 'name' => $pod, 'url' => $d['show'] ?? '']]];
if ($ents) { $ld['mentions'] = array_map(function ($n) { return ['@type' => 'Thing', 'name' => $n]; }, array_slice($ents, 0, 8)); }
$ldJson = str_replace('</', '<\/', json_encode($ld, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

$tpl = preg_replace('#<title>.*?</title>#s', '<title>' . $h($title) . '</title>', $tpl, 1);
$tpl = preg_replace('#<meta name="description"[^>]*>#', '<meta name="description" content="' . $h($desc) . '">', $tpl, 1);
$tpl = str_replace('<link rel="canonical" href="https://listenly.org/">', '<link rel="canonical" href="' . $h($url) . '">', $tpl);
$tpl = str_replace('<meta property="og:url" content="https://listenly.org/">', '<meta property="og:url" content="' . $h($url) . '">', $tpl);
$tpl = preg_replace('#<meta property="og:title"[^>]*>#', '<meta property="og:title" content="' . $h($q) . '">', $tpl, 1);
$tpl = preg_replace('#<script type="application/ld\+json">.*?</script>#s', '<script type="application/ld+json">' . $ldJson . '</script>', $tpl, 1);
// H1 = la question (le titre d'accueil devient un simple sous-titre de marque)
$tpl = preg_replace('#<h1>.*?</h1>#s', '<h1 style="font-size:clamp(26px,4vw,40px)">' . $h($q) . '</h1>', $tpl, 1);
$tpl = preg_replace('#<p class="sub">.*?</p>#s', '<p class="sub">' . ($t > 0 ? 'Answered at <strong style="color:#F5F5F7">' . $h($ts) . '</strong> in ' : 'Answered in ')
  . $h($epi) . ' · ' . $h($pod) . '</p>', $tpl, 1);

// Carte "reponse" rendue par le serveur : lue par Google et par les visiteurs sans JavaScript.
// Avec JavaScript, deeplink.js la remplace par l'affichage habituel de l'accueil (recap + lecteur + moments cles).
$card = '<div class="result-card"><p class="rc-question">' . $h($q) . '</p>';
foreach ($paras as $p) { $card .= '<p class="rc-excerpt">' . $h($p) . '</p>'; }
$card .= '<div class="rc-meta"><span class="rc-source"><strong>' . $h($who !== '' ? $who : 'Unknown') . '</strong> on ' . $h($pod) . '</span>'
  . '<span style="display:inline-flex;gap:14px;align-items:center;flex-wrap:wrap;">'
  . ($epUrl ? '<a href="' . $h($epUrl) . '" class="rc-play" style="text-decoration:none;">Episode page →</a>' : '')
  . ($hub ? '<a href="' . $h($hub) . '" class="rc-play" style="text-decoration:none;">All answers from this podcast →</a>' : '')
  . '</span></div></div>';

// Fiche complete, repliee : le texte reste dans la page (lisible par Google) et le visiteur la deplie s'il veut en savoir plus.
$sec = 'margin:22px 0 0;';
$lab = 'font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:#86868B;margin:0 0 10px;font-weight:600;';
$fiche = '<section class="mf-wrap"><style>'
  . '.mf-wrap{position:relative;z-index:1;max-width:640px;margin:-90px auto 120px;padding:0 24px}'
  . '.mf{background:#1C1C1E;border:1px solid rgba(255,255,255,.08);border-radius:16px;overflow:hidden}'
  . '.mf>summary{list-style:none;cursor:pointer;padding:18px 22px;display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:15px;font-weight:600;color:#F5F5F7}'
  . '.mf>summary::-webkit-details-marker{display:none}'
  . '.mf>summary small{display:block;font-weight:400;color:#86868B;font-size:12.5px;margin-top:2px}'
  . '.mf>summary .chev{flex:none;color:#86868B;transition:transform .2s}.mf[open]>summary .chev{transform:rotate(180deg)}'
  . '.mf-body{padding:4px 22px 24px;border-top:1px solid rgba(255,255,255,.08)}'
  . '.mf-body p{font-size:14.5px;line-height:1.65;color:#B5B5BA;margin:0 0 12px}'
  . '.mf-body ul{margin:0;padding-left:18px;font-size:14.5px;line-height:1.75;color:#B5B5BA}'
  . '.mf-body li{margin-bottom:4px}.mf-body a{color:#2997FF;text-decoration:none}.mf-body a:hover{opacity:.75}'
  . '.mf-body blockquote{margin:0;padding:6px 0 6px 16px;border-left:3px solid #2997FF;color:#F5F5F7;font-size:18px;line-height:1.5;font-style:italic}.mf-body ul.kt{list-style:none;padding:0}.mf-body ul.kt li{position:relative;padding-left:20px;margin-bottom:9px;color:#D2D2D7}.mf-body ul.kt li:before{content:\'\';position:absolute;left:2px;top:.62em;width:7px;height:7px;border-radius:50%;background:#2997FF}.mf-body>div+div{padding-top:22px;border-top:1px solid rgba(255,255,255,.06)}'
  . '.mf-body .t{display:inline-block;min-width:44px;margin-right:8px;padding:1px 8px;border-radius:999px;background:rgba(41,151,255,.14);color:#2997FF;font-size:12.5px;text-align:center}'
  . '.mf-body .tags span{display:inline-block;margin:0 6px 6px 0;padding:4px 11px;border-radius:999px;background:rgba(255,255,255,.07);color:#D2D2D7;font-size:13px}'
  . '@media (max-width:560px){.mf-wrap{padding:0 14px;margin-top:-70px}.mf>summary{padding:16px 16px}.mf-body{padding:4px 16px 20px}}'
  . '</style><details class="mf"><summary><span>Full answer and details<small>Read the whole answer, key facts and every other question from this episode</small></span>'
  . '<svg class="chev" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg></summary><div class="mf-body">';
// --- Resume structure : l'essentiel, les points a retenir, la citation, puis la reponse detaillee ---
$isHead = function ($p) { return mb_strlen($p) < 90 && !preg_match('/[.!?:]$/u', $p); };
$firstSentence = function ($p) {
    $parts = preg_split('/(?<=[.!?])\s+(?=[A-Z“"])/u', trim($p), 2);
    return trim($parts[0]);
};
$body = array_values(array_filter($paras, function ($p) use ($isHead) { return !$isHead($p); }));
$inShort = $body ? $firstSentence($body[0]) : '';
if (mb_strlen($inShort) > 260) { $inShort = rtrim(mb_substr($inShort, 0, 257), " ,;:") . '…'; }
$pull = $quote;                                      // citation de l'invite si l'extraction l'a trouvee, sinon une phrase entre guillemets de la reponse
if ($pull === '') {
    foreach ($paras as $p) { if (preg_match('/[“"]([^“”"]{40,240})[”"]/u', $p, $mq)) { $pull = trim($mq[1]); break; } }
}
$points = [];
foreach ($body as $i => $p) {
    $sent = $firstSentence($p);
    if ($i === 0 && count($body) > 1) {            // 1er paragraphe : deja repris dans "In short"
        $parts = preg_split('/(?<=[.!?])\s+(?=[A-Z“"])/u', trim($p));
        $sent = $parts[1] ?? '';
    }
    $sent = trim($sent, " \t\n\r\"“”");
    $inQuote = ($pull !== '' && (mb_stripos($pull, mb_substr($sent, 0, 40)) !== false || mb_stripos($sent, mb_substr($pull, 0, 40)) !== false));
    if (mb_strlen($sent) >= 40 && mb_strlen($sent) <= 260 && !$inQuote && !in_array($sent, $points, true)) { $points[] = $sent; }
}
$points = array_slice($points, 0, 5);
$H2 = 'font-size:20px;font-weight:650;color:#F5F5F7;margin:0 0 12px;letter-spacing:-.01em;';
$meta = $h($who !== '' ? $who : 'Guest') . ($role !== '' ? ', ' . $h($role) : '') . ' · ' . $h($epi) . ' · ' . $h($pod);

if ($inShort !== '') {
    $fiche .= '<div style="' . $sec . '"><h2 style="' . $H2 . '">In short</h2><p style="font-size:17px;line-height:1.55;color:#F5F5F7;margin:0 0 6px">' . $h($inShort) . '</p>'
      . '<p style="font-size:12.5px;color:#86868B;margin:0">' . $meta . ($t > 0 ? ' · answer at ' . $h($ts) : '') . '</p></div>';
}
if ($points) {
    $fiche .= '<div style="' . $sec . '"><h2 style="' . $H2 . '">Key takeaways</h2><ul class="kt">';
    foreach ($points as $x) { $fiche .= '<li>' . $h($x) . '</li>'; }
    $fiche .= '</ul></div>';
}
if ($pull !== '') {
    $fiche .= '<div style="' . $sec . '"><h2 style="' . $H2 . '">Quote to remember</h2><blockquote>“' . $h($pull) . '”</blockquote>'
      . ($who !== '' ? '<p style="font-size:12.5px;color:#86868B;margin:8px 0 0">— ' . $h($who) . '</p>' : '') . '</div>';
}
$fiche .= '<div style="' . $sec . '"><h2 style="' . $H2 . '">The full answer' . ($te > $t && $t > 0 ? ' <span style="font-size:13px;font-weight:400;color:#86868B">· about ' . max(1, round(($te - $t) / 60)) . ' min</span>' : '') . '</h2>';
foreach ($paras as $p) {
    if ($isHead($p)) { $fiche .= '<h3 style="font-size:15.5px;font-weight:600;color:#F5F5F7;margin:18px 0 6px">' . $h($p) . '</h3>'; }
    else { $fiche .= '<p>' . $h($p) . '</p>'; }
}
$fiche .= '</div>';
if ($stats) {
    $fiche .= '<div style="' . $sec . '"><h2 style="' . $H2 . '">Key facts</h2><ul class="kt">';
    foreach ($stats as $x) { $fiche .= '<li>' . $h($x) . '</li>'; }
    $fiche .= '</ul></div>';
}
if ($quote !== '') {
    $fiche .= '';
}
if ($ents) {
    $fiche .= '<div style="' . $sec . '"><h2 style="' . $H2 . '">People, companies and topics mentioned</h2><div class="tags">';
    foreach (array_slice($ents, 0, 8) as $x) { $fiche .= '<span>' . $h($x) . '</span>'; }
    $fiche .= '</div></div>';
}
if ($related) {
    $fiche .= '<div style="' . $sec . '"><h2 style="' . $H2 . '">More answers from this episode</h2><ul style="list-style:none;padding:0">';
    foreach (array_slice($related, 0, 12) as $r) {
        $fiche .= '<li><span class="t">' . $h(mmss($r['t'])) . '</span><a href="/podcast-btb/m/' . $h($slug) . '/' . $h($r['id']) . '">' . $h($r['q']) . '</a></li>';
    }
    $fiche .= '</ul></div>';
}
$fiche .= '<div style="' . $sec . 'font-size:14px">' . ($epUrl ? '<a href="' . $h($epUrl) . '">Open the full episode →</a>' : '')
  . ($hub ? ' &nbsp;·&nbsp; <a href="' . $h($hub) . '">All answers from ' . $h($pod) . ' →</a>' : '') . '</div>';
$fiche .= '</div></details></section>';

$tpl = str_replace('<!--MOMENT_CARD-->', $card, $tpl);
$tpl = str_replace('<!--MOMENT_FICHE-->', $fiche, $tpl);
if ($thin) {
    header('X-Robots-Tag: noindex, follow');
    $tpl = str_replace('</head>', '<meta name="robots" content="noindex,follow"></head>', $tpl);
}
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: public, max-age=300');
echo $tpl;

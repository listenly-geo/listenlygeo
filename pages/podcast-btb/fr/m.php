<?php
/**
 * Page "moment" FRANCAISE (generateur FR independant, 17/11/2026) : listenly.org/podcast-btb/fr/m/<podcast>/<id>
 * Page autonome (aucun fichier du moteur americain) : charte sombre Listenly, reponse complete, lecteur place au bon moment.
 * Donnees : fr/data/moments/<podcast>.json (ecrit par automation/fr/generate_fr.py).
 * Regle "page fine -> noindex" identique a celle du moteur americain (reponse >= 25 mots, richesse >= 90, horaire, invite).
 */
$slug = preg_replace('/[^a-z0-9\-]/i', '', $_GET['p'] ?? '');
$mid  = preg_replace('/[^a-f0-9]/i', '', $_GET['m'] ?? '');
$base = __DIR__;
function gone($code, $msg) { http_response_code($code); header('Content-Type: text/plain; charset=utf-8'); header('X-Robots-Tag: noindex'); echo $msg; exit; }
function wc($s) { return count(preg_split('/\s+/u', trim((string)$s), -1, PREG_SPLIT_NO_EMPTY)); }
function mmss($t) { return floor($t / 60) . ':' . str_pad((string)($t % 60), 2, '0', STR_PAD_LEFT); }
$h = function ($s) { return htmlspecialchars((string)$s, ENT_QUOTES | ENT_HTML5, 'UTF-8'); };
if ($slug === '' || $mid === '') gone(404, 'Introuvable');
$file = $base . '/data/moments/' . $slug . '.json';
if (!is_file($file)) gone(404, 'Introuvable');
$d = json_decode(file_get_contents($file), true);
$e = $d['entries'][$mid] ?? null;
if (!is_array($e)) gone(404, 'Introuvable');

$q = trim($e['q'] ?? ''); $t = max(0, (int)($e['t'] ?? 0)); $te = (int)($e['te'] ?? 0); $ts = mmss($t);
$pod = $d['podcast'] ?? $slug; $epi = $e['e'] ?? ''; $who = trim($e['x'] ?? ''); $role = trim($e['gt'] ?? '');
$audio = (preg_match('#^https?://#', $e['u'] ?? '')) ? $e['u'] : '';
$show = (preg_match('#^https://listenly\.(org|fr)/#', $d['show'] ?? '')) ? $d['show'] : '';
$hub = 'https://listenly.org/podcast-btb/fr/' . $slug . '.html';
$cover = (preg_match('#^https://#', $d['cover'] ?? '')) ? $d['cover'] : '';
if ($q === '' || $audio === '') gone(404, 'Introuvable');

$paras = [];
if (!empty($e['f']) && is_array($e['f'])) { foreach ($e['f'] as $p) { $p = trim(preg_replace('/\s+([.,;:!?])/u', '$1', (string)$p)); if ($p !== '') $paras[] = $p; } }
if (!$paras && trim($e['a'] ?? '') !== '') $paras[] = trim($e['a']);
$answerText = implode(' ', $paras);
$stats = array_values(array_filter(array_map('trim', (array)($e['ks'] ?? []))));
$ents  = array_values(array_filter(array_map('trim', (array)($e['en'] ?? []))));
$quote = trim($e['rq'] ?? '');
$related = [];
foreach ($d['entries'] as $oid => $o) {
    if ($oid === $mid || !is_array($o) || ($o['e'] ?? '') !== $epi) continue;
    if ((int)($o['t'] ?? 0) <= 0 || mb_strlen(trim($o['a'] ?? '')) < 80 || trim($o['q'] ?? '') === '') continue;
    $related[] = ['id' => $oid, 't' => (int)$o['t'], 'q' => trim($o['q'])];
}
usort($related, function ($a, $b) { return $a['t'] <=> $b['t']; });
$score = wc($answerText) + wc(implode(' ', $stats)) + wc($quote) + 8 * min(count($related), 4);
$thin = (wc($answerText) < 25 || $score < 90 || $t <= 0 || $who === '' || count($paras) < 2);

$url = 'https://listenly.org/podcast-btb/fr/m/' . $slug . '/' . $mid;
$title = trim($e['ts'] ?? '') !== '' ? trim($e['ts']) : $q . ' | Listenly';
$desc = $q . ' Réponse à ' . $ts . ' dans « ' . $epi . ' » (' . $pod . '). Écoutez à l\'instant exact.';
$ans = ['@type' => 'Answer', 'text' => mb_substr($answerText !== '' ? $answerText : $q, 0, 1800), 'url' => $url];
if ($who !== '') { $ans['author'] = ['@type' => 'Person', 'name' => $who] + ($role !== '' ? ['jobTitle' => $role] : []); }
$ld = ['@context' => 'https://schema.org', '@type' => 'Question', 'name' => $q, 'inLanguage' => 'fr', 'acceptedAnswer' => $ans,
  'publisher' => ['@type' => 'Organization', 'name' => 'Listenly', 'url' => 'https://listenly.org/'],
  'about' => ['@type' => 'PodcastEpisode', 'name' => $epi, 'partOfSeries' => ['@type' => 'PodcastSeries', 'name' => $pod, 'url' => $show]]];
if ($ents) { $ld['mentions'] = array_map(function ($n) { return ['@type' => 'Thing', 'name' => $n]; }, array_slice($ents, 0, 8)); }
$ldJson = str_replace('</', '<\/', json_encode($ld, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

if ($thin) { header('X-Robots-Tag: noindex, follow'); }
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: public, max-age=300');
?><!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title><?= $h($title) ?></title>
<meta name="description" content="<?= $h($desc) ?>">
<link rel="canonical" href="<?= $h($url) ?>">
<?php if ($thin): ?><meta name="robots" content="noindex,follow">
<?php endif; ?>
<meta property="og:type" content="article"><meta property="og:title" content="<?= $h($q) ?>"><meta property="og:url" content="<?= $h($url) ?>"><meta property="og:locale" content="fr_FR">
<script type="application/ld+json"><?= $ldJson ?></script>
<style>
:root{--bg:#000;--panel:#1C1C1E;--ink:#F5F5F7;--soft:#86868B;--line:rgba(255,255,255,.1);--accent:#2997FF}
*{box-sizing:border-box}html,body{margin:0}body{background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased;padding-bottom:96px}
a{color:var(--accent);text-decoration:none}a:hover{opacity:.8}
header{display:flex;align-items:center;justify-content:space-between;padding:16px clamp(16px,4vw,40px)}
header a.logo{color:var(--ink);font-weight:700;font-size:18px;letter-spacing:-.01em}
.wrap{max-width:720px;margin:0 auto;padding:8px 20px 40px}
.search{display:flex;gap:8px;margin:6px 0 26px}.search input{flex:1;background:var(--panel);border:1px solid var(--line);border-radius:999px;color:var(--ink);padding:13px 18px;font-size:15px;outline:none}.search input:focus{border-color:var(--accent)}
.search button{background:var(--accent);border:0;color:#fff;border-radius:999px;padding:0 20px;font-weight:600;cursor:pointer}
h1{font-size:clamp(26px,4vw,38px);line-height:1.18;letter-spacing:-.02em;margin:0 0 12px}
.sub{color:var(--soft);font-size:14.5px;margin:0 0 22px}.sub strong{color:var(--ink)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:22px;margin:0 0 18px}
.card p{font-size:16px;line-height:1.65;color:#D2D2D7;margin:0 0 14px}.card p:last-child{margin-bottom:0}
h2{font-size:19px;margin:26px 0 10px;letter-spacing:-.01em}
blockquote{margin:0;padding:6px 0 6px 16px;border-left:3px solid var(--accent);font-size:18px;line-height:1.5;font-style:italic}
ul{margin:0;padding-left:18px;color:#B5B5BA;line-height:1.75;font-size:15px}ul.l{list-style:none;padding:0}
.t{display:inline-block;min-width:44px;margin-right:8px;padding:1px 8px;border-radius:999px;background:rgba(41,151,255,.14);color:var(--accent);font-size:12.5px;text-align:center}
.tags span{display:inline-block;margin:0 6px 6px 0;padding:4px 11px;border-radius:999px;background:rgba(255,255,255,.07);color:#D2D2D7;font-size:13px}
.play{display:inline-flex;align-items:center;gap:8px;background:var(--accent);color:#fff;border:0;border-radius:999px;padding:11px 20px;font-weight:600;font-size:14.5px;cursor:pointer;margin:2px 0 4px}
.res{margin:0 0 22px}.res .it{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:0 0 10px}.res .it b{display:block;font-size:15px;margin-bottom:4px}.res .it span{color:var(--soft);font-size:13px}.res .it button{margin-top:8px;background:transparent;border:1px solid var(--line);color:var(--ink);border-radius:999px;padding:6px 14px;cursor:pointer}
#bar{position:fixed;left:0;right:0;bottom:0;background:rgba(28,28,30,.96);backdrop-filter:blur(12px);border-top:1px solid var(--line);padding:10px 16px;z-index:9}
#bar .in{max-width:720px;margin:0 auto;display:flex;align-items:center;gap:12px}#bar .tt{flex:1;min-width:0;font-size:13px;color:var(--soft);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}#bar .tt b{color:var(--ink);display:block;font-weight:600}#bar audio{height:36px;max-width:55%}
.foot{color:var(--soft);font-size:13.5px;margin-top:28px}
</style>
</head>
<body>
<header><a class="logo" href="https://listenly.org/">Listenly</a><a href="<?= $h($hub) ?>" style="font-size:13.5px"><?= $h($pod) ?></a></header>
<div class="wrap">
<form class="search" id="sf"><input id="sq" type="search" placeholder="Posez une question, un expert y a déjà répondu…" autocomplete="off"><button>Chercher</button></form>
<div class="res" id="res"></div>
<article>
<h1><?= $h($q) ?></h1>
<p class="sub"><?= $t > 0 ? 'Réponse à <strong>' . $h($ts) . '</strong> dans ' : 'Réponse dans ' ?><?= $h($epi) ?> · <?= $h($pod) ?></p>
<button class="play" id="pl" type="button">▶ Écouter à partir de <?= $h($ts) ?></button>
<div class="card" style="margin-top:14px">
<?php foreach ($paras as $p): ?><p><?= $h($p) ?></p>
<?php endforeach; ?>
<?php if ($who !== ''): ?><p style="font-size:13px;color:var(--soft)">— <?= $h($who) ?><?= $role !== '' ? ', ' . $h($role) : '' ?></p><?php endif; ?>
</div>
<?php if ($quote !== ''): ?><h2>Citation à retenir</h2><blockquote>« <?= $h($quote) ?> »</blockquote><?php endif; ?>
<?php if ($stats): ?><h2>Chiffres clés</h2><ul class="l"><?php foreach ($stats as $x): ?><li>• <?= $h($x) ?></li><?php endforeach; ?></ul><?php endif; ?>
<?php if ($ents): ?><h2>Personnes, entreprises et sujets cités</h2><div class="tags"><?php foreach (array_slice($ents, 0, 8) as $x): ?><span><?= $h($x) ?></span><?php endforeach; ?></div><?php endif; ?>
<?php if ($related): ?><h2>Autres réponses de cet épisode</h2><ul class="l"><?php foreach (array_slice($related, 0, 12) as $r): ?><li><span class="t"><?= $h(mmss($r['t'])) ?></span><a href="/podcast-btb/fr/m/<?= $h($slug) ?>/<?= $h($r['id']) ?>"><?= $h($r['q']) ?></a></li><?php endforeach; ?></ul><?php endif; ?>
<p class="foot"><a href="<?= $h($hub) ?>">Toutes les réponses de <?= $h($pod) ?> →</a><?= $show ? ' &nbsp;·&nbsp; <a href="' . $h($show) . '">Fiche du podcast sur Listenly →</a>' : '' ?></p>
</article>
</div>
<div id="bar"><div class="in"><div class="tt"><b><?= $h($pod) ?></b><?= $h($epi) ?></div><audio id="au" controls preload="none" src="<?= $h($audio) ?>"></audio></div></div>
<script>
(function(){
  var au=document.getElementById('au'), start=<?= (int)$t ?>;
  function playAt(src,sec){ if(src && au.getAttribute('src')!==src){ au.setAttribute('src',src); au.load(); }
    var go=function(){ try{ au.currentTime=sec||0; }catch(e){} au.play().catch(function(){}); };
    if(au.readyState>0) go(); else au.addEventListener('loadedmetadata',go,{once:true}); }
  document.getElementById('pl').addEventListener('click',function(){ playAt('',start); });
  var res=document.getElementById('res');
  function esc(s){ var d=document.createElement('div'); d.textContent=s==null?'':s; return d.innerHTML; }
  document.getElementById('sf').addEventListener('submit',function(ev){
    ev.preventDefault(); var question=document.getElementById('sq').value.trim(); if(!question) return;
    res.innerHTML='<div class="it"><span>Recherche en cours…</span></div>';
    fetch('https://listenly.org/api/listenly-search.php',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:question})})
      .then(function(r){return r.json();}).then(function(data){
        var list=(data&&data.results)||[]; if(!list.length){ res.innerHTML='<div class="it"><span>Aucune réponse trouvée pour le moment. Essayez une autre formulation.</span></div>'; return; }
        res.innerHTML=list.map(function(r,i){ return '<div class="it"><b>'+esc(r.question)+'</b><span>'+esc(r.expert||'')+' · '+esc(r.podcast||'')+'</span><br><button data-i="'+i+'">▶ Écouter</button></div>'; }).join('');
        res.querySelectorAll('button').forEach(function(b){ b.addEventListener('click',function(){ var r=list[+b.dataset.i]; playAt(r.audio_url,r.start_seconds||0); }); });
      }).catch(function(){ res.innerHTML='<div class="it"><span>Service de recherche indisponible. Réessayez dans un instant.</span></div>'; });
  });
})();
</script>
</body>
</html>

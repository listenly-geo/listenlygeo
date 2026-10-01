/*
 * Lien profond des hubs N1 vers la page d'accueil Listenly (recherche + lecteur en barre).
 *   listenly.fr/?p=<podcast>&m=<moment>  ->  affiche la reponse (vignette du podcast + carte) et lance l'audio au bon moment.
 *
 * + vignette du podcast (pochette, nom, bouton "Full podcast") sur chaque resultat de la recherche
 *   (carte /podcast-btb/data/podcast_covers.json, cle = nom du podcast renvoye par la recherche : aucun changement serveur).
 *
 * Charge par la page d'accueil via <script src="/podcast-btb/deeplink.js"></script> (une seule ligne a coller).
 * Toute amelioration de ce fichier est mise en ligne par le moteur : la page d'accueil n'a plus besoin d'etre recopiee.
 * Sans parametres dans l'adresse, seules les vignettes de la recherche sont actives.
 *
 * Donnees : /podcast-btb/data/moments/<podcast>.json (ecrit par automation/scripts/moments_index.py).
 * Utilise les fonctions de la page : renderResults, playAnswer, stopPlaceholderCycle, resultsWrap.
 */
(function () {
  'use strict';
  if (typeof renderResults !== 'function' || typeof playAnswer !== 'function') return;
  var params = new URLSearchParams(location.search);
  var slug = (params.get('p') || '').replace(/[^a-z0-9\-]/gi, '');
  var mid = (params.get('m') || '').replace(/[^a-f0-9]/gi, '');

  var safeListenly = function (u) { return /^https:\/\/listenly\.fr\//.test(u || '') ? u : ''; };
  var safeImage = function (u) { return /^https:\/\//.test(u || '') ? u : ''; };
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function injectStyles() {
    var css = [
      '.dl-tile{display:flex;align-items:center;gap:16px;background:#1C1C1E;border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:14px 16px 14px 14px;margin-bottom:12px;text-align:left}',
      '.dl-cover{width:84px;height:84px;border-radius:12px;object-fit:cover;flex:none;background:linear-gradient(135deg,#2997FF,#6b5bff);box-shadow:0 6px 18px rgba(0,0,0,.45)}',
      '.dl-info{flex:1;min-width:0}',
      '.dl-kicker{font-size:11.5px;letter-spacing:.07em;text-transform:uppercase;color:#86868B;margin-bottom:5px;font-weight:500}',
      '.dl-name{font-size:17px;font-weight:650;color:#F5F5F7;line-height:1.25;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}',
      '.dl-sub{font-size:13.5px;color:#86868B;margin-top:4px;line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}',
      '.dl-sub b{color:#F5F5F7;font-weight:500}',
      '.dl-btn{flex:none;background:#F5F5F7;color:#000;font-weight:600;font-size:14px;padding:11px 18px;border-radius:999px;text-decoration:none;white-space:nowrap;transition:opacity .15s}',
      '.dl-btn:hover{opacity:.85}',
      '.dl-mini{display:flex;align-items:center;gap:12px;margin:-4px 0 16px;padding-bottom:16px;border-bottom:1px solid rgba(255,255,255,.08)}',
      '.dl-mini .dl-cover{width:46px;height:46px;border-radius:9px;box-shadow:0 3px 10px rgba(0,0,0,.4)}',
      '.dl-mini .dl-info{flex:1;min-width:0}',
      '.dl-mini .dl-kicker{margin-bottom:2px;font-size:10.5px}',
      '.dl-mini .dl-name{font-size:14.5px;-webkit-line-clamp:1}',
      '.dl-mini .dl-link{flex:none;font-size:13px;font-weight:500;color:#2997FF;text-decoration:none;white-space:nowrap}',
      '.dl-mini .dl-link:hover{opacity:.75}',
      '.pb-art .dl-art{width:100%;height:100%;object-fit:cover;border-radius:10px;display:block}',
      '@media (max-width:560px){.dl-tile{flex-wrap:wrap}.dl-cover{width:72px;height:72px}.dl-btn{width:100%;text-align:center}.dl-mini .dl-cover{width:46px;height:46px}}'
    ].join('\n');
    var st = document.createElement('style');
    st.textContent = css;
    document.head.appendChild(st);
  }

  // Vignette style Spotify : pochette + nom du podcast + invite / episode + bouton vers le podcast complet
  function buildTile(d, e) {
    var tile = el('div', 'dl-tile');
    var cover = safeImage(d.cover);
    if (cover) {
      var img = el('img', 'dl-cover');
      img.src = cover; img.alt = d.podcast || ''; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer';
      img.onerror = function () { img.style.visibility = 'hidden'; };
      tile.appendChild(img);
    } else {
      tile.appendChild(el('div', 'dl-cover'));
    }
    var info = el('div', 'dl-info');
    info.appendChild(el('div', 'dl-kicker', 'Podcast'));
    info.appendChild(el('div', 'dl-name', d.podcast || ''));
    var sub = el('div', 'dl-sub');
    if (e.x) { sub.appendChild(el('b', null, e.x)); sub.appendChild(document.createTextNode(e.e ? ' · ' + e.e : '')); }
    else sub.textContent = e.e || '';
    info.appendChild(sub);
    tile.appendChild(info);
    var target = safeListenly(d.show) || safeListenly(e.l);
    if (target) {
      var a = el('a', 'dl-btn', 'Full podcast →');
      a.href = target; a.target = '_blank'; a.rel = 'noopener';
      a.addEventListener('click', function () { try { if (window.plausible) window.plausible('Moment Podcast Complet'); } catch (err) {} });
      tile.appendChild(a);
    }
    return tile;
  }

  // ---------- Vignette du podcast sur chaque resultat de la recherche ----------
  var coversPromise = null;
  function getCovers() {
    if (!coversPromise) {
      coversPromise = fetch('/podcast-btb/data/podcast_covers.json')
        .then(function (r) { return r.ok ? r.json() : {}; })
        .catch(function () { return {}; });
    }
    return coversPromise;
  }
  function decorateResults(results, map) {
    var cards = resultsWrap.querySelectorAll('.result-card');
    if (!results || cards.length !== results.length) return;   // une autre recherche a deja remplace l'affichage
    cards.forEach(function (card, i) {
      var r = results[i], info = map[r.podcast];
      var qEl = card.querySelector('.rc-question');
      if (!info || card.querySelector('.dl-mini') || !qEl || qEl.textContent !== r.question) return;
      var mini = el('div', 'dl-mini');
      var cover = safeImage(info.c);
      if (cover) {
        var img = el('img', 'dl-cover');
        img.src = cover; img.alt = r.podcast || ''; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer';
        img.onerror = function () { img.style.visibility = 'hidden'; };
        mini.appendChild(img);
      } else mini.appendChild(el('div', 'dl-cover'));
      var box = el('div', 'dl-info');
      box.appendChild(el('div', 'dl-kicker', 'Podcast'));
      box.appendChild(el('div', 'dl-name', r.podcast || ''));
      mini.appendChild(box);
      var target = safeListenly(info.s) || safeListenly(info.h);
      if (target) {
        var a = el('a', 'dl-link', 'Full podcast \u2192');
        a.href = target; a.target = '_blank'; a.rel = 'noopener';
        a.addEventListener('click', function () { try { if (window.plausible) window.plausible('Moment Podcast Complet'); } catch (err) {} });
        mini.appendChild(a);
      }
      card.insertBefore(mini, card.firstChild);
    });
  }
  // Pochette du podcast dans le lecteur en barre, pour TOUTE lecture (recherche ou lien profond) ;
  // sans pochette connue : l'icone d'origine reste.
  function setPlayerCover(cover) {
    var art = document.querySelector('.pb-art');
    if (!art) return;
    var old = art.querySelector('.dl-art');
    if (old) old.remove();
    var sv = art.querySelector('svg');
    cover = safeImage(cover);
    if (!cover) { if (sv) sv.style.display = ''; return; }
    var im = new Image();
    im.className = 'dl-art'; im.alt = ''; im.referrerPolicy = 'no-referrer';
    im.onload = function () { if (sv) sv.style.display = 'none'; art.appendChild(im); };
    im.src = cover;
  }
  var originalPlay = window.playAnswer;
  window.playAnswer = function (r) {
    var out = originalPlay.apply(this, arguments);
    window.__dlCurrent = r;
    try { document.dispatchEvent(new CustomEvent('dl:play', { detail: r })); } catch (err) {}
    getCovers().then(function (map) {
      var info = map[r && r.podcast];
      setPlayerCover((info && info.c) || (r && r.cover) || '');
    });
    return out;
  };
  injectStyles();
  var originalRender = window.renderResults;
  window.renderResults = function (results) {
    originalRender.apply(this, arguments);
    if (window.__dlSkipTiles) return;
    getCovers().then(function (map) { decorateResults(results, map); });
  };

  // Panneau du lecteur (moments cles, recap, vitesse, partage) : fichier separe, sans effet sur le reste s'il est absent
  var pp = document.createElement('script');
  pp.src = '/podcast-btb/player-panel.js?v=1'; pp.async = true;
  document.head.appendChild(pp);

  // ---------- Lien profond depuis un hub : ?p=<podcast>&m=<moment> ----------
  if (!slug || !mid) return;
  fetch('/podcast-btb/data/moments/' + slug + '.json', { cache: 'no-cache' })
    .then(function (r) { if (!r.ok) throw new Error('missing'); return r.json(); })
    .then(function (d) {
      var e = d.entries && d.entries[mid];
      if (!e) return;
      var r = {
        question: e.q,
        excerpt: (e.ap ? 'The exact moment is not available for this answer, so the episode plays from the start. ' : '') + (e.a || ''),
        expert: e.x || '',
        podcast: d.podcast,
        episode: e.e,
        audio_url: e.u,
        start_seconds: e.ap ? 0 : (e.t || 0),
        episode_url: safeListenly(e.l) || safeListenly(d.show),
        cover: d.cover || ''
      };
      if (typeof stopPlaceholderCycle === 'function') stopPlaceholderCycle();
      var hero = document.querySelector('.hero');
      if (hero) hero.style.paddingTop = '7vh';
      window.__dlSkipTiles = true;
      renderResults([r]);
      window.__dlSkipTiles = false;
      resultsWrap.insertBefore(buildTile(d, e), resultsWrap.firstChild);
      if (d.hub) {
        var back = el('a', null, '← All answers from ' + d.podcast);
        back.href = d.hub;
        back.style.cssText = 'display:block;text-align:center;color:#86868B;font-size:13.5px;text-decoration:none;margin-top:6px;';
        resultsWrap.appendChild(back);
      }
      playAnswer(r, null);
      try { if (window.plausible) window.plausible('Moment Lien Hub'); } catch (err) {}
      var top = resultsWrap.getBoundingClientRect().top;
      if (top > window.innerHeight * 0.55) resultsWrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
    })
    .catch(function () {});
})();

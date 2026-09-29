/*
 * Panneau du lecteur (29/09/2026) : la barre de lecture se deroule vers le haut.
 *  - Recap de la reponse (question + extrait + expert)
 *  - Moments cles du meme episode (clic = saut a la minute), surlignes pendant la lecture
 *  - Vitesse de lecture (1x, 1.25x, 1.5x, 2x) et bouton Partager ce moment
 * Charge par deeplink.js. Donnees : /podcast-btb/data/moments/<podcast>.json et podcast_covers.json (aucun changement serveur).
 * Retour arriere : retirer la ligne "player-panel.js" de deeplink.js (ou restaurer backup/deeplink-2026-09-29-avant-panneau.js).
 */
(function () {
  'use strict';
  var bar = document.getElementById('playerBar'), audio = document.getElementById('pbAudio');
  if (!bar || !audio || window.__ppLoaded) return;
  window.__ppLoaded = true;

  var current = window.__dlCurrent || null, momentsCache = {}, covers = null;
  var safeListenly = function (u) { return /^https:\/\/listenly\.fr\//.test(u || '') ? u : ''; };
  var safeImage = function (u) { return /^https:\/\//.test(u || '') ? u : ''; };
  var norm = function (s) { return String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim(); };
  var fmt = function (s) { s = Math.max(0, Math.floor(s || 0)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }

  // ---------- styles ----------
  var css = [
    '.pp-btn{flex-shrink:0;background:none;border:none;color:#86868B;cursor:pointer;padding:4px;display:flex;transition:color .15s,transform .2s}',
    '.pp-btn:hover{color:#F5F5F7}.pp-btn svg{width:18px;height:18px}.pp-btn[aria-expanded="true"]{color:#2997FF;transform:rotate(180deg)}',
    '.pp-sheet{position:fixed;left:50%;width:min(680px,100%);max-height:68vh;overflow-y:auto;z-index:9;background:rgba(28,28,30,.97);-webkit-backdrop-filter:blur(24px) saturate(1.5);backdrop-filter:blur(24px) saturate(1.5);border:1px solid rgba(255,255,255,.09);border-bottom:0;border-radius:22px 22px 0 0;box-shadow:0 -14px 48px rgba(0,0,0,.5);padding:22px 22px 26px;color:#F5F5F7;opacity:0;pointer-events:none;transform:translate(-50%,24px);transition:opacity .22s ease,transform .22s ease;text-align:left}',
    '.pp-sheet.open{opacity:1;pointer-events:auto;transform:translate(-50%,0)}',
    '.pp-head{display:flex;align-items:center;gap:14px;margin-bottom:18px}',
    '.pp-cover{width:64px;height:64px;border-radius:12px;object-fit:cover;flex:none;background:linear-gradient(135deg,#2997FF,#6b5bff);box-shadow:0 6px 18px rgba(0,0,0,.45)}',
    '.pp-head-info{flex:1;min-width:0}',
    '.pp-ep{font-size:16px;font-weight:650;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}',
    '.pp-who{font-size:13px;color:#86868B;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
    '.pp-x{flex:none;background:rgba(255,255,255,.08);border:0;color:#F5F5F7;width:30px;height:30px;border-radius:50%;cursor:pointer;font-size:15px;line-height:1}',
    '.pp-label{font-size:11.5px;letter-spacing:.07em;text-transform:uppercase;color:#86868B;font-weight:500;margin:20px 0 10px}',
    '.pp-recap{background:#2C2C2E;border-radius:16px;padding:16px 18px}',
    '.pp-q{font-size:15.5px;font-weight:600;line-height:1.4;margin:0 0 8px}',
    '.pp-a{font-size:14px;line-height:1.6;color:#B4B4B9;margin:0;display:-webkit-box;-webkit-line-clamp:6;-webkit-box-orient:vertical;overflow:hidden}',
    '.pp-list{display:flex;flex-direction:column;gap:6px}',
    '.pp-item{display:flex;gap:12px;align-items:flex-start;width:100%;text-align:left;background:none;border:0;color:#F5F5F7;font:inherit;padding:10px 12px;border-radius:12px;cursor:pointer;transition:background .15s}',
    '.pp-item:hover{background:rgba(255,255,255,.06)}',
    '.pp-item.on{background:rgba(41,151,255,.16)}',
    '.pp-time{flex:none;min-width:46px;text-align:center;font-size:12.5px;font-weight:600;font-variant-numeric:tabular-nums;color:#2997FF;background:rgba(41,151,255,.14);border-radius:999px;padding:4px 9px}',
    '.pp-item .pp-t{font-size:14px;line-height:1.4;padding-top:2px}',
    '.pp-empty{font-size:13.5px;color:#86868B;padding:4px 2px}',
    '.pp-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}',
    '.pp-seg{display:inline-flex;background:#2C2C2E;border-radius:999px;padding:3px}',
    '.pp-seg button{border:0;background:none;color:#B4B4B9;font:600 13px/1 inherit;font-family:inherit;padding:8px 13px;border-radius:999px;cursor:pointer}',
    '.pp-seg button.on{background:#F5F5F7;color:#000}',
    '.pp-share{margin-left:auto;background:#F5F5F7;color:#000;border:0;border-radius:999px;font:600 13.5px/1 inherit;font-family:inherit;padding:10px 18px;cursor:pointer}',
    '.pp-share:hover{opacity:.85}',
    '.pp-link{display:inline-block;margin-top:16px;color:#2997FF;font-size:14px;text-decoration:none;font-weight:500}',
    '@media (max-width:700px){.pp-sheet{padding:18px 16px 22px;max-height:62vh}.pp-share{margin-left:0}}'
  ].join('\n');
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  // ---------- bouton de deroulement dans la barre ----------
  var toggle = el('button', 'pp-btn');
  toggle.type = 'button'; toggle.setAttribute('aria-label', 'Show details'); toggle.setAttribute('aria-expanded', 'false');
  toggle.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 15 12 9 18 15"/></svg>';
  var closeBtn = bar.querySelector('.pb-close');
  bar.insertBefore(toggle, closeBtn || null);

  var sheet = el('div', 'pp-sheet');
  sheet.setAttribute('role', 'dialog'); sheet.setAttribute('aria-label', 'Episode details');
  document.body.appendChild(sheet);

  function place() {
    var r = bar.getBoundingClientRect();
    sheet.style.bottom = Math.max(0, window.innerHeight - r.top) + 'px';
  }
  function open(v) {
    if (v && !current) return;
    sheet.classList.toggle('open', !!v);
    toggle.setAttribute('aria-expanded', v ? 'true' : 'false');
    if (v) { place(); render(); }
  }
  toggle.addEventListener('click', function () { open(!sheet.classList.contains('open')); });
  window.addEventListener('resize', function () { if (sheet.classList.contains('open')) place(); });
  if (closeBtn) closeBtn.addEventListener('click', function () { open(false); });

  // ---------- donnees ----------
  function getCovers() {
    if (!covers) covers = fetch('/podcast-btb/data/podcast_covers.json').then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; });
    return covers;
  }
  function getMoments(slug) {
    if (!slug) return Promise.resolve(null);
    if (!momentsCache[slug]) momentsCache[slug] = fetch('/podcast-btb/data/moments/' + slug + '.json').then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    return momentsCache[slug];
  }
  function slugOf(info) {
    var m = /\/podcast-btb\/([a-z0-9\-]+)-podcast\.html$/i.exec((info && info.h) || '');
    return m ? m[1] : '';
  }

  // ---------- rendu ----------
  var token = 0, currentList = [];
  function render() {
    if (!current) return;
    var mine = ++token, r = current;
    getCovers().then(function (map) {
      var info = map[r.podcast] || {}, slug = slugOf(info);
      return getMoments(slug).then(function (data) { if (mine === token) draw(r, info, slug, data); });
    });
  }
  function draw(r, info, slug, data) {
    sheet.textContent = '';
    var head = el('div', 'pp-head');
    var cover = safeImage(info.c || r.cover);
    if (cover) { var im = el('img', 'pp-cover'); im.src = cover; im.alt = ''; im.referrerPolicy = 'no-referrer'; im.onerror = function () { im.style.visibility = 'hidden'; }; head.appendChild(im); }
    else head.appendChild(el('div', 'pp-cover'));
    var hi = el('div', 'pp-head-info');
    hi.appendChild(el('div', 'pp-ep', r.episode || r.podcast || ''));
    hi.appendChild(el('div', 'pp-who', (r.expert ? r.expert + ' · ' : '') + (r.podcast || '')));
    head.appendChild(hi);
    var x = el('button', 'pp-x', '✕'); x.type = 'button'; x.setAttribute('aria-label', 'Close details');
    x.addEventListener('click', function () { open(false); });
    head.appendChild(x);
    sheet.appendChild(head);

    // recap
    sheet.appendChild(el('div', 'pp-label', 'Answer recap'));
    var rc = el('div', 'pp-recap');
    rc.appendChild(el('p', 'pp-q', r.question || ''));
    if (r.excerpt) rc.appendChild(el('p', 'pp-a', r.excerpt));
    sheet.appendChild(rc);

    // moments cles du meme episode
    var list = [], myId = '';
    if (data && data.entries) {
      Object.keys(data.entries).forEach(function (id) {
        var e = data.entries[id];
        var same = (e.u && r.audio_url && e.u === r.audio_url) || (norm(e.e) && norm(e.e) === norm(r.episode));
        if (!same) return;
        if (norm(e.q) === norm(r.question)) myId = id;
        if (!e.ap && e.t > 0) list.push({ id: id, t: e.t, q: e.q, u: e.u || r.audio_url });
      });
      list.sort(function (a, b) { return a.t - b.t; });
    }
    currentList = list;
    sheet.appendChild(el('div', 'pp-label', 'Key moments in this episode'));
    if (list.length > 1) {
      var ul = el('div', 'pp-list');
      list.forEach(function (m) {
        var b = el('button', 'pp-item'); b.type = 'button'; b.dataset.t = m.t;
        b.appendChild(el('span', 'pp-time', fmt(m.t)));
        b.appendChild(el('span', 'pp-t', m.q));
        b.addEventListener('click', function () { audio.currentTime = m.t; audio.play().catch(function () {}); highlight(); });
        ul.appendChild(b);
      });
      sheet.appendChild(ul);
    } else {
      sheet.appendChild(el('div', 'pp-empty', 'Only this moment is available for this episode so far.'));
    }

    // vitesse + partage
    sheet.appendChild(el('div', 'pp-label', 'Playback'));
    var row = el('div', 'pp-row'), seg = el('div', 'pp-seg');
    [1, 1.25, 1.5, 2].forEach(function (v) {
      var b = el('button', audio.playbackRate === v ? 'on' : '', v + '×'); b.type = 'button';
      b.addEventListener('click', function () {
        audio.defaultPlaybackRate = v; audio.playbackRate = v;
        seg.querySelectorAll('button').forEach(function (n) { n.classList.remove('on'); }); b.classList.add('on');
      });
      seg.appendChild(b);
    });
    row.appendChild(seg);
    var share = el('button', 'pp-share', 'Share this moment'); share.type = 'button';
    var link = (slug && myId) ? 'https://listenly.fr/?p=' + slug + '&m=' + myId : (safeListenly(r.episode_url) || 'https://listenly.fr/');
    share.addEventListener('click', function () {
      var done = function () { share.textContent = 'Link copied ✓'; setTimeout(function () { share.textContent = 'Share this moment'; }, 1800); };
      if (navigator.share && /Mobi|Android/i.test(navigator.userAgent)) { navigator.share({ title: r.question, url: link }).catch(function () {}); return; }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(link).then(done, function () { window.prompt('Copy this link', link); });
      else window.prompt('Copy this link', link);
    });
    row.appendChild(share);
    sheet.appendChild(row);

    var show = safeListenly(info.s) || safeListenly(info.h && ('https://listenly.fr' + info.h));
    if (show) { var a = el('a', 'pp-link', 'Full podcast →'); a.href = show; a.target = '_blank'; a.rel = 'noopener'; sheet.appendChild(a); }
    highlight();
  }
  function highlight() {
    var t = audio.currentTime || 0, items = sheet.querySelectorAll('.pp-item'), on = null;
    items.forEach(function (b) { if (parseFloat(b.dataset.t) <= t + 0.5) on = b; b.classList.remove('on'); });
    if (on) on.classList.add('on');
  }
  audio.addEventListener('timeupdate', function () { if (sheet.classList.contains('open')) highlight(); });

  // nouvelle lecture : on met a jour le panneau (ouvert ou non)
  document.addEventListener('dl:play', function (ev) {
    current = ev.detail;
    if (sheet.classList.contains('open')) { place(); render(); }
  });
  var cs = bar.classList; // la barre est fermee => panneau ferme
  new MutationObserver(function () { if (!bar.classList.contains('active')) open(false); }).observe(bar, { attributes: true, attributeFilter: ['class'] });
})();

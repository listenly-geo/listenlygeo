(function () {
  try {
    var m = location.pathname.match(/^\/docs\/([a-z0-9-]+)/), q = '';
    if (m) q = 'site=' + m[1];
    else if (!/(^|\.)marketforge\.fr$/.test(location.hostname)) q = 'host=' + encodeURIComponent(location.hostname);
    if (!q) return;
    var url = '__BRIDGE__?action=portal&' + q, css = 'display:inline-flex;align-items:center;margin-left:12px;padding:7px 14px;border-radius:999px;border:1px solid rgba(128,128,128,.45);font:600 13px -apple-system,Segoe UI,Arial,sans-serif;color:inherit;text-decoration:none;white-space:nowrap;background:transparent';
    function make() { var a = document.createElement('a'); a.id = 'mf-admin'; a.href = url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = 'Espace admin'; a.style.cssText = css; return a; }
    function place() {
      if (document.getElementById('mf-admin')) return true;
      var els = document.querySelectorAll('span,div,a,button');
      for (var i = 0; i < els.length; i++) {
        var el = els[i];
        if (el.children.length === 0 && /^production$/i.test((el.textContent || '').trim()) && el.parentNode) { el.parentNode.appendChild(make()); return true; }
      }
      return false;
    }
    var n = 0, t = setInterval(function () {
      n++;
      if (place()) { clearInterval(t); return; }
      if (n > 20) { clearInterval(t); var a = make(); a.style.cssText = css + ';position:fixed;top:16px;right:16px;z-index:50;background:#fff;color:#1d1d1f;margin:0'; document.body.appendChild(a); }
    }, 300);
    new MutationObserver(function () { if (!document.getElementById('mf-admin')) place(); }).observe(document.documentElement, { childList: true, subtree: true });
  } catch (e) {}
})();

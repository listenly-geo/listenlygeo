"""Bouton « Accéder au podcast » : lit la destination en direct (redirections.json) et met le lien à jour sur la fiche.
Sans destination enregistrée, le bouton garde le lien Listenly d'origine."""
import re, sys, os

SNIPPET = '''<script>
(function(){
  var slug = "{SLUG}";
  fetch("https://raw.githubusercontent.com/listenly-geo/listenlygeo/main/automation/marketforge_engine/redirections.json?t=" + Date.now())
    .then(function(r){ return r.ok ? r.json() : {}; })
    .then(function(d){
      var url = d[slug]; if (!url) return;
      document.querySelectorAll("a").forEach(function(a){
        if (/Acc\\u00e9der au podcast|\\u00c9couter le podcast/.test(a.textContent)) { a.href = url; a.target = "_blank"; a.rel = "noopener"; }
      });
    }).catch(function(){});
})();
</script>
'''

def patch(html, slug):
    if "redirections.json" in html:
        return html
    snip = SNIPPET.replace("{SLUG}", slug)
    return html.replace("</body>", snip + "</body>") if "</body>" in html else html + snip

if __name__ == "__main__":
    path = sys.argv[1]
    slug = os.path.basename(path).replace("-podcast.html", "")
    html = open(path, encoding="utf-8").read()
    out = patch(html, slug)
    open(path, "w", encoding="utf-8").write(out)
    print("patched" if out != html else "already")

#!/usr/bin/env python3
"""
Page « concept » Listenly (Knowledge Search) + lien profond depuis les hubs N1 (29/09/2026).

Part de la page de recherche d'Etienne (automation/tools/knowledge-search-source.html : hero, recherche,
compteurs, lecteur en barre avec +/-10 s) et lui ajoute UN comportement : ?p=<podcast>&m=<moment>
ouvre la reponse correspondante et lance le lecteur au bon moment.

Sorties :
  pages/podcast-btb/ecouter.html                    : copie deployee par le moteur (noindex) — cible des boutons des hubs
  automation/tools/knowledge-search-deeplink.html   : meme page, indexable (canonical /knowledge-search),
                                                      a coller sur listenly.fr/knowledge-search
Usage : python automation/tools/build_knowledge_deeplink.py
"""
import re, os

SRC = "automation/tools/knowledge-search-source.html"
OUT_ECOUTER = "pages/podcast-btb/ecouter.html"
OUT_CONCEPT = "automation/tools/knowledge-search-deeplink.html"

DEEPLINK_JS = r"""
  // ---------- Lien profond depuis les hubs N1 : ?p=<podcast>&m=<moment> ----------
  // Ouvre la reponse (carte + lien "Episode page") ET lance le lecteur au bon moment, comme un clic
  // sur "Listen at". Donnees : /podcast-btb/data/moments/<podcast>.json (ecrit par le moteur a chaque
  // nouvelle extraction). Sans parametres, la page se comporte exactement comme avant.
  (function deepLink(){
    const params = new URLSearchParams(location.search);
    const slug = (params.get('p') || '').replace(/[^a-z0-9\-]/gi, '');
    const mid = (params.get('m') || '').replace(/[^a-f0-9]/gi, '');
    if (!slug || !mid) return;
    fetch('/podcast-btb/data/moments/' + slug + '.json', { cache: 'no-cache' })
      .then(r => { if (!r.ok) throw new Error('missing'); return r.json(); })
      .then(d => {
        const e = d.entries && d.entries[mid];
        if (!e) return;
        const safe = u => /^https:\/\/listenly\.fr\//.test(u || '') ? u : '';
        const r = {
          question: e.q,
          excerpt: (e.ap ? 'The exact moment is not available for this answer, so the episode plays from the start. ' : '') + (e.a || ''),
          expert: e.x || '',
          podcast: d.podcast,
          episode: e.e,
          audio_url: e.u,
          start_seconds: e.ap ? 0 : (e.t || 0),
          episode_url: safe(e.l) || safe(d.show)
        };
        stopPlaceholderCycle();
        document.querySelector('.hero').style.paddingTop = '7vh';
        renderResults([r]);
        if (d.hub) {
          const back = document.createElement('a');
          back.href = d.hub;
          back.textContent = '← All answers from ' + d.podcast;
          back.style.cssText = 'display:block;text-align:center;color:#86868B;font-size:13.5px;text-decoration:none;margin-top:6px;';
          resultsWrap.appendChild(back);
        }
        playAnswer(r, null);
        try { if (window.plausible) window.plausible('Moment Lien Hub'); } catch (err) {}
        const top = resultsWrap.getBoundingClientRect().top;
        if (top > window.innerHeight * 0.55) resultsWrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
      })
      .catch(() => {});
  })();
"""


def build():
    with open(SRC, encoding="utf-8") as f:
        src = f.read()
    assert "function playAnswer(" in src and "function renderResults(" in src, "page source inattendue"
    marker = "</script>\n</body>"
    assert marker in src, "fin de script introuvable"
    concept = src.replace(marker, DEEPLINK_JS + marker, 1)

    ecouter = concept
    ecouter = re.sub(r'<link rel="canonical"[^>]*>\n', '', ecouter)
    ecouter = re.sub(r'<meta property="og:url"[^>]*>\n', '', ecouter)
    ecouter = ecouter.replace('<meta charset="UTF-8">', '<meta charset="UTF-8">\n<meta name="robots" content="noindex, follow">', 1)
    ecouter = ecouter.replace("<title>Listenly — Knowledge Search: Find the Exact Podcast Answer to Any Question</title>",
                              "<title>Listen to the answer — Listenly</title>", 1)

    with open(OUT_CONCEPT, "w", encoding="utf-8") as f:
        f.write(concept)
    with open(OUT_ECOUTER, "w", encoding="utf-8") as f:
        f.write(ecouter)
    print(f"[deeplink] {OUT_ECOUTER} ({len(ecouter)} o), {OUT_CONCEPT} ({len(concept)} o)")


if __name__ == "__main__":
    build()

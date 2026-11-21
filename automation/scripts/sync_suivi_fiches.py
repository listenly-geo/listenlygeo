"""Garde le tableau de suivi (suivi_fiches.json) a jour a partir de index_requests.json.
Toute URL 'urls_demandees' absente du suivi y est ajoutee (date, url, question, podcast)."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import moment_urls as mu   # 21/11/2026 : adresses par question -> cle podcast/code
D = "pages/podcast-btb/data"
req = json.load(open(f"{D}/index_requests.json"))
S = json.load(open(f"{D}/suivi_fiches.json"))
L = S["fiches"]
TIT = json.load(open(f"{D}/titres_seo.json")).get("titres", {})
def titre(u):
    return TIT.get(mu.path_to_key(u) or "/".join(u.split("/m/")[1].split("/")[:2]))
deja = {f["url"] for f in L}
ajout = 0
for date, e in sorted(req.items()):
    if not isinstance(e, dict):
        continue
    for u in e.get("urls_demandees", []):
        if u in deja or "/m/" not in u:
            continue
        slug, mid = (mu.path_to_key(u) or "/".join(u.split("/m/")[1].split("/")[:2])).split("/")
        try:
            m = json.load(open(f"{D}/moments/{slug}.json"))["entries"][mid]
            q, p = m.get("q", ""), m.get("p") or slug.replace("-", " ").title()
        except Exception:
            q, p = "", slug.replace("-", " ").title()
        L.append({"date": date, "url": u, "question": titre(u) or q, "podcast": p})
        deja.add(u); ajout += 1
for f in L:  # le tableau affiche le titre Google optimise, pas la question longue
    t = titre(f["url"])
    if t and f.get("question") != t:
        f["question"] = t; ajout += 1
if ajout:
    json.dump(S, open(f"{D}/suivi_fiches.json", "w"), ensure_ascii=False, indent=1)
print("ajoutees:", ajout)

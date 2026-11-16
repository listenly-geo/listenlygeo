"""Garde le tableau de suivi (suivi_fiches.json) a jour a partir de index_requests.json.
Toute URL 'urls_demandees' absente du suivi y est ajoutee (date, url, question, podcast)."""
import json, os
D = "pages/podcast-btb/data"
req = json.load(open(f"{D}/index_requests.json"))
S = json.load(open(f"{D}/suivi_fiches.json"))
L = S["fiches"]
deja = {f["url"] for f in L}
ajout = 0
for date, e in sorted(req.items()):
    if not isinstance(e, dict):
        continue
    for u in e.get("urls_demandees", []):
        if u in deja or "/m/" not in u:
            continue
        slug, mid = u.split("/m/")[1].split("/")[:2]
        try:
            m = json.load(open(f"{D}/moments/{slug}.json"))["entries"][mid]
            q, p = m.get("q", ""), m.get("p") or slug.replace("-", " ").title()
        except Exception:
            q, p = "", slug.replace("-", " ").title()
        L.append({"date": date, "url": u, "question": q, "podcast": p})
        deja.add(u); ajout += 1
if ajout:
    json.dump(S, open(f"{D}/suivi_fiches.json", "w"), ensure_ascii=False, indent=1)
print("ajoutees:", ajout)

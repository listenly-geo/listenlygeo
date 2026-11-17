"""Traduit en francais les titres affiches dans le tableau de suivi (suivi-indexation-*.html).
Ecrit pages/podcast-btb/data/traductions_fr.json : {url: "titre en francais"}. Ne traduit que ce qui manque."""
import json, os, re, glob, urllib.request
D = "pages/podcast-btb/data"
OUT = f"{D}/traductions_fr.json"
tr = json.load(open(OUT)) if os.path.exists(OUT) else {}
items = {}
for page in glob.glob("pages/podcast-btb/suivi-indexation-*.html"):
    h = open(page, encoding="utf-8").read()
    for k in ("REQUESTS", "RESERVOIR"):
        m = re.search(r"const " + k + r"=(\[.*?\]);\n", h)
        if m:
            for r in json.loads(m.group(1)):
                if r.get("question"):
                    items[r.get("url") or "q:" + r["question"]] = r["question"]
for f in json.load(open(f"{D}/suivi_fiches.json")).get("fiches", []):
    if f.get("url") and f.get("question"):
        items[f["url"]] = f["question"]
# retraduire si le titre anglais a change
etat = tr.pop("_source", {}) if isinstance(tr.get("_source"), dict) else {}
todo = [u for u, q in items.items() if u not in tr or etat.get(u) != q]
print(f"{len(items)} titres, {len(todo)} a traduire")

def claude(lines):
    prompt = ("Traduis en français naturel chacun de ces titres de pages (questions de podcast). Garde tel quel ce qui suit "
              "« | » (nom du podcast ou Listenly) et les noms propres. Réponds UNIQUEMENT par un tableau JSON de chaînes, "
              "dans le même ordre, même nombre d'éléments.\n\n" + json.dumps(lines, ensure_ascii=False))
    body = json.dumps({"model": "claude-haiku-4-5-20251001", "max_tokens": 8000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    t = json.loads(urllib.request.urlopen(req, timeout=180).read())["content"][0]["text"]
    out = json.loads(t[t.find("["):t.rfind("]") + 1])
    if len(out) != len(lines):
        raise ValueError("nombre de lignes different")
    return out

n = 0
for i in range(0, len(todo), 80):
    lot = todo[i:i + 80]
    try:
        res = claude([items[u] for u in lot])
    except Exception as e:
        print("lot ignore :", e); continue
    for u, fr in zip(lot, res):
        tr[u] = str(fr).strip(); etat[u] = items[u]; n += 1
tr["_source"] = etat
json.dump(tr, open(OUT, "w"), ensure_ascii=False, indent=0)
print("traduits :", n)

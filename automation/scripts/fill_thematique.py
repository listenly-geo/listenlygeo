#!/usr/bin/env python3
"""
Thematique de chaque podcast pour le mail de prospection (30/09/2026).

Le mail dit : "... lorsqu'un dirigeant recherche des informations sur {THEMATIQUE}".
Ce script demande a Claude (Haiku, sans recherche web, 1 appel pour ~40 podcasts) une thematique courte,
en francais, precedee de son article (ex. "l'immobilier commercial", "la cybersecurite industrielle"),
a partir du nom du podcast et de sa fiche (categorie, societe de l'hote, punchline).
Resultat : champ `thematique` de chaque podcast dans queue.json (une seule fois par podcast) ;
sheet_bridge.py le pousse ensuite dans le Sheet (colonne Thematique).
Variables : ANTHROPIC_API_KEY. Ne bloque jamais le run.
"""
import os, sys, json, re, urllib.request

QUEUE = "automation/marketforge_engine/queue.json"
PODCASTS = "pages/podcast-btb/data/podcasts.json"
MODEL = "claude-haiku-4-5-20251001"
BATCH = 40
MAX_PER_RUN = 120


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def ask(prompt):
    payload = {"model": MODEL, "max_tokens": 3000, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=json.dumps(payload).encode("utf-8"),
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                 "content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        res = json.loads(r.read())
    return "".join(b.get("text", "") for b in res.get("content", []) if b.get("type") == "text")


def clean(t):
    t = re.sub(r"\s+", " ", str(t or "")).strip().strip("\"'«».").strip()
    return t if 3 <= len(t) <= 60 else ""


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[thematique] ANTHROPIC_API_KEY absent, rien a faire.")
        return 0
    queue = load(QUEUE, {"podcasts": {}})
    fiches = {p.get("slug"): p for p in load(PODCASTS, []) if isinstance(p, dict)}
    todo = [s for s, p in queue["podcasts"].items() if not p.get("thematique")][:MAX_PER_RUN]
    if not todo:
        print("[thematique] Tous les podcasts ont deja une thematique.")
        return 0
    done = 0
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        lines = []
        for s in chunk:
            f, q = fiches.get(s, {}), queue["podcasts"][s]
            lines.append(f"- {s} | {q.get('podcast_name') or f.get('podcast_name', '')} | categorie: {f.get('categorie', '')} | "
                         f"societe de l'hote: {f.get('host_company', '')} | {str(f.get('punchline', ''))[:200]}")
        prompt = (
            "Pour chaque podcast B2B ci-dessous, donne sa THEMATIQUE en francais : un groupe nominal court (2 a 6 mots) "
            "PRECEDE DE SON ARTICLE, qui complete la phrase \"un dirigeant recherche des informations sur ...\". "
            "Exemples : \"l'immobilier commercial\", \"la cybersecurite industrielle\", \"le recrutement tech\", "
            "\"la logistique du dernier kilometre\". Pas de nom de podcast ni de marque, pas de point final. "
            "Reponds UNIQUEMENT par un objet JSON {\"slug\": \"thematique\", ...}.\n\n" + "\n".join(lines))
        try:
            raw = ask(prompt)
            data = json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group(0))
        except Exception as e:
            print(f"[thematique] AVERTISSEMENT : lot ignore ({e})")
            continue
        for s in chunk:
            t = clean(data.get(s))
            if t:
                queue["podcasts"][s]["thematique"] = t
                done += 1
    with open(QUEUE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"::notice title=Thematique::{done}/{len(todo)} thematique(s) renseignee(s) pour le mail")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # ne bloque jamais le run
        print(f"::warning title=Thematique::{str(e)[:300]}")

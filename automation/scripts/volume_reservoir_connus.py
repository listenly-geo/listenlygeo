#!/usr/bin/env python3
"""
VOLUMES RESERVOIR (08/11/2026) : volume de recherche Google Ads (Keyword Planner) des questions du reservoir
MarketForge qui n'ont pas encore de fiche. Lecture seule : ne publie rien, ne modifie pas le reservoir.

1. Chaque question recoit un theme court (1 a 3 mots anglais, ce qu'une personne taperait dans Google),
   ecrit par Claude (Haiku) puis garde en cache : automation/moments_connus/themes_reservoir.json
2. Google Ads est interroge par lots de 20 themes (meme methode que keyword_planner_quotidien.py)
3. Resultat : automation/moments_connus/volumes_reservoir.json (volume mensuel moyen du theme, par question)

Secrets : ANTHROPIC_API_KEY, GOOGLE_ADS_CLIENT_ID / CLIENT_SECRET / REFRESH_TOKEN / CUSTOMER_ID (+ developer token)
"""
import os, sys, json, re, hashlib, datetime, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import keyword_planner as kp  # noqa: E402

RESERVOIR = "automation/marketforge_engine/reservoir_questions.json"
DIR = "automation/moments_connus"
THEMES = f"{DIR}/themes_reservoir.json"
OUT = f"{DIR}/volumes_reservoir.json"
MODEL = "claude-haiku-4-5-20251001"
BATCH_THEME = 40
BATCH_ADS = 20


def qkey(item):
    norm = re.sub(r'\W+', ' ', (item.get('question') or '').lower()).strip()
    base = item.get('podcast_slug', '') + '|' + norm
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


def claude_themes(questions):
    """questions : liste de textes. Retourne une liste de themes (meme ordre), '' si echec."""
    numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    prompt = (
        "For each numbered podcast question below, write the short Google search query (1 to 3 English words, "
        "lowercase) a person would type to find this topic. No person names, no podcast names, no question words. "
        "Reply with ONLY a JSON object mapping each number to its query, e.g. {\"1\": \"cash flow\", \"2\": \"ai marketing\"}.\n\n"
        + numbered
    )
    body = json.dumps({"model": MODEL, "max_tokens": 3000, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        text = json.loads(r.read())["content"][0]["text"]
    m = re.search(r"\{.*\}", text, re.S)
    data = json.loads(m.group(0)) if m else {}
    return [re.sub(r"\s+", " ", str(data.get(str(i + 1), "")).strip().lower())[:60] for i in range(len(questions))]


def main():
    now = datetime.datetime.utcnow().isoformat(timespec="minutes") + "Z"
    items = [i for i in json.load(open(RESERVOIR, encoding="utf-8"))["items"] if not i.get("fiche_url")]
    cache = json.load(open(THEMES, encoding="utf-8")) if os.path.exists(THEMES) else {}
    todo = [i for i in items if qkey(i) not in cache]
    if todo and os.environ.get("ANTHROPIC_API_KEY"):
        for s in range(0, len(todo), BATCH_THEME):
            lot = todo[s:s + BATCH_THEME]
            try:
                themes = claude_themes([i.get("question", "") for i in lot])
            except Exception as e:
                print(f"Themes : lot {s // BATCH_THEME} en echec ({e})")
                continue
            for it, th in zip(lot, themes):
                if th:
                    cache[qkey(it)] = th
        os.makedirs(DIR, exist_ok=True)
        json.dump(cache, open(THEMES, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"Themes : {len([i for i in items if qkey(i) in cache])}/{len(items)} questions ont un theme.")

    missing = kp.secrets_ok()
    if missing:
        json.dump({"statut": "non connecte", "manque": missing, "date": now}, open(OUT, "w"), indent=1)
        print("Google Ads non connecte : " + ", ".join(missing))
        return
    try:
        token = kp.access_token()
    except Exception as e:
        json.dump({"statut": "erreur", "etape": "jeton Google Ads", "detail": str(e)[:200], "date": now}, open(OUT, "w"), indent=1)
        print(f"Jeton Google Ads refuse : {e}")
        return

    themes = sorted({cache[qkey(i)] for i in items if qkey(i) in cache})
    vol, faits, erreurs = {}, 0, 0
    for s in range(0, len(themes), BATCH_ADS):
        try:
            for idea in kp.generate_ideas(themes[s:s + BATCH_ADS], token):
                k = (idea.get("requete") or "").lower()
                if k and idea["volume_mensuel_moyen"] > vol.get(k, -1):
                    vol[k] = idea["volume_mensuel_moyen"]
            faits += 1
        except urllib.error.HTTPError as e:
            erreurs += 1
            if e.code in (429, 403):
                print(f"Arret au lot {s // BATCH_ADS} : erreur {e.code}")
                break
    res = {}
    for i in items:
        k = qkey(i)
        if k in cache:
            res[k] = {"question": i.get("question", ""), "podcast_slug": i.get("podcast_slug", ""),
                      "date_ajout": i.get("date_ajout", ""), "theme": cache[k], "volume": vol.get(cache[k], 0)}
    json.dump({"statut": "connecte" if faits else "erreur", "date": now, "themes": len(themes),
               "lots_reussis": faits, "lots_en_erreur": erreurs, "items": res},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    avec = sum(1 for v in res.values() if v["volume"] >= 100)
    print(f"Volumes : {len(res)} questions, {avec} avec au moins 100 recherches/mois ({faits} lots, {erreurs} erreurs).")


if __name__ == "__main__":
    main()

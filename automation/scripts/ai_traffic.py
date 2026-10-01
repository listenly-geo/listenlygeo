#!/usr/bin/env python3
"""
Trafic venant des IA (01/10/2026) via l'API Plausible (les pages envoient deja leurs visites a Plausible).
Secret GitHub requis : PLAUSIBLE_API_KEY (Plausible > Settings > API keys). Optionnels : PLAUSIBLE_SITE_ID
(defaut listenly.fr), PLAUSIBLE_URL (defaut https://plausible.io). Sans cle : on sort sans erreur.
Ecrit pages/podcast-btb/data/ai_traffic.json : visiteurs 7 jours total / venant des IA, par source.
"""
import os, json, datetime, urllib.request

OUT = "pages/podcast-btb/data/ai_traffic.json"
AI = ("chatgpt", "openai", "perplexity", "gemini", "bard", "claude", "anthropic", "copilot", "you.com", "phind",
      "mistral", "deepseek", "grok", "meta.ai", "poe.com", "kagi")


def q(base, key, body):
    req = urllib.request.Request(f"{base}/api/v2/query", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    key = os.environ.get("PLAUSIBLE_API_KEY")
    if not key:
        print("[ai-traffic] PLAUSIBLE_API_KEY absente : suivi du trafic IA non actif.")
        return
    base = (os.environ.get("PLAUSIBLE_URL") or "https://plausible.io").rstrip("/")
    site = os.environ.get("PLAUSIBLE_SITE_ID") or "listenly.fr"
    try:
        tot = q(base, key, {"site_id": site, "metrics": ["visitors", "pageviews"], "date_range": "7d"})
        src = q(base, key, {"site_id": site, "metrics": ["visitors"], "date_range": "7d", "dimensions": ["visit:source"]})
    except Exception as e:
        print(f"[ai-traffic] erreur API : {e}")
        return
    total = (tot.get("results") or [{}])[0].get("metrics", [0, 0])
    ai = {}
    for row in src.get("results", []):
        name = (row["dimensions"][0] or "").lower()
        if any(a in name for a in AI):
            ai[row["dimensions"][0]] = row["metrics"][0]
    out = {"date": datetime.date.today().isoformat(), "visitors_7d": total[0], "pageviews_7d": total[1],
           "ai_visitors_7d": sum(ai.values()), "ai_sources": ai}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"[ai-traffic] visiteurs 7j: {total[0]} | venant des IA: {out['ai_visitors_7d']} {ai}")


if __name__ == "__main__":
    main()

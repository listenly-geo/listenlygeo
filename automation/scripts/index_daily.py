#!/usr/bin/env python3
"""
Publication quotidienne des Index (19/11/2026, decision d'Etienne) : chaque jour, une page de la file de chaque client
est mise en ligne sur son site (5 pages le jour du paiement, puis 1 par jour, jusqu'a 100).
La file est dans automation/onboarding_queue/<site>.json (creee par index_builder.py). Une page par client et par jour, au plus.
Variables : HUB_IMPORT_TOKEN ; DRY_RUN=1 (simulation) ; INDEX_MAX_DAYS (100).
"""
import os, sys, json, glob, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index_builder as ib  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

# 22/11/2026 : un cycle = un mois d'abonnement = 30 jours de publication.
MAX_DAYS = int(os.environ.get("INDEX_MAX_DAYS") or 30)


def log(m):
    print(f"[index-daily] {m}", flush=True)


def main():
    today = datetime.datetime.now(ZoneInfo("Europe/Paris")).date()
    files = sorted(glob.glob(os.path.join(ib.QUEUE_DIR, "*.json")))
    log(f"{len(files)} file(s) d'Index, aujourd'hui {today.isoformat()}.")
    for path in files:
        with open(path, encoding="utf-8") as f:
            q = json.load(f)
        if q.get("pause"):
            log(f"{q['site']} : en pause (abonnement resilie), rien a publier.")
            continue
        if q.get("pointer", 0) >= len(q.get("pages", [])):
            continue
        if q.get("last_publish") == today.isoformat():
            continue
        age = (today - datetime.date.fromisoformat(q.get("cycle_start") or q["created"])).days   # 20/11/2026 : le delai se compte depuis le debut du cycle mensuel
        if age > MAX_DAYS:
            log(f"{q['site']} : delai de {MAX_DAYS} jours depasse, file non publiee.")
            continue
        page = q["pages"][q["pointer"]]
        payload = {"site": q["site"], "create_site": q["podcast"], "podcast": q["podcast"], "publish": True,
                   "docs_theme": "mintlify", "cta_url": q.get("cta_url", ""), "cta_text": q.get("cta_text", "Learn more"),
                   "answers": [page], "dry_run": ib.DRY_RUN}
        if ib.DRY_RUN:
            log(f"[dry] {q['site']} : page {q['pointer'] + 1}/{len(q['pages'])} -> {page.get('question', '')[:70]}")
            continue
        res = ib.post_import(payload)
        if not res.get("ok"):
            log(f"ERREUR {q['site']} : {str(res.get('output', ''))[:200]}")
            continue
        q["pointer"] += 1
        q["live"] = q.get("live", ib.FIRST_BATCH) + 1
        q["last_publish"] = today.isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(q, f, ensure_ascii=False, indent=1)
        log(f"{q['site']} : {q['live']} pages en ligne (cycle {q.get('cycle', 1)} : {q['pointer']}/{len(q['pages'])})")


if __name__ == "__main__":
    main()

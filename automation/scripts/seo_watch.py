#!/usr/bin/env python3
"""
Veille indexation Google (29/09/2026) : photographie chaque jour l'etat SEO des fiches N1 et signale ce qui avance.
Lit gsc_hub_status.json (indexation des hubs), gsc_index_status.json (fiches question), gsc_pages.json (impressions/clics).
Ecrit pages/podcast-btb/data/seo_watch.json : historique + "alert" (texte pret a envoyer, id = date) quand quelque chose progresse
par rapport au dernier releve. Lu par la tache planifiee qui previent Etienne par mail.
"""
import json, datetime, os

D = "pages/podcast-btb/data"
OUT = f"{D}/seo_watch.json"


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def main():
    today = datetime.date.today().isoformat()
    hub = load(f"{D}/gsc_hub_status.json", {})
    q = load(f"{D}/gsc_index_status.json", {"urls": {}})
    gp = load(f"{D}/gsc_pages.json", {"pages": {}}).get("pages", {})
    names = {p.get("slug"): p.get("podcast_name") for p in load(f"{D}/podcasts.json", [])}
    state = load(OUT, {"history": [], "indexed_slugs": [], "alert": None})

    indexed = sorted(s for s, v in hub.items() if v.get("indexed_on"))
    hubs_imp = {u.rsplit("/", 1)[-1].replace("-podcast.html", ""): v for u, v in gp.items()
                if u.endswith("-podcast.html") and "/questions/" not in u}
    snap = {
        "date": today,
        "hubs_checked": sum(1 for v in hub.values() if v.get("date")),
        "hubs_indexed": len(indexed),
        "hubs_with_impressions": sum(1 for v in hubs_imp.values() if v.get("impressions", 0) > 0),
        "hub_impressions": sum(v.get("impressions", 0) for v in hubs_imp.values()),
        "hub_clicks": sum(v.get("clicks", 0) for v in hubs_imp.values()),
        "questions_indexed": sum(1 for v in q.get("urls", {}).values()
                                 if v.get("verdict") == "PASS" or "submitted and indexed" in (v.get("coverage") or "").lower()),
    }
    # 10 fiches N1 a soumettre a Google aujourd'hui : les plus recentes, CONFIRMEES non indexees par l'inspection
    # (jamais une fiche non verifiee), et pas deja proposees un jour precedent. Recalcule a chaque run du jour.
    podcasts = load(f"{D}/podcasts.json", [])
    listed = {s_: d_ for s_, d_ in (state.get("listed") or {}).items() if d_ != today}
    recent = datetime.date.today() - datetime.timedelta(days=30)
    cand = [p for p in podcasts if p.get("slug") in hub and hub[p["slug"]].get("date")
            and not hub[p["slug"]].get("indexed_on") and p["slug"] not in listed and p.get("fiche_url")]
    # 01/10/2026 : ordre de priorite = prospects d'abord (extraits > en attente > deja contactes), puis N1 anciennes
    # jamais explorees, puis le reste (les plus anciennes d'abord) ; les refusees par Google en dernier.
    try:
        import n1_priority as _np
        _q = load("automation/marketforge_engine/queue.json", {"podcasts": {}}).get("podcasts", {})
        cand.sort(key=lambda p: _np.rank_key(p["slug"], str(p.get("date", ""))[:10], _q.get(p["slug"], {}).get("status", ""),
                                             hub[p["slug"]].get("coverage", "")))
    except Exception:  # noqa: BLE001  (garde-fou : ancien tri si le module de priorite est indisponible)
        cand.sort(key=lambda p: (str(p.get("date", ""))[:10], p["slug"]), reverse=True)
    pick = cand[:10]
    for p_ in pick:
        listed[p_["slug"]] = today
    state["listed"] = listed
    state["submit"] = {"date": today, "urls": [{"url": p_["fiche_url"], "name": p_.get("podcast_name", ""),
                                                 "created": str(p_.get("date", ""))[:10]} for p_ in pick]}
    prev = state["history"][-1] if state["history"] else None
    new_idx = [s for s in indexed if s not in set(state.get("indexed_slugs", []))]
    if prev is None:
        new_idx = []           # 1er releve : simple base de comparaison, pas d'alerte
    lines = []
    if new_idx:
        lines.append(f"{len(new_idx)} fiche(s) N1 détectée(s) indexée(s) par Google (vérifiées aujourd’hui, pas forcément indexées aujourd’hui) : " + ", ".join(names.get(s) or s for s in new_idx[:15])
                     + (" …" if len(new_idx) > 15 else ""))
    if prev:
        for k, label in (("hubs_with_impressions", "hubs qui apparaissent dans Google"), ("hub_clicks", "clics sur les hubs")):
            if snap[k] > prev.get(k, 0):
                lines.append(f"{label} : {prev.get(k, 0)} → {snap[k]}")
        if snap["hub_impressions"] >= prev.get("hub_impressions", 0) * 1.25 and snap["hub_impressions"] - prev.get("hub_impressions", 0) >= 20:
            lines.append(f"impressions des hubs : {prev.get('hub_impressions', 0)} → {snap['hub_impressions']}")
    if lines:
        state["alert"] = {"id": today, "lines": lines, "snapshot": snap}
    if state["history"] and state["history"][-1]["date"] == today:
        state["history"][-1] = snap
    else:
        state["history"].append(snap)
    state["history"] = state["history"][-120:]
    state["indexed_slugs"] = indexed
    state["updated"] = datetime.datetime.utcnow().isoformat(timespec="minutes")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"[seo-watch] {snap} | alerte : {'oui' if lines else 'non'}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"[seo-watch] ignore (non bloquant) : {e}")

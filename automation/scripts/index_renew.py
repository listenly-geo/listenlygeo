#!/usr/bin/env python3
"""
Renouvellement mensuel des Index clients et mise en pause a la resiliation (20/11/2026, decision d'Etienne).

Chaque jour, pour chaque client paye (onglet Onboarding), l'etat de son abonnement Stripe est lu via le pont Apps Script :
  - abonnement resilie / impaye (canceled, unpaid, incomplete_expired) -> la file du client est mise en PAUSE (rien de nouveau n'est publie ;
    les pages deja en ligne restent) + mail au client et alerte a Etienne ;
  - abonnement actif ou en essai -> la pause est levee si elle existait ;
  - abonnement actif, nouvelle periode commencee, file du mois epuisee, pas de resiliation programmee -> les 30 pages du mois suivant sont
    extraites des NOUVEAUX episodes (jamais les memes), mises en file (1 par jour, index_daily.py) + mail au client.
Un client en retard de paiement (past_due) n'est ni renouvele ni mis en pause : Stripe relance la carte.

Usage : python index_renew.py sync       (pause / reprise + compte les renouvellements dus -> sortie GitHub n=)
        python index_renew.py            (pause / reprise + renouvellements : extraction audio)
        python index_renew.py reminders  (relances automatiques : onboarding non rempli, DNS non fait, rappel Google)
Variables : MFE_SHEET_URL, HUB_IMPORT_TOKEN, cles IA (comme index_builder), DRY_RUN=1 (simulation : aucun mail, aucune extraction).
"""
import os, sys, json, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet_bridge as sb  # noqa: E402
import index_builder as ib  # noqa: E402
import marketforge_extract_queue as xq  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

DRY = ib.DRY_RUN
STOP = {"canceled", "unpaid", "incomplete_expired"}
GO = {"trialing", "active"}
TZ = ZoneInfo("Europe/Paris")


def log(m):
    print(f"[index-renew] {m}", flush=True)


def qpath(site):
    return os.path.join(ib.QUEUE_DIR, site + ".json")


def load(site):
    try:
        with open(qpath(site), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save(q):
    if DRY:
        return
    with open(qpath(q["site"]), "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=1)


def subscriptions():
    j = sb.call(payload={"action": "onboarding_subscriptions"})
    if not (isinstance(j, dict) and j.get("ok")):
        raise RuntimeError(f"pont injoignable ou refuse : {str(j)[:200]}")
    return j.get("rows", [])


def notify(r, kind, pages=0):
    if DRY:
        log(f"[dry] mail '{kind}' -> {r.get('email')}")
        return
    try:
        sb.call(payload={"action": "onboarding_notify", "row": r["row"], "kind": kind, "site": r["site"], "pages": pages})
    except Exception as e:
        log(f"mail '{kind}' non envoye : {e}")


def period_start(r):
    ps = r.get("period_start")
    return datetime.datetime.fromtimestamp(int(ps), TZ).date() if ps else None


def is_due(r, q, today):
    if r.get("status") != "active" or r.get("cancel") or q.get("pause"):
        return False
    start = period_start(r)
    if not start:
        return False
    cycle_start = datetime.date.fromisoformat(q.get("cycle_start") or q["created"])
    retry = q.get("renew_retry")
    if retry and datetime.date.fromisoformat(retry) > today:
        return False
    return start > cycle_start and q.get("pointer", 0) >= len(q.get("pages", []))


def sync(today):
    """Pause / reprise selon l'abonnement. Retourne la liste des (ligne, file) dont le renouvellement est du."""
    due = []
    for r in subscriptions():
        site, st = r.get("site"), r.get("status")
        if r.get("error"):
            log(f"{site} : Stripe illisible ({r['error']}), on ne touche a rien.")
            continue
        q = load(site)
        if not q:
            log(f"{site} : pas de file (abonnement {st}), ignore.")
            continue
        if st in STOP and not q.get("pause"):
            q["pause"] = True
            save(q)
            log(f"{site} : abonnement {st} -> PAUSE.")
            notify(r, "paused")
        elif st in GO and q.get("pause"):
            q["pause"] = False
            save(q)
            log(f"{site} : abonnement {st} -> production reprise.")
            notify(r, "resumed")
        if is_due(r, q, today):
            due.append((r, q))
        else:
            log(f"{site} : abonnement {st}, cycle {q.get('cycle', 1)}, rien a renouveler.")
    return due


def renew(r, q, today):
    site, name = q["site"], q["podcast"]
    log(f"=== Renouvellement {site} (cycle {q.get('cycle', 1) + 1}) ===")
    if DRY:
        log(f"[dry] {site} : extraction des 30 pages du mois suivant.")
        return
    episodes, _contact = xq.read_rss(r["rss"])
    used = set(q.get("used_episodes", []))
    fresh = [e for e in episodes if e.get("audio_url") and e.get("title") not in used]
    fresh = sorted(fresh, key=lambda e: 0 if e.get("transcript_url") else 1)[: ib.QUEUE_EPISODES * 2]
    retry = (today + datetime.timedelta(days=7)).isoformat()
    if not fresh:
        q["renew_retry"] = retry
        save(q)
        log(f"{site} : aucun nouvel episode, nouvel essai dans 7 jours.")
        return
    podcast = {"slug": ib.slugify(name), "podcast_name": name, "rss_url": r["rss"], "language": "en"}
    answers = ib.extract_answers(podcast, fresh, ib.AUDIO_MIN, ib.QUEUE_EPISODES)
    keys, uniq = set(q.get("keys", [])), []
    for a in answers:
        k = ib.qkey(a["question"])
        if k and k not in keys:
            keys.add(k)
            uniq.append(a)
    uniq = uniq[: ib.QUEUE_MAX]
    if not uniq:
        q["renew_retry"] = retry
        save(q)
        log(f"{site} : aucune nouvelle reponse exploitable, nouvel essai dans 7 jours.")
        return
    q.update({"pages": uniq, "pointer": 0, "last_publish": "", "cycle": q.get("cycle", 1) + 1,
              "cycle_start": period_start(r).isoformat(), "keys": sorted(keys),
              "used_episodes": sorted(used | {a["episode"] for a in uniq})})
    q.pop("renew_retry", None)
    save(q)
    log(f"{site} : {len(uniq)} nouvelles pages en file (cycle {q['cycle']}).")
    notify(r, "renewed", len(uniq))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if not sb.URL:
        log("MFE_SHEET_URL manquant : rien a faire.")
        return
    today = datetime.datetime.now(TZ).date()
    if mode == "reminders":
        if DRY:
            log("[dry] relances non envoyees.")
            return
        log(f"Relances : {sb.call(payload={'action': 'onboarding_reminders'})}")
        return
    due = sync(today)
    log(f"{len(due)} renouvellement(s) du(s).")
    if mode == "sync":
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a") as f:
                f.write(f"n={len(due)}\n")
        return
    for r, q in due:
        try:
            renew(r, q, today)
        except Exception as e:
            log(f"ERREUR {q['site']} : {type(e).__name__}: {str(e)[:300]}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Moteur autonome des pages de moment (15/10/2026). v1.

Chaque nuit, il :
1. calcule le score de chaque moment sur 100 (forme de la question 30, sujet metier 25, richesse de la
   reponse 20, credibilite de l'intervenant 15, maillage 10) ;
2. lit les requetes Search Console qui font apparaitre chaque page (historique listenly.fr, suite listenly.org)
   et ajoute un bonus de tri (jamais un bonus de score) ;
3. adapte le rythme d'ouverture a Google selon le taux d'indexation observe (lots qui grandissent seulement
   si Google indexe, qui ralentissent si Google ne suit pas) ;
4. limite le nombre de nouvelles pages par podcast pour ne pas faire pousser un seul podcast ;
5. liste les podcasts qui meritent un hub (seuil : au moins 3 moments de qualite) ;
6. propose des titres alignes sur les requetes reelles, sans les publier (validation humaine d'abord) ;
7. ecrit un etat et un bilan dans data/moteur_autonome_etat.json.

Ce script ne supprime aucune page, ne touche a aucune redirection, ne publie aucun titre.
Le generateur de sitemap (generate_moments_sitemap.py) lit son etat pour l'ordre et le plafond par podcast.

Usage : python3 automation/scripts/moteur_autonome_moments.py
"""
import os, re, json, glob, datetime, collections

PAGES = "pages/podcast-btb"
MOMENTS = f"{PAGES}/data/moments"
GSC_PAGES = f"{PAGES}/data/gsc_pages.json"
INDEX_STATUS = f"{PAGES}/data/indexation_moments.json"
ETAT = f"{PAGES}/data/moteur_autonome_etat.json"
SCORES = f"{PAGES}/data/moments_scores.json"
HUBS = f"{PAGES}/data/hubs_candidats.json"
TITRES = f"{PAGES}/data/titres_proposes.json"

QUESTION_START = ("how", "what", "why", "should", "are", "is", "do", "does", "can", "when", "which")
BUSINESS = [
    "growth", "revenue", "margin", "pricing", "cash", "finance", "investment", "valuation", "profit",
    "operations", "supply", "logistics", "freight", "procurement", "marketing", "sales", "customer",
    "hiring", "leadership", "strategy", "culture", "ai", "automation", "compliance", "risk", "cyber",
    "market", "brand", "product", "team", "saas", "b2b", "payroll", "tax", "budget", "decision",
    "framework", "process", "efficiency", "scale", "funding", "acquisition", "retention",
]


QWORDS = r"^(what|why|how|when|where|who|which|is|are|does|do|can|should|could|would|will|did|was|were)\s+"
FILL = r"^(is|are|does|do|the|a|an|of|to|for|in|on|that|this|it|be|being)\s+"


def seo_title(question, max_len=58, brand="Listenly"):
    """Brouillon de titre SEO (rapport du 15/10/2026) : sans mot interrogatif, 50 a 58 caracteres, marque a la fin.
    Brouillon uniquement : chaque titre est relu avant publication."""
    s = re.sub(r"[?.!]+$", "", (question or "").strip())
    s = re.sub(QWORDS, "", s, flags=re.I)
    s = re.sub(FILL, "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    suffix = f" | {brand}"
    room = max_len - len(suffix)
    core = s
    if len(core) > room:
        out = ""
        for w in core.split():
            cand = (out + " " + w).strip()
            if len(cand) > room:
                break
            out = cand
        core = out or core[:room]
    title = core + suffix if len(core) + len(suffix) <= max_len else core
    if title and title[0].islower():
        title = title[0].upper() + title[1:]
    return {"titre": title, "caracteres": len(title), "alerte_longueur": len(title) > 65}


def wc(s):
    return len(str(s or "").split())


def answer_text(e):
    paras = [str(x).strip() for x in (e.get("f") or []) if str(x).strip()]
    if not paras and (e.get("a") or "").strip():
        paras = [e["a"].strip()]
    return " ".join(paras), len(paras)


def named_run(q):
    """Vrai si la question contient 2 mots capitalises consecutifs apres le premier mot (nom propre)."""
    words = q.split()
    run = best = 0
    for w in words[1:]:
        if re.match(r"^[A-Z][a-zA-Z\-]+[,.]?$", w):
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best >= 2


def content_score(e, related_count):
    q = (e.get("q") or "").strip()
    ans, nparas = answer_text(e)
    detail = {}
    # 1. forme de la question (30)
    forme = 30 if q.lower().startswith(QUESTION_START) else 10
    if re.search(r"\d", q):
        forme -= 15
    if named_run(q):
        forme -= 10
    if re.search(r"\b(first|initial|how many|how much|what percentage|what was the|in what year|which year|exact|precise)\b", q.lower()):
        forme -= 15
    forme = max(0, forme)
    detail["forme"] = forme
    # 2. sujet metier (25)
    blob = (q + " " + ans).lower()
    hits = sum(1 for k in BUSINESS if re.search(r"\b" + re.escape(k) + r"\b", blob))
    sujet = 25 if hits >= 3 else 15 if hits >= 1 else 5
    detail["sujet"] = sujet
    # 3. richesse de la reponse (20)
    rich = (8 if nparas >= 2 else 3) + (7 if wc(ans) >= 150 else 3 if wc(ans) >= 60 else 0) + (5 if re.search(r"\d", ans) else 0)
    detail["richesse"] = min(rich, 20)
    # 4. credibilite de l'intervenant (15)
    cred = (8 if (e.get("x") or "").strip() else 0) + (7 if (e.get("gt") or "").strip() else 0)
    detail["credibilite"] = cred
    # 5. maillage (10)
    mail = 10 if related_count >= 3 else 5 if related_count >= 1 else 0
    detail["maillage"] = mail
    return forme + sujet + min(rich, 20) + cred + mail, detail


def nparas_ok(e):
    """Porte d'entree : reponse complete en au moins deux paragraphes."""
    _, n = answer_text(e)
    return n >= 2


def rich_ok(e):
    """Regle de richesse identique a m.php et generate_moments_sitemap.py."""
    ans, _ = answer_text(e)
    stats = " ".join(str(x).strip() for x in (e.get("ks") or []) if str(x).strip())
    return (wc(ans) >= 25 and int(e.get("t") or 0) > 0 and (e.get("x") or "").strip() != ""
            and (e.get("u") or "").startswith("http") and (e.get("q") or "").strip() != "")


def search_signals():
    """{url_moment_path: (impressions, clics, requetes)} depuis gsc_pages.json, pour les pages /m/."""
    out = {}
    try:
        d = json.load(open(GSC_PAGES, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    for u, v in (d.get("pages") or {}).items():
        m = re.search(r"/podcast-btb/m/([^/]+)/([a-f0-9]+)", u)
        if m:
            out[f"{m.group(1)}/{m.group(2)}"] = (v.get("impressions", 0), v.get("clicks", 0), v.get("queries") or [])
    return out


def indexation_rate():
    """Taux d'indexation des moments inspectes : (taux en %, nombre inspecte)."""
    try:
        d = json.load(open(INDEX_STATUS, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, 0
    items = d.get("urls") if isinstance(d, dict) and "urls" in d else d
    rows = list(items.values()) if isinstance(items, dict) else items or []
    inspected = [r for r in rows if isinstance(r, dict) and r.get("coverage")]
    if not inspected:
        return None, 0
    indexed = sum(1 for r in inspected if (r.get("verdict") == "PASS" or "indexed" in str(r.get("coverage", "")).lower()) and "not indexed" not in str(r.get("coverage", "")).lower())
    return round(100 * indexed / len(inspected), 1), len(inspected)


def next_cap(current, rate, inspected, cfg):
    """Rythme : grandit seulement si Google indexe ; ralentit si Google ne suit pas ; sinon stable."""
    lo, hi = int(cfg.get("moments_par_jour_min", 30)), int(cfg.get("moments_par_jour_max", 500))
    if rate is None or inspected < 30:
        return current, "pas assez de pages inspectees : rythme stable"
    if rate >= 40:
        return min(int(current * 1.5), hi), f"indexation {rate}% sur {inspected} pages : rythme +50%"
    if rate < 15 and inspected >= 60:
        return max(int(current * 0.7), lo), f"indexation {rate}% sur {inspected} pages : rythme -30%"
    return current, f"indexation {rate}% sur {inspected} pages : rythme stable"


def kp_best(question):
    """Volume mensuel (Keyword Planner) de la requete la plus proche de la question, ou None si non branche."""
    try:
        d = json.load(open("pages/podcast-btb/data/keyword_planner.json", encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if d.get("statut") != "connecte":
        return None
    qw = set(re.findall(r"[a-z]{4,}", question.lower()))
    best = None
    for idea in d.get("idees", []):
        iw = set(re.findall(r"[a-z]{4,}", (idea.get("requete") or "").lower()))
        if qw and iw and len(qw & iw) / len(iw) >= 0.6:
            v = idea.get("volume_mensuel_moyen", 0)
            best = v if best is None else max(best, v)
    return best if best is not None else 0


def main():
    try:
        cfg = json.load(open("automation/marketforge_engine/trafic_seo.json", encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cfg = {}
    signals = search_signals()
    rate, inspected = indexation_rate()
    try:
        etat_prev = json.load(open(ETAT, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        etat_prev = {}
    base_cap = int(etat_prev.get("moments_par_jour", cfg.get("moments_par_jour", 30)))
    cap, raison = next_cap(base_cap, rate, inspected, cfg)

    scores = {}
    per_podcast_good = collections.Counter()
    titres = []
    for f in sorted(glob.glob(f"{MOMENTS}/*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        slug = d.get("slug") or os.path.basename(f)[:-5]
        entries = d.get("entries") or {}
        by_ep = collections.Counter(e.get("e") or "" for e in entries.values() if isinstance(e, dict) and answer_text(e)[0])
        for mid, e in entries.items():
            if not isinstance(e, dict) or not rich_ok(e):
                continue
            ans, _ = answer_text(e)
            related = max(by_ep.get(e.get("e") or "", 0) - 1, 0)
            s, detail = content_score(e, related)
            key = f"{slug}/{mid}"
            imp, clics, queries = signals.get(key, (0, 0, []))
            bonus = (5 if imp > 0 else 0) + (5 if clics > 0 else 0)
            scores[key] = {"score": s, "detail": detail, "bonus_recherche": bonus,
                           "impressions": imp, "clics": clics, "podcast": slug, "gate": False,
                           "question": e.get("q"), "t": int(e.get("t") or 0)}
            gate = nparas_ok(e) and s >= 70
            scores[key]["gate"] = gate
            # Demande (20 pts) : Keyword Planner si branche, sinon Search Console (impressions 10, clics 20)
            kp = kp_best(e.get("q") or "")
            if kp is not None:
                demande = min(20, round(20 * min(kp, 1000) / 1000))
            else:
                demande = 20 if clics > 0 else 10 if imp > 0 else 0
            scores[key]["demande"] = demande
            scores[key]["score_final"] = round(s * 0.8 + demande)
            if gate:
                per_podcast_good[slug] += 1
            # titre propose : une requete reelle dont les mots sont presents dans la reponse
            for qr in queries[:3]:
                qtext = (qr.get("query") if isinstance(qr, dict) else str(qr)) or ""
                qw = set(re.findall(r"[a-z]{4,}", qtext.lower()))
                aw = set(re.findall(r"[a-z]{4,}", ans.lower()))
                if qw and len(qw & aw) / len(qw) >= 0.6 and qtext.lower() not in (e.get("q") or "").lower():
                    titres.append({"page": key, "titre_actuel": e.get("q"), "requete_reelle": qtext,
                                   "statut": "a_valider"})
                    break

    # brouillons de titres pour les 30 meilleures pages de qualité (relecture humaine avant toute publication)
    meilleures = sorted((k for k, v in scores.items() if v.get("gate")), key=lambda k: -scores[k]["score_final"])[:30]
    for key in meilleures:
        t = seo_title(scores[key].get("question") or "")
        titres.append({"page": key, "titre_actuel": scores[key].get("question"), "titre_propose": t["titre"],
                       "caracteres": t["caracteres"], "alerte_longueur": t["alerte_longueur"],
                       "statut": "brouillon_a_relire"})
    hubs = {p: n for p, n in per_podcast_good.items() if n >= 3}
    max_par_podcast = 3 if rate is None or rate < 40 else 6

    os.makedirs(os.path.dirname(SCORES), exist_ok=True)
    json.dump(scores, open(SCORES, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    json.dump({"date": datetime.date.today().isoformat(), "podcasts": hubs},
              open(HUBS, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    json.dump({"date": datetime.date.today().isoformat(), "propositions": titres[:200]},
              open(TITRES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    etat = {
        "date": datetime.date.today().isoformat(),
        "moments_par_jour": cap,
        "raison_rythme": raison,
        "max_par_podcast": max_par_podcast,
        "taux_indexation_pct": rate,
        "pages_inspectees": inspected,
        "moments_qualite": len(scores),
        "porte_entree_complete": sum(1 for v in scores.values() if v.get("gate")),
        "hubs_candidats": len(hubs),
        "titres_a_valider": len(titres),
        "recherche_keyword_planner": "non connecte",
    }
    json.dump(etat, open(ETAT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(etat, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

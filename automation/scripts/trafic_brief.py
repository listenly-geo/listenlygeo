#!/usr/bin/env python3
"""Synthese quotidienne du moteur trafic SEO (lue par la tache planifiee 'Mission trafic SEO').
Entrees : data/gsc/*.json (gsc_pull.py), pages/podcast-btb/data/moments_sitemap_state.json, automation/marketforge_engine/trafic_seo.json
Sorties : data/gsc/brief.json et data/gsc/brief.md (courts, pour decider en 1 minute). Ne modifie aucun reglage."""
import os, re, json, datetime, urllib.parse

G = "data/gsc"
today = datetime.date.today()


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return d


def kind(u):
    if "/podcast-btb/m/" in u: return "moment"
    if "/podcast-btb/questions/" in u: return "fiche-question"
    if "/podcast-btb/categorie/" in u: return "categorie"
    if re.search(r"/podcast-btb/[^/]+\.html$", u): return "hub"
    if "/podcast/show/" in u: return "show-listenly"
    if re.sub(r"^https://(www\.)?listenly\.(fr|org)/?$", "", u.rstrip("/") + "/") == "" : return "accueil"
    return "autre"


def main():
    pages = load(f"{G}/pages.json", [])
    req = load(f"{G}/requetes.json", [])
    mom_q = load(f"{G}/pages_requetes_moments.json", [])
    ix = load(f"{G}/indexation_moments.json", {})
    resume = load(f"{G}/resume.json", {})
    cfg = load("automation/marketforge_engine/trafic_seo.json", {})
    st = load("pages/podcast-btb/data/moments_sitemap_state.json", {}).get("released", {})

    par_type = {}
    for p in pages:
        a = par_type.setdefault(kind(p["page"]), {"pages": 0, "clics": 0, "impressions": 0})
        a["pages"] += 1; a["clics"] += p["clics"]; a["impressions"] += p["impressions"]

    # indexation des pages de moments ouvertes il y a >= 7 jours
    vieux = [k for k, d in st.items() if (today - datetime.date.fromisoformat(d)).days >= 7]
    controles = [k for k in vieux if k in ix and ix[k].get("etat") != "erreur"]
    indexees = [k for k in controles if ix[k]["etat"] == "indexee"]
    taux = round(100 * len(indexees) / len(controles), 1) if controles else None
    cap = int(cfg.get("moments_par_jour", 30)); mx = int(cfg.get("moments_par_jour_max", 100)); mn = int(cfg.get("moments_par_jour_min", 15))
    step = int(cfg.get("variation_max_par_jour", 15))
    if taux is None:
        reco, why = cap, "pas assez de pages ouvertes depuis 7 jours et controlees : on ne change pas"
    elif taux >= 40:
        reco, why = min(cap + step, mx), f"{taux}% indexees : on peut accelerer"
    elif taux < 15 and len(controles) >= 60:
        reco, why = max(cap - step, mn), f"{taux}% indexees sur {len(controles)} pages : ralentir et enrichir"
    else:
        reco, why = cap, f"{taux}% indexees : on garde le rythme"

    # 10 pages de moments a faire indexer a la main aujourd'hui : ouvertes, controlees non indexees (ou jamais controlees)
    cand = [k for k, d in sorted(st.items(), key=lambda kv: kv[1], reverse=True)
            if (ix.get(k, {}).get("etat") in (None, "inconnue", "detectee_non_indexee"))][:10]
    site = os.environ.get("GSC_SITE", "sc-domain:listenly.fr")   # propriete Search Console active (change au moment de la bascule .fr -> .org)
    host = site.replace("sc-domain:", "")
    base = "https://search.google.com/u/1/search-console/inspect?resource_id=" + urllib.parse.quote(site, safe="") + "&id="
    a_indexer = [{"page": f"https://{host}/podcast-btb/m/{k}", "etat": ix.get(k, {}).get("etat", "jamais controlee"),
                  "lien_gsc": base + urllib.parse.quote(f"https://{host}/podcast-btb/m/{k}", safe="")} for k in cand]

    # pages deja visibles mais peu cliquees (positions 3 a 15) : a retravailler (titre / extrait)
    ctr = sorted([p for p in pages if 3 <= p["position"] <= 15 and p["impressions"] >= 8 and p["clics"] == 0],
                 key=lambda p: -p["impressions"])[:10]
    emergentes = sorted([r for r in req if r["impressions"] >= 3 and r["position"] <= 20], key=lambda r: r["position"])[:15]

    brief = {"date": str(today), "periode": resume.get("periode"), "totaux": {k: resume.get(k) for k in ("pages", "clics", "impressions", "pages_moments", "clics_moments", "impressions_moments")},
             "par_type": par_type,
             "moments": {"ouvertes_total": len(st), "ouvertes_depuis_7j": len(vieux), "controlees": len(controles), "indexees": len(indexees),
                         "taux_indexation_pct": taux, "etats": (load(f"{G}/indexation_resume.json", {}) or {}).get("par_etat")},
             "quota": {"actuel": cap, "recommande": reco, "raison": why},
             "a_demander_a_la_main_aujourdhui": a_indexer,
             "pages_visibles_sans_clic": [{"page": p["page"], "impr": p["impressions"], "pos": p["position"]} for p in ctr],
             "requetes_bien_placees": [{"requete": r["requete"], "impr": r["impressions"], "pos": r["position"], "clics": r["clics"]} for r in emergentes],
             "requetes_sur_pages_moments": mom_q[:15]}
    json.dump(brief, open(f"{G}/brief.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    L = [f"# Brief trafic SEO — {today}", "",
         f"- Période {brief['periode']} : {brief['totaux']['clics']} clics / {brief['totaux']['impressions']} impressions sur {brief['totaux']['pages']} pages",
         f"- Pages de moments dans Google : {brief['totaux']['pages_moments']} pages, {brief['totaux']['impressions_moments']} impressions, {brief['totaux']['clics_moments']} clics",
         f"- Moments ouverts au sitemap : {len(st)} (dont {len(vieux)} depuis 7 j+) ; contrôlés : {len(controles)} ; indexés : {len(indexees)} ({taux}%)",
         f"- Quota : {cap}/jour → recommandé {reco}/jour ({why})", "", "## Par type de page"]
    for k, a in sorted(par_type.items(), key=lambda kv: -kv[1]["impressions"]):
        L.append(f"- {k} : {a['pages']} pages, {a['impressions']} impr., {a['clics']} clics")
    L += ["", "## 10 pages de moments à faire indexer à la main aujourd'hui"] + [f"- {x['page']} ({x['etat']})" for x in a_indexer]
    L += ["", "## Pages visibles (positions 3-15) sans clic : titre/extrait à retravailler"] + [f"- {p['page']} — {p['impressions']} impr., pos {p['position']}" for p in ctr]
    L += ["", "## Requêtes bien placées"] + [f"- {r['requete']} — {r['impressions']} impr., pos {r['position']}, {r['clics']} clic(s)" for r in emergentes]
    open(f"{G}/brief.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("Brief ecrit :", brief["quota"], "| indexation moments :", taux)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print("[brief] ignore (non bloquant) :", e)

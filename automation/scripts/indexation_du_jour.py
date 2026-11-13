#!/usr/bin/env python3
"""Chaque jour : choisit 10 pages de moments a faire indexer, verifie chaque URL .org et son etat
dans la Search Console (API d'inspection, lecture seule), ecrit pages/podcast-btb/data/indexation_du_jour.json.
Selection : pages de MOMENTS validees par le systeme (gate=True), pas les fiches question.
La demande d'indexation elle-meme se fait a la main (session Claude + Chrome, validation par page).
Secret : GSC_SERVICE_ACCOUNT_JSON. Ne bloque jamais le workflow : en cas d'erreur, la liste est ecrite quand meme."""
import os, json, datetime
import requests

PAGES = "pages/podcast-btb"
OUT = f"{PAGES}/data/indexation_du_jour.json"
SITE = os.environ.get("GSC_SITE", "sc-domain:listenly.org")
BASE = "https://listenly.org/podcast-btb/"
N = 10
RETARD = []    # slug/id des fiches en retard (non demandees la veille), prioritaires
SOURCES = {}   # slug/id -> "connu" | "mot_cle" (08/11/2026 : repartition 50/50 pendant 14 jours, puis reglage selon la Search Console)
QUOTA_CONNU = 5
QUOTA_MOTCLE = 5


def volumes_motcle():
    """08/11/2026 : volumes Google Ads des questions du reservoir (volume_reservoir_connus.py). {slug/id: volume}.
    Seules les questions a 100 recherches/mois ou plus sont des fiches 'mot-cle'."""
    import hashlib, re
    try:
        d = json.load(open("automation/moments_connus/volumes_reservoir.json", encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if d.get("statut") != "connecte":
        return {}
    out = {}
    for v in d.get("items", {}).values():
        if v.get("volume", 0) >= 100:
            norm = re.sub(r"\s+", " ", (v["question"] or "").strip().lower())
            mid = hashlib.sha1(f"{v['podcast_slug']}|{norm}".encode("utf-8")).hexdigest()[:10]
            out[f"{v['podcast_slug']}/{mid}"] = v["volume"]
    return out


def choisir():
    """Methode du 17/10/2026 : d'abord la DEMANDE reelle (volume Google Ads du theme de la fiche),
    puis la note. Seules les fiches avec un volume > 0 sont retenues. Plafond 3 par podcast.
    Exclut les pages deja demandees (indexation_demandees.json et index_requests.json)."""
    scores = json.load(open(f"{PAGES}/data/moments_scores.json", encoding="utf-8"))
    scores = scores.get("scores", scores)
    try:
        dem_raw = json.load(open(f"{PAGES}/data/demande_par_fiche.json", encoding="utf-8"))
        demande = dem_raw.get("fiches", {})
        # 26/10/2026 : si les volumes ne sont pas du jour (Keyword Planner en echec), on ne les utilise pas.
        # La selection continue alors avec la seule note de qualite (score_final).
        if str(dem_raw.get("date", ""))[:10] != datetime.date.today().isoformat():
            demande = {}
    except (OSError, json.JSONDecodeError):
        demande = {}
    deja = set()
    for f in ("indexation_demandees.json", "index_requests.json", "indexees_verifiees.json"):  # 02/11/2026 : pages verifiees indexees
        try:
            d = json.load(open(f"{PAGES}/data/{f}", encoding="utf-8"))
            if isinstance(d, dict):
                # 28/10/2026 : "urls_en_attente" = pages NON demandees (quota/outil absent) -> restent proposables.
                for kq, v in d.items():
                    if kq == "urls_en_attente":
                        continue
                    if isinstance(v, list):
                        deja.update(x for x in v if isinstance(x, str))
                    elif isinstance(v, dict):
                        # 21/10/2026 : journal par date (urls_demandees, deja_indexees)
                        # 28/10/2026 : une journee ou "0 demande envoyee" ne fait exclure aucune de ses URL.
                        aucune = v.get("urls_demandees") == 0 or str(v.get("resultat", "")).startswith("0 demande")
                        for kk in ("urls_demandees", "deja_indexees", "urls"):
                            if aucune and kk == "urls":
                                continue
                            val = v.get(kk, [])
                            if isinstance(val, list):
                                deja.update(x for x in val if isinstance(x, str))
                # 21/10/2026 : seules les URL REELLEMENT demandees ou deja indexees sont exclues.
                # Les entrees "en attente" (non demandees faute de Claude in Chrome) restent proposables.
                for h in d.get("historique", []):
                    txt = (h.get("resultat", "") + " " + h.get("essai", ""))
                    # 28/10/2026 : "0 demande envoyee" = rien n'a ete demande, donc rien a exclure.
                    if "en attente" in txt or "NON demandee" in txt or h.get("urls_demandees") == 0 \
                            or str(h.get("resultat", "")).startswith("0 demande"):
                        continue
                    deja.update(h.get("urls", []))
        except (OSError, json.JSONDecodeError):
            pass
    # 09/11/2026 (Etienne) : REGLE — les fiches choisies mais NON demandees faute de quota/outil (urls_en_attente du
    # journal) passent AVANT TOUTES LES AUTRES le lendemain, tant qu'elles ne sont ni demandees ni indexees.
    retard = []
    try:
        jr = json.load(open(f"{PAGES}/data/index_requests.json", encoding="utf-8"))
        for kd in sorted(jr):
            v = jr[kd]
            if isinstance(v, dict):
                for u in (v.get("urls_en_attente") or []):
                    if isinstance(u, str) and "/podcast-btb/m/" in u and u not in deja and u not in retard:
                        retard.append(u)
    except (OSError, json.JSONDecodeError):
        pass
    RETARD.clear()
    RETARD.extend(u.split("/podcast-btb/m/", 1)[1].strip("/") for u in retard)
    # 18/10/2026 : seuls les podcasts des niveaux ouverts (trafic_seo.json > niveaux_ouverts) sont proposes
    try:
        niv = json.load(open(f"{PAGES}/data/priorite_podcasts.json", encoding="utf-8")).get("niveaux", {})
        ouverts = set(json.load(open("automation/marketforge_engine/trafic_seo.json", encoding="utf-8")).get("niveaux_ouverts") or ["A"])
    except (OSError, json.JSONDecodeError):
        niv, ouverts = {}, {"A"}
    # 21/10/2026 : une page n'est proposee a l'indexation que si son titre SEO est deja ecrit
    # (titres_seo.json, cle slug/id). Sans titre, on ne demande pas l'indexation.
    try:
        titres = json.load(open(f"{PAGES}/data/titres_seo.json", encoding="utf-8"))
        titres = titres.get("titres", titres)
    except (OSError, json.JSONDecodeError):
        titres = {}
    # 02/11/2026 : niveau B ouvert seulement pour les podcasts qui ont deja des clics, et seulement quand
    # le stock titre du niveau A passe sous 20 fiches.
    try:
        prouves = {x["podcast"] for x in json.load(open("data/gsc/resultats_par_podcast.json", encoding="utf-8")).get("detail", []) if x.get("clics", 0) > 0}
    except (OSError, json.JSONDecodeError):
        prouves = set()
    stock_A = sum(1 for key, v in scores.items()
                  if isinstance(v, dict) and v.get("gate") and niv.get(key.split("/", 1)[0], "C") == "A"
                  and titres.get(key) and BASE + "m/" + key not in deja)
    ouvrir_B = stock_A < 20
    cands = []
    motcle = volumes_motcle()
    # 08/11/2026 : les fiches rallongees aujourd'hui (enrichir_du_jour.py) passent en premier dans leur groupe
    try:
        enrichies = set(json.load(open(f"{PAGES}/data/enrichies_du_jour.json", encoding="utf-8")).get("cles", []))
    except (OSError, json.JSONDecodeError):
        enrichies = set()
    for key, v in scores.items():
        if not isinstance(v, dict) or not v.get("gate"):
            continue
        lvl = niv.get(key.split("/", 1)[0], "C")
        vol = (demande.get(key) or {}).get("volume", 0)
        if lvl in ouverts:
            SOURCES[key] = "connu"
        elif lvl not in ouverts:
            # 13/11/2026 : fiche 'mot-cle' = toute fiche validee d'un podcast moins connu (niveaux B/C).
            # Le volume Google Ads n'est plus qu'un bonus de tri (volumes figes), jamais un filtre.
            SOURCES[key] = "mot_cle"
            vol = max(vol, motcle.get(key, 0))
        else:
            continue
        # 21/10/2026 : élargi. Les pages avec volume passent d'abord (tri par volume), puis les autres niveau A par note.
        if BASE + "m/" + key in deja:
            continue
        cands.append((-(vol + (10**9 if key in enrichies else 0)), -(v.get("score_final") or 0), key))
    cands.sort()
    # 28/10/2026 : plus de plafond ici. Le plafond par podcast (3) et les N pages sont appliques dans main(),
    # apres verification du titre : sinon les 30 premiers (souvent sans titre) bloquaient les pages deja titrees.
    out = [(k.split("/", 1)[0], k.split("/", 1)[1], -sc) for _, sc, k in cands]
    return out, titres


def titre_pour(slug, mid, titres):
    """Titre existant, sinon titre genere (meme regle que seo_title). None si pas assez propre."""
    key = slug + "/" + mid
    if titres.get(key):
        return titres[key]
    try:
        d = json.load(open(f"{PAGES}/data/moments/{slug}.json", encoding="utf-8"))
        q = d["entries"][mid]["q"]
        name = d.get("podcast") or slug
    except (OSError, KeyError, json.JSONDecodeError):
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("mam", "automation/scripts/moteur_autonome_moments.py")
        mam = importlib.util.module_from_spec(spec); spec.loader.exec_module(mam)
        t = mam.seo_title(q, name)
    except Exception:
        return None
    if t["tronque"] or t["alerte_longueur"]:
        return None   # question a reecrire : on passe a la suivante
    return t["titre"]


def token():
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    info = json.loads(os.environ["GSC_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    creds.refresh(Request())
    return creds.token


def inspecter(tok, url):
    r = requests.post("https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
                      headers={"Authorization": f"Bearer {tok}"},
                      json={"inspectionUrl": url, "siteUrl": SITE}, timeout=60)
    r.raise_for_status()
    s = r.json().get("inspectionResult", {}).get("indexStatusResult", {})
    return {"verdict": s.get("verdict"), "etat": s.get("coverageState"),
            "robots": s.get("robotsTxtState"), "indexation_bloquee": s.get("indexingState")}


def http(url):
    try:
        return requests.head(url, allow_redirects=True, timeout=30).status_code
    except requests.RequestException:
        return None


def main():
    items = []
    try:
        tok = token() if os.environ.get("GSC_SERVICE_ACCOUNT_JSON") else None
    except Exception:
        tok = None
    cands, titres = choisir()
    nouveaux = {}
    chosen = []
    par_podcast = {}
    deja_indexees_nouvelles = []
    # 02/11/2026 : repartition 70 % / 30 %. 7 pages sur 10 vont aux podcasts qui ont deja des clics
    # (data/gsc/resultats_par_podcast.json), les 3 autres a des podcasts nouveaux. Les places restantes sont
    # completees par n'importe quelle page disponible.
    prouves = set()
    try:
        rp = json.load(open("data/gsc/resultats_par_podcast.json", encoding="utf-8"))
        prouves = {x["podcast"] for x in rp.get("detail", []) if x.get("clics", 0) > 0}
    except (OSError, json.JSONDecodeError):
        pass
    QUOTA_PROUVES = round(N * 0.7)
    vus = set()

    def essayer(slug, mid, score):
        if (slug, mid) in vus:
            return
        vus.add((slug, mid))
        if par_podcast.get(slug, 0) >= 3:
            return
        titre = titre_pour(slug, mid, titres)
        if not titre:
            return
        # 02/11/2026 : controle reel dans la Search Console (API) avant de choisir.
        # Une page deja indexee n'est pas proposee : elle est notee dans indexees_verifiees.json.
        if tok:
            try:
                etat = inspecter(tok, BASE + "m/" + slug + "/" + mid)
                if etat.get("verdict") == "PASS":
                    deja_indexees_nouvelles.append(BASE + "m/" + slug + "/" + mid)
                    return
            except Exception:
                pass
        par_podcast[slug] = par_podcast.get(slug, 0) + 1
        if not titres.get(slug + "/" + mid):
            nouveaux[slug + "/" + mid] = titre
        chosen.append((slug, mid, score, titre))

    # 08/11/2026 : repartition 50/50 (remplace le 70/30 'podcasts avec clics'). 5 fiches de podcasts connus,
    # 5 fiches mots-cles du reservoir (volume Google Ads >= 100/mois). Si un groupe manque de stock,
    # l'autre complete. Chaque fiche porte son etiquette de source pour le suivi Search Console.
    def n_source(src):
        return sum(1 for c in chosen if SOURCES.get(c[0] + "/" + c[1]) == src)
    # passe 0 (09/11/2026) : les fiches en retard d'abord, sans quota de groupe
    for slug, mid, score in cands:
        if len(chosen) >= N:
            break
        if slug + "/" + mid in RETARD:
            essayer(slug, mid, score)
    for src, quota in (("connu", QUOTA_CONNU), ("mot_cle", QUOTA_MOTCLE)):
        for slug, mid, score in cands:
            if n_source(src) >= quota:
                break
            if SOURCES.get(slug + "/" + mid) == src:
                essayer(slug, mid, score)
    for slug, mid, score in cands:
        if len(chosen) >= N:
            break
        essayer(slug, mid, score)
    if deja_indexees_nouvelles:
        vp = f"{PAGES}/data/indexees_verifiees.json"
        try:
            vd = json.load(open(vp, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            vd = {"note": "Pages verifiees INDEXEES dans la Search Console.", "urls": []}
        vd["urls"] = sorted(set(vd.get("urls", [])) | set(deja_indexees_nouvelles))
        json.dump(vd, open(vp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    for slug, mid, score, titre in chosen:
        url = BASE + "m/" + slug + "/" + mid
        item = {"url": url, "titre": titre, "score_qualite": score, "source": SOURCES.get(slug + "/" + mid, "connu"), "http": http(url)}
        if tok:
            try:
                item.update(inspecter(tok, url))
            except Exception as e:
                item["inspection_erreur"] = str(e)[:120]
        # Pret = en ligne, pas bloquee par robots.txt ni par balise noindex, et pas encore indexee.
        item["pret_pour_demande"] = (item["http"] == 200 and item.get("verdict") != "PASS"
                                     and item.get("robots") != "DISALLOWED"
                                     and item.get("indexation_bloquee") not in ("BLOCKED_BY_META_TAG", "BLOCKED_BY_HTTP_HEADER"))
        items.append(item)
    try:
        volumes_ok = str(json.load(open(f"{PAGES}/data/demande_par_fiche.json", encoding="utf-8")).get("date", ""))[:10] == datetime.date.today().isoformat()
    except (OSError, json.JSONDecodeError):
        volumes_ok = False
    out = {"date": datetime.date.today().isoformat(),
           "mode": "liste a traiter dans Claude + Chrome (demande d'indexation manuelle, validation par page)",
           "repartition": {"connu": sum(1 for i in items if i.get("source") == "connu"), "mot_cle": sum(1 for i in items if i.get("source") == "mot_cle")},
           "selection": "50/50 connus + mots-cles ; volumes du jour + note" if volumes_ok else "note seule (volumes non a jour, Keyword Planner en echec)",
           "pretes": sum(1 for i in items if i["pret_pour_demande"]),
           "urls": items}
    if nouveaux:
        tp = f"{PAGES}/data/titres_seo.json"
        raw = json.load(open(tp, encoding="utf-8"))
        if isinstance(raw, dict) and "titres" in raw:
            raw["titres"].update(nouveaux)
        else:
            raw.update(nouveaux)
        json.dump(raw, open(tp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[indexation] {out['pretes']} pretes sur {len(items)}")


if __name__ == "__main__":
    main()

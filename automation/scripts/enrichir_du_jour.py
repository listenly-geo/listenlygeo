#!/usr/bin/env python3
"""
ENRICHISSEMENT DU JOUR (08/11/2026) : rallonge la reponse des fiches moment qui vont etre proposees a Google,
et seulement elles (cout minime : ~12 appels Haiku par jour).

Pourquoi : une fiche issue d'une extraction recente n'a qu'un court extrait (1 paragraphe). La porte d'entree
de qualite exige 2 paragraphes. Ici la reponse est reecrite A PARTIR DE LA TRANSCRIPTION de l'episode
(rien d'invente) puis ecrite dans data/moments/<podcast>.json (champ "f").

Choix des fiches (meme repartition que indexation_du_jour.py) :
  - 5 'connues'  : podcasts niveau A, nouvelles fiches du reservoir des podcasts connus, meilleure note d'abord
  - 5 'mots-cles': questions du reservoir MarketForge avec >= 100 recherches/mois, plus fort volume d'abord
  (+2 de reserve par groupe si une transcription est introuvable). Max 3 par podcast.
Sortie : pages/podcast-btb/data/enrichies_du_jour.json (lu par indexation_du_jour.py pour les passer en premier).
Secret : ANTHROPIC_API_KEY.
"""
import os, sys, re, json, glob, datetime, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import moteur_autonome_moments as mam   # noqa: E402
import indexation_du_jour as ij          # noqa: E402

PAGES = "pages/podcast-btb"
INBOX = "automation/inbox/moteur-trafic-transcripts"
OUT = f"{PAGES}/data/enrichies_du_jour.json"
MODEL = "claude-haiku-4-5-20251001"
PAR_GROUPE = 5
RESERVE = 2


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def transcript(slug, episode_title):
    for f in glob.glob(f"{INBOX}/{slug}/*.json"):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if norm(d.get("episode_title")) == norm(episode_title) and d.get("transcript_full"):
            return d["transcript_full"]
    return ""


def reecrire(question, extrait, texte):
    prompt = (
        "You write the answer section of a podcast Q&A web page, using ONLY the transcript below. "
        "Never add facts that are not in the transcript. Write 2 paragraphs (150 to 220 words in total), plain prose, "
        "third person, concrete details and figures when the transcript has them, no filler, no mention of 'the transcript'. "
        "If the transcript does not contain enough to answer the question, reply exactly NONE.\n\n"
        f"QUESTION: {question}\n\nSHORT EXCERPT ALREADY KNOWN: {extrait}\n\nTRANSCRIPT:\n{texte[:20000]}\n\n"
        "Reply with the two paragraphs separated by a blank line, nothing else.")
    body = json.dumps({"model": MODEL, "max_tokens": 700, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        t = json.loads(r.read())["content"][0]["text"].strip()
    if t.upper().startswith("NONE"):
        return None
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    if len(paras) < 2 or sum(len(p.split()) for p in paras) < 110:
        return None
    return paras[:3]


def claude(prompt, max_tokens=120):
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["content"][0]["text"].strip()


def titre_court(question, podcast):
    """Titre Google : question courte (meme regle que seo_title : question + ' | Podcast', 50 a 58 caracteres).
    Les questions longues ne se raccourcissent pas mecaniquement : Claude les reformule."""
    name = re.sub(r"\s+", " ", podcast or "").strip() or "Listenly"
    suffix = f" | {name}" if len(name) <= 28 else " | " + name[:26].rstrip()
    room = 58 - len(suffix)
    for essai in range(2):
        t = claude(f"Rewrite this podcast question as a short natural Google search question in English, "
                   f"at most {room - 4 * essai} characters including the final question mark, keeping its meaning and "
                   f"its main keywords. No quotes, reply with the question only.\n\n{question}", 80).strip(' "\n')
        t = re.sub(r"\s+", " ", t)
        if t and not t.endswith("?"):
            t += "?"
        t = t[:1].upper() + t[1:]
        full = t + suffix
        if t and len(full) <= 58:
            return full
    return None


def main():
    scores = json.load(open(f"{PAGES}/data/moments_scores.json", encoding="utf-8"))
    scores = scores.get("scores", scores)
    niv = json.load(open(f"{PAGES}/data/priorite_podcasts.json", encoding="utf-8")).get("niveaux", {})
    motcle = ij.volumes_motcle()
    try:
        connus = json.load(open("automation/moments_connus/reservoir_connus.json", encoding="utf-8"))["items"]
    except (OSError, json.JSONDecodeError):
        connus = []
    import hashlib
    keys_connus = {i["podcast_slug"] + "/" + hashlib.sha1(f"{i['podcast_slug']}|{norm(i['question'])}".encode()).hexdigest()[:10]
                   for i in connus}
    # 13/11/2026 : ij.deja_demandees n'existe pas -> l'enrichissement re-choisissait des fiches deja demandees.
    deja = set()
    for fn in ("index_requests.json", "indexees_verifiees.json", "indexation_demandees.json"):
        try:
            raw = json.load(open(f"{PAGES}/data/{fn}", encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        stack = [raw]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)
            elif isinstance(x, str) and "/podcast-btb/m/" in x:
                deja.add(x.split("/podcast-btb/m/", 1)[1].strip("/"))

    def pool(keys, tri):
        out = []
        for k in keys:
            v = scores.get(k)
            if not v or v.get("gate") or not v.get("question"):
                continue
            out.append((tri(k, v), k))
        out.sort(key=lambda x: -x[0])
        return [k for _, k in out]

    c_connu = pool((k for k in keys_connus if niv.get(k.split("/")[0]) == "A"), lambda k, v: v.get("score_final", 0))
    c_motcle = pool((k for k in motcle if k not in keys_connus), lambda k, v: motcle[k] * 1000 + v.get("score_final", 0))

    done, par_podcast, rapport = [], {}, []
    for groupe, cands in (("connu", c_connu), ("mot_cle", c_motcle)):
        ok = 0
        for k in cands:
            if ok >= PAR_GROUPE or len([r for r in rapport if r["groupe"] == groupe]) >= PAR_GROUPE + RESERVE:
                break
            if k in deja:
                continue
            slug, mid = k.split("/")
            if par_podcast.get(slug, 0) >= 3:
                continue
            f = f"{PAGES}/data/moments/{slug}.json"
            d = json.load(open(f, encoding="utf-8"))
            e = d["entries"].get(mid)
            if not e:
                continue
            if len(e.get("f") or []) >= 2:
                # deja rallongee (relance du meme jour) : on complete seulement le titre s'il manque
                if e.get("enrichi") and e.get("q"):
                    tp = f"{PAGES}/data/titres_seo.json"
                    raw = json.load(open(tp, encoding="utf-8"))
                    tit = raw["titres"] if isinstance(raw, dict) and "titres" in raw else raw
                    if not tit.get(k):
                        try:
                            t2 = titre_court(e.get("q"), d.get("podcast") or slug)
                        except Exception:
                            t2 = None
                        if t2:
                            tit[k] = t2
                            json.dump(raw, open(tp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                    if tit.get(k) and e.get("enrichi") == datetime.date.today().isoformat():
                        done.append(k); par_podcast[slug] = par_podcast.get(slug, 0) + 1; ok += 1
                        rapport.append({"groupe": groupe, "cle": k, "question": e["q"], "resultat": "ok", "titre": tit[k]})
                continue
            txt = transcript(slug, e.get("e"))
            r = {"groupe": groupe, "cle": k, "question": e.get("q"), "resultat": ""}
            rapport.append(r)
            if not txt:
                r["resultat"] = "transcription introuvable"
                continue
            try:
                paras = reecrire(e.get("q"), e.get("a"), txt)
            except Exception as ex:
                r["resultat"] = f"erreur Claude ({str(ex)[:80]})"
                continue
            if not paras:
                r["resultat"] = "transcription insuffisante"
                continue
            e["f"] = paras
            e["enrichi"] = datetime.date.today().isoformat()
            json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False)
            par_podcast[slug] = par_podcast.get(slug, 0) + 1
            try:
                titre = titre_court(e.get("q"), d.get("podcast") or slug)
            except Exception:
                titre = None
            if titre:
                tp = f"{PAGES}/data/titres_seo.json"
                raw = json.load(open(tp, encoding="utf-8"))
                (raw["titres"] if isinstance(raw, dict) and "titres" in raw else raw)[k] = titre
                json.dump(raw, open(tp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                r["titre"] = titre
            r["resultat"] = "ok"
            done.append(k)
            ok += 1
    json.dump({"date": datetime.date.today().isoformat(), "cles": done, "rapport": rapport},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[enrichissement] {len(done)} fiche(s) rallongee(s) : "
          f"{sum(1 for r in rapport if r['groupe']=='connu' and r['resultat']=='ok')} connues, "
          f"{sum(1 for r in rapport if r['groupe']=='mot_cle' and r['resultat']=='ok')} mots-cles")
    for r in rapport:
        print(f"  {r['groupe']:8s} {r['resultat']:28s} {r.get('titre') or r['question'][:70]}")


if __name__ == "__main__":
    main()

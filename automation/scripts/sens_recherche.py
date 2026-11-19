#!/usr/bin/env python3
"""
FILTRE « SENS DANS LA RECHERCHE » (19/11/2026, demande d'Etienne).

Avant qu'une fiche moment soit rallongee ou proposee a Google, l'IA verifie que la question a un vrai sens
pour quelqu'un qui cherche sur Google, sans avoir ecoute l'episode :
  - une vraie personne taperait-elle cette question (ou une tres proche) dans Google ?
  - la question se comprend-elle seule (pas de « he », « this deal », personne ou entreprise inconnue du public,
    detail interne d'une petite entreprise, fait divers, actualite perimee) ?
  - le sujet est-il utile et durable (conseil, methode, explication, chiffre, metier) ?

Verdicts :
  ok       : la question et le titre sont bons ;
  retitrer : le sujet est bon mais le titre a perdu le sens -> nouveau titre propose (question claire + suffixe) ;
  rejeter  : le sujet n'a pas de sens dans la recherche -> la fiche n'est jamais proposee.

Memoire : pages/podcast-btb/data/sens_recherche.json (cle slug/id), pour ne juger qu'une fois chaque fiche.
Sans ANTHROPIC_API_KEY : aucun jugement (None), le reste du systeme continue comme avant.
"""
import os, re, json, datetime, urllib.request

PATH = "pages/podcast-btb/data/sens_recherche.json"
MODEL = "claude-haiku-4-5-20251001"
VERSION = 1
MAX_APPELS = 80   # par lancement : au-dela, les fiches non jugees ne sont pas proposees ce jour-la
_cache = None
_appels = 0

PROMPT = """You review pages for a podcast Q&A site. Each page answers ONE question with a passage from a podcast episode.
The page title is what a stranger sees in Google results, without having heard the episode.

Decide if this page makes sense as a Google search result.

ACCEPT only if ALL are true:
1. A real person could type this question (or a very close one) into Google.
2. It is understandable on its own: no unexplained pronoun, no "this/the deal", no reference to the episode.
3. It does not hinge on a private individual, a little-known person, or a small company the public does not know
   (famous brands and famous people are fine; "How did Taliaferro scale his business?" or "What is NorQuest's strategy?" are not).
4. It is useful and durable: advice, method, explanation, definition, data, career or business know-how.
   Reject crime/court gossip, trivia, one-off news, anecdotes ("Who bought newspapers?", "What sentence did X get?").

If the TOPIC passes but the TITLE is vague, lost context, or is badly phrased, propose a better title:
a clear, natural English search question, at most {room} characters including the question mark, no quotes,
keeping the real subject of the passage (e.g. "Did fines make parents arrive even later?" -> "Do fines change behavior? The daycare late-fee study").

Original question from the episode: {question}
Current page title: {titre}
Podcast: {podcast}

Reply with JSON only: {{"verdict": "ok" | "retitrer" | "rejeter", "raison": "<short reason in French>", "titre": "<new question, only if retitrer>"}}"""


def _load():
    global _cache
    if _cache is None:
        try:
            _cache = json.load(open(PATH, encoding="utf-8"))
        except (OSError, ValueError):
            _cache = {}
        _cache.setdefault("fiches", {})
    return _cache


def save():
    if _cache is not None:
        _cache["maj"] = datetime.date.today().isoformat()
        json.dump(_cache, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _claude(prompt):
    body = json.dumps({"model": MODEL, "max_tokens": 200, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        t = json.loads(r.read())["content"][0]["text"]
    return json.loads(t[t.find("{"):t.rfind("}") + 1])


def suffixe(titre):
    m = re.search(r"\s\|\s[^|]+$", titre or "")
    return m.group(0) if m else " | Listenly"


def juger(cle, question, titre=None, podcast=""):
    """Renvoie {"verdict", "raison", "titre"(complet avec suffixe si retitrer)} ou None si pas de cle API.
    Le jugement est memorise par (cle, titre) : un nouveau titre est rejuge."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    c = _load()["fiches"]
    titre = titre or question
    old = c.get(cle)
    if old and old.get("v") == VERSION and old.get("titre_juge") == titre:
        return old
    global _appels
    if _appels >= MAX_APPELS:
        return {"verdict": "rejeter", "raison": "non jugee aujourd'hui (budget d'appels atteint)"}
    _appels += 1
    suf = " | Listenly"   # 19/11/2026 : un titre reecrit finit toujours par la marque (pas de nom de podcast coupe)
    room = 58 - len(suf)
    try:
        r = _claude(PROMPT.format(room=room - 4, question=question, titre=titre, podcast=podcast))
    except Exception as ex:
        print(f"[sens] {cle} : jugement impossible ({str(ex)[:80]})")
        return None
    brut = str(r.get("verdict", "")).strip().lower()
    # 19/11/2026 : verdict mal ecrit par l'IA -> jamais « ok » par defaut
    v = "ok" if brut in ("ok", "accept", "accepte") else "retitrer" if brut.startswith("reti") else "rejeter"
    out = {"v": VERSION, "verdict": v, "raison": str(r.get("raison", ""))[:200], "titre_juge": titre,
           "question": question, "date": datetime.date.today().isoformat()}
    if v == "retitrer":
        q = re.sub(r"\s+", " ", str(r.get("titre", ""))).strip(' "\n')
        if q and not q.endswith("?"):
            q += "?"
        if q and len(q + suf) > 58 and _appels < MAX_APPELS:
            # 19/11/2026 : second essai -> on demande une version plus courte au lieu de jeter un bon sujet
            _appels += 1
            try:
                r2 = _claude(f"Shorten this Google search question to at most {room - 2} characters including the question mark, "
                             f"keeping its subject clear and natural. Reply with JSON only: {{\"titre\": \"...\"}}\n\n{q}")
                q2 = re.sub(r"\s+", " ", str(r2.get("titre", ""))).strip(' "\n')
                if q2 and not q2.endswith("?"):
                    q2 += "?"
                if q2 and len(q2 + suf) <= 58:
                    q = q2
            except Exception:
                pass
        if q and len(q + suf) <= 58:
            out["titre"] = q[:1].upper() + q[1:] + suf
        else:
            # 19/11/2026 : titre propose inutilisable (trop long) -> on ne garde pas un titre juge flou
            out["verdict"] = "rejeter"
            out["raison"] = (out["raison"] + " (titre clair impossible en 58 caracteres)").strip()
    c[cle] = out
    print(f"[sens] {out['verdict']:8s} {titre[:70]}" + (f" -> {out['titre']}" if out.get("titre") else "") + f" | {out['raison'][:100]}")
    return out

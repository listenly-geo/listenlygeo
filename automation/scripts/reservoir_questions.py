"""Reservoir de questions : chaque question extraite par le moteur MarketForge est ajoutee ici,
avec son podcast, son episode et son lien. Le cron quotidien (tri, choix, optimisation du titre)
lira ce fichier plus tard. Ce module ne decide rien : il ne fait qu'enregistrer.

Fichier : automation/marketforge_engine/reservoir_questions.json
Cle de dedoublonnage : slug du podcast + question normalisee.
"""
import os, json, re, datetime

ENGINE_DIR = "automation/marketforge_engine"
RESERVOIR_FILE = f"{ENGINE_DIR}/reservoir_questions.json"
N1_BASE = "https://listenly.org/podcast-btb"


def _load(path):
    if not os.path.exists(path):
        return {"version": 1, "items": []}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data
    except Exception:
        pass
    return {"version": 1, "items": []}


def _norm(text):
    return re.sub(r"\W+", " ", (text or "").lower()).strip()


def add_questions(podcast, ep, qa, today=None):
    """Ajoute les questions d'un episode au reservoir. Retourne le nombre ajoute.
    Ne leve jamais d'exception vers l'appelant : l'extraction ne doit pas casser."""
    try:
        today = today or datetime.date.today().isoformat()
        slug = podcast.get("slug", "")
        data = _load(RESERVOIR_FILE)
        seen = {(i.get("podcast_slug"), _norm(i.get("question"))) for i in data["items"]}
        ajoutes = 0
        for item in qa or []:
            q = (item.get("q") or "").strip()
            if not q or (slug, _norm(q)) in seen:
                continue
            data["items"].append({
                "question": q,
                "podcast_slug": slug,
                "podcast_name": podcast.get("name", ""),
                "n1_url": f"{N1_BASE}/{slug}-podcast.html",
                "episode_title": ep.get("title", ""),
                "episode_guid": ep.get("guid") or ep.get("title", ""),
                "source_url": ep.get("audio_url", ""),
                "date_ajout": today,
                "statut": "nouveau",
            })
            seen.add((slug, _norm(q)))
            ajoutes += 1
        if ajoutes:
            os.makedirs(os.path.dirname(RESERVOIR_FILE), exist_ok=True)
            with open(RESERVOIR_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
        return ajoutes
    except Exception as e:
        print(f"[reservoir] AVERTISSEMENT ajout impossible ({e})", flush=True)
        return 0

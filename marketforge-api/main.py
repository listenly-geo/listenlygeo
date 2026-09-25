"""Marketforge AI Visibility Hub - API MVP.

Stockage : un fichier JSON par client dans DATA_DIR.
Seul le type de source "podcast" est traité réellement (RSS -> Claude -> questions/réponses).
"""

import hashlib
import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import anthropic
import feedparser
import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("marketforge")

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5")
EPISODES_PER_PODCAST = 3

SourceType = Literal["website", "podcast", "video", "document", "webinar", "article"]
SUPPORTED_TYPES = {"podcast"}
Strategy = Literal["hub", "site", "both"]

app = FastAPI(title="Marketforge AI Visibility Hub API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "https://marketforge.fr,https://www.marketforge.fr").split(",")
        if o.strip()
    ],
    # Aperçus de l'éditeur Bolt.ai
    allow_origin_regex=r"https://.*\.(bolt\.new|bolt\.host|webcontainer-api\.io|webcontainer\.io)",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Un seul verrou pour tout le stockage : suffisant avec un seul process uvicorn.
_lock = threading.Lock()


# ---------------------------------------------------------------- stockage

def _normalize_client_id(client_id: str) -> str:
    cid = client_id.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", cid):
        raise HTTPException(status_code=422, detail="client_id doit être l'email de l'utilisateur")
    return cid


def _path(client_id: str) -> Path:
    return DATA_DIR / (hashlib.sha256(client_id.encode()).hexdigest()[:32] + ".json")


def _empty(client_id: str) -> dict:
    return {
        "client_id": client_id,
        "sources": [],
        "strategy": None,
        "status": "idle",  # idle | running | done | error
        "last_run_at": None,
        "last_error": None,
        "opportunities": [],
        "resources_published": 0,
    }


def _load(client_id: str) -> dict:
    p = _path(client_id)
    if not p.exists():
        return _empty(client_id)
    return json.loads(p.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    p = _path(data["client_id"])
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)  # écriture atomique


def _update(client_id: str, fn) -> dict:
    with _lock:
        data = _load(client_id)
        fn(data)
        _save(data)
        return data


# ---------------------------------------------------------------- modèles

class SourceIn(BaseModel):
    client_id: str
    type: SourceType
    value: str = Field(default="", description="URL du flux RSS pour un podcast")


class StrategyIn(BaseModel):
    client_id: str
    strategy: Strategy


# ---------------------------------------------------------------- routes

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/onboarding/sources")
def add_source(body: SourceIn):
    cid = _normalize_client_id(body.client_id)
    value = body.value.strip()
    supported = body.type in SUPPORTED_TYPES
    if supported and not value.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="Pour un podcast, value doit être l'URL du flux RSS")

    def apply(d):
        # Une source identique (même type + même valeur) n'est pas ajoutée deux fois.
        if not any(s["type"] == body.type and s["value"] == value for s in d["sources"]):
            d["sources"].append({
                "type": body.type,
                "value": value,
                "supported": supported,
                "status": "pending" if supported else "coming_soon",
            })

    data = _update(cid, apply)
    return {"ok": True, "sources": data["sources"]}


@app.post("/api/onboarding/strategy")
def set_strategy(body: StrategyIn):
    cid = _normalize_client_id(body.client_id)
    _update(cid, lambda d: d.update(strategy=body.strategy))
    return {"ok": True, "strategy": body.strategy}


@app.post("/api/run/{client_id}")
def run(client_id: str, background: BackgroundTasks):
    cid = _normalize_client_id(client_id)
    with _lock:
        data = _load(cid)
        if data["status"] == "running":
            return {"ok": True, "status": "running"}
        if not any(s["supported"] for s in data["sources"]):
            raise HTTPException(status_code=400, detail="Aucune source traitable (seuls les podcasts le sont pour l'instant)")
        data["status"] = "running"
        data["last_error"] = None
        _save(data)
    background.add_task(_process_client, cid)
    return {"ok": True, "status": "running"}


@app.get("/api/dashboard/{client_id}")
def dashboard(client_id: str):
    cid = _normalize_client_id(client_id)
    with _lock:
        d = _load(cid)
    return {
        "sources_connected": len(d["sources"]),
        "sources_processed": sum(1 for s in d["sources"] if s["status"] == "done"),
        "opportunities_found": len(d["opportunities"]),
        "resources_published": d["resources_published"],
        "strategy": d["strategy"],
        "status": d["status"],
        "last_run_at": d["last_run_at"],
        "last_error": d["last_error"],
        "sources": d["sources"],
    }


@app.get("/api/opportunities/{client_id}")
def opportunities(client_id: str):
    cid = _normalize_client_id(client_id)
    with _lock:
        return {"opportunities": _load(cid)["opportunities"]}


# ---------------------------------------------------------------- traitement

EXTRACTION_PROMPT = """Voici le titre et la description d'un épisode de podcast.

Titre : {title}
Description : {description}

Extrais entre 2 et 4 questions concrètes qu'un prospect pourrait poser à un moteur de recherche ou à une IA, \
et auxquelles cet épisode répond. Pour chaque question, rédige une réponse courte (2 à 4 phrases).

Règle absolue : n'utilise QUE les informations présentes dans le titre et la description ci-dessus. \
N'invente aucun chiffre, nom, fait ou conseil qui n'y figure pas. \
Si la description est trop pauvre pour 2 questions fiables, renvoie une liste vide.

Réponds uniquement avec un objet JSON, sans texte autour, de la forme :
{{"questions": [{{"question": "...", "answer": "..."}}]}}"""


def _clean_html(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def _fetch_episodes(rss_url: str) -> list[dict]:
    resp = httpx.get(rss_url, timeout=30, follow_redirects=True, headers={"User-Agent": "MarketforgeBot/1.0"})
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    if not feed.entries:
        raise ValueError("Flux RSS vide ou illisible")
    episodes = []
    for e in feed.entries[:EPISODES_PER_PODCAST]:
        episodes.append({
            "title": _clean_html(e.get("title", "")),
            "description": _clean_html(e.get("summary") or e.get("description") or "")[:6000],
            "link": e.get("link"),
            "published": e.get("published"),
        })
    return episodes


def _extract_questions(client: anthropic.Anthropic, episode: dict) -> list[dict]:
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(**episode)}],
    )
    if response.stop_reason == "refusal":
        log.warning("Refus du modèle pour l'épisode %s", episode["title"])
        return []
    text = "".join(b.text for b in response.content if b.type == "text")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return []
    items = json.loads(match.group(0)).get("questions", [])
    return [
        {"question": q["question"].strip(), "answer": q["answer"].strip()}
        for q in items[:4]
        if isinstance(q, dict) and q.get("question") and q.get("answer")
    ]


def _process_client(client_id: str) -> None:
    try:
        client = anthropic.Anthropic()
        with _lock:
            sources = [s for s in _load(client_id)["sources"] if s["supported"]]

        found = []
        for src in sources:
            try:
                for ep in _fetch_episodes(src["value"]):
                    for qa in _extract_questions(client, ep):
                        found.append({
                            **qa,
                            "source_type": src["type"],
                            "source_url": src["value"],
                            "episode_title": ep["title"],
                            "episode_link": ep["link"],
                        })
                status = "done"
            except Exception as exc:  # une source en erreur ne bloque pas les autres
                log.exception("Échec de la source %s", src["value"])
                status = "error"
                src["error"] = str(exc)[:300]
            src["status"] = status

        def apply(d):
            by_key = {(s["type"], s["value"]): s for s in sources}
            for s in d["sources"]:
                if (s["type"], s["value"]) in by_key:
                    s.update(by_key[(s["type"], s["value"])])
            d["opportunities"] = found
            d["status"] = "done" if any(s["status"] == "done" for s in sources) else "error"
            d["last_error"] = None if d["status"] == "done" else "Aucune source n'a pu être traitée"
            d["last_run_at"] = datetime.now(timezone.utc).isoformat()

        _update(client_id, apply)
        log.info("Client %s : %d questions extraites", client_id, len(found))
    except Exception as exc:
        log.exception("Échec du traitement pour %s", client_id)
        _update(client_id, lambda d: d.update(status="error", last_error=str(exc)[:300]))

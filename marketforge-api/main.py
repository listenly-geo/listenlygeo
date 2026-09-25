"""Marketforge AI Visibility Hub - API MVP.

L'API ne génère rien elle-même : elle déclenche le moteur trafic existant de
listenly-geo/listenlygeo (workflow marketforge-hub.yml -> generate_podcast_btb.py +
generate_qa_fiches_btb.py) et lit ce qu'il a produit pour alimenter le dashboard.

Stockage : un fichier JSON par client dans DATA_DIR.
Seul le type de source "podcast" est traité ; les autres sont enregistrés comme "coming_soon".
"""

import base64
import hashlib
import json
import logging
import os
import re
import threading
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import feedparser
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("marketforge")

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "listenly-geo/listenlygeo")
WORKFLOW_FILE = os.getenv("WORKFLOW_FILE", "marketforge-hub.yml")
PUBLIC_BASE = "https://listenly.fr/podcast-btb"

# Garde-fous de coût (chaque run = transcription Whisper + appels Claude côté moteur).
FICHES_PER_RUN = int(os.getenv("FICHES_PER_RUN", "3"))
MIN_HOURS_BETWEEN_RUNS = float(os.getenv("MIN_HOURS_BETWEEN_RUNS", "12"))
MAX_RUNS_PER_DAY = int(os.getenv("MAX_RUNS_PER_DAY", "10"))

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


def _path(name: str) -> Path:
    return DATA_DIR / (hashlib.sha256(name.encode()).hexdigest()[:32] + ".json")


def _empty(client_id: str) -> dict:
    return {"client_id": client_id, "sources": [], "strategy": None, "runs": []}


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


# ---------------------------------------------------------------- moteur (GitHub)

def slugify(s: str) -> str:
    """Identique à generate_podcast_btb.slugify, pour retomber sur les mêmes fichiers."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"^-+|-+$", "", s)[:60]


def _gh(method: str, path: str, **kw) -> httpx.Response:
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN non configuré sur le serveur")
    return httpx.request(
        method,
        f"https://api.github.com/repos/{GITHUB_REPO}{path}",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=20,
        **kw,
    )


_cache: dict[str, tuple[datetime, int, object]] = {}
CACHE_SECONDS = 30


def _gh_get_json(path: str, **params) -> tuple[int, object]:
    """GET GitHub mis en cache 30 s : le dashboard poll toutes les 5 s, le quota est de 5000 req/h."""
    key = path + json.dumps(params, sort_keys=True)
    now = datetime.now(timezone.utc)
    hit = _cache.get(key)
    if hit and (now - hit[0]).total_seconds() < CACHE_SECONDS:
        return hit[1], hit[2]
    try:
        r = _gh("GET", path, params=params)
        body = r.json() if r.status_code == 200 else None
        code = r.status_code
    except httpx.HTTPError as exc:
        log.warning("GitHub injoignable (%s) : %s", path, exc)
        return (hit[1], hit[2]) if hit else (503, None)
    _cache[key] = (now, code, body)
    return code, body


def _read_podcast_title(rss_url: str) -> str:
    try:
        resp = httpx.get(rss_url, timeout=20, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(status_code=422, detail="Flux RSS injoignable : vérifiez l'URL")
    feed = feedparser.parse(resp.content)
    title = (feed.feed.get("title") or "").strip()
    if not title or not feed.entries:
        raise HTTPException(status_code=422, detail="Cette URL n'est pas un flux RSS de podcast valide")
    return title


def _registry(slug: str) -> dict | None:
    """Registre du moteur trafic : pending_qa (questions extraites) + published (fiches en ligne)."""
    code, body = _gh_get_json(f"/contents/pages/podcast-btb/questions/{slug}/_qa_registry.json", ref="main")
    if code != 200 or not body.get("content"):
        return None
    return json.loads(base64.b64decode(body["content"]))


def _hub_exists(slug: str) -> bool:
    code, _ = _gh_get_json(f"/contents/pages/podcast-btb/{slug}-podcast.html", ref="main")
    return code == 200


def _latest_run(slug: str) -> dict | None:
    code, body = _gh_get_json(f"/actions/workflows/{WORKFLOW_FILE}/runs", per_page=50, event="workflow_dispatch")
    if code != 200:
        return None
    for run in body.get("workflow_runs", []):  # du plus récent au plus ancien
        if run.get("display_title") == f"marketforge {slug}":
            return run
    return None


def _run_status(run: dict | None) -> str:
    if run is None:
        return "idle"
    if run["status"] != "completed":
        return "running"
    return "done" if run["conclusion"] == "success" else "error"


# ---------------------------------------------------------------- modèles

class SourceIn(BaseModel):
    client_id: str
    type: SourceType
    value: str = Field(default="", description="URL du flux RSS pour un podcast, URL du site pour website")


class StrategyIn(BaseModel):
    client_id: str
    strategy: Strategy


# ---------------------------------------------------------------- routes

@app.get("/health")
def health():
    return {"status": "ok", "engine_configured": bool(GITHUB_TOKEN)}


@app.post("/api/onboarding/sources")
def add_source(body: SourceIn):
    cid = _normalize_client_id(body.client_id)
    value = body.value.strip()
    source = {
        "type": body.type,
        "value": value,
        "supported": body.type in SUPPORTED_TYPES,
        "status": "pending" if body.type in SUPPORTED_TYPES else "coming_soon",
    }
    if body.type == "podcast":
        if not value.startswith(("http://", "https://")):
            raise HTTPException(status_code=422, detail="Pour un podcast, indiquez l'URL du flux RSS")
        source["title"] = _read_podcast_title(value)
        source["slug"] = slugify(source["title"])
        source["hub_url"] = f"{PUBLIC_BASE}/{source['slug']}-podcast.html"

    def apply(d):
        if not any(s["type"] == body.type and s["value"] == value for s in d["sources"]):
            d["sources"].append(source)

    data = _update(cid, apply)
    return {"ok": True, "sources": data["sources"]}


@app.post("/api/onboarding/strategy")
def set_strategy(body: StrategyIn):
    cid = _normalize_client_id(body.client_id)
    _update(cid, lambda d: d.update(strategy=body.strategy))
    return {"ok": True, "strategy": body.strategy}


def _global_runs_today() -> list[str]:
    p = DATA_DIR / "_runs_log.json"
    today = datetime.now(timezone.utc).date().isoformat()
    runs = json.loads(p.read_text()) if p.exists() else []
    return [r for r in runs if r.startswith(today)]


@app.post("/api/run/{client_id}")
def run(client_id: str):
    cid = _normalize_client_id(client_id)
    with _lock:
        data = _load(cid)
        podcasts = [s for s in data["sources"] if s["type"] == "podcast"]
        if not podcasts:
            raise HTTPException(status_code=400, detail="Aucune source traitable (seuls les podcasts le sont pour l'instant)")

        now = datetime.now(timezone.utc)
        if data["runs"]:
            last = datetime.fromisoformat(data["runs"][-1])
            if now - last < timedelta(hours=MIN_HOURS_BETWEEN_RUNS):
                return {"ok": True, "status": "already_started", "last_run_at": data["runs"][-1]}

        today_runs = _global_runs_today()
        if len(today_runs) + len(podcasts) > MAX_RUNS_PER_DAY:
            raise HTTPException(status_code=429, detail="Limite quotidienne d'analyses atteinte, réessayez demain")

        website = next((s["value"] for s in data["sources"] if s["type"] == "website" and s["value"]), "")
        for src in podcasts:
            r = _gh("POST", f"/actions/workflows/{WORKFLOW_FILE}/dispatches", json={
                "ref": "main",
                "inputs": {
                    "podcast_slug": src["slug"],
                    "rss_url": src["value"],
                    "cta_url": website or src["value"],
                    "max_fiches": str(FICHES_PER_RUN),
                },
            })
            if r.status_code not in (200, 204):
                log.error("Dispatch refusé (%s) : %s", r.status_code, r.text[:300])
                raise HTTPException(status_code=502, detail="Le moteur n'a pas pu être lancé")

        data["runs"].append(now.isoformat())
        _save(data)
        _cache.clear()
        p = DATA_DIR / "_runs_log.json"
        p.write_text(json.dumps(today_runs + [now.isoformat()] * len(podcasts)))
    return {"ok": True, "status": "running"}


def _collect(client: dict) -> dict:
    """Assemble l'état réel de chaque podcast à partir du dépôt du moteur."""
    sources, opportunities = [], []
    statuses = []
    for s in client["sources"]:
        s = dict(s)
        if s["type"] == "podcast":
            run = _latest_run(s["slug"]) if client["runs"] else None
            status = _run_status(run)
            # Juste après le dispatch, GitHub met quelques secondes à créer le run.
            if status != "running" and client["runs"]:
                started = datetime.fromisoformat(client["runs"][-1])
                if datetime.now(timezone.utc) - started < timedelta(minutes=2) and (
                    run is None or run["created_at"] < client["runs"][-1][:19] + "Z"
                ):
                    status = "running"
            reg = _registry(s["slug"]) or {"pending_qa": [], "published": []}
            s["status"] = status if client["runs"] else "pending"
            s["hub_online"] = _hub_exists(s["slug"])
            s["run_url"] = run["html_url"] if run else None
            for p in reg.get("published", []):
                opportunities.append({
                    "question": p["question"], "answer": p.get("answer_snippet", ""), "url": p["url"],
                    "published": True, "episode_title": p.get("source_episode_title", ""),
                    "added_date": p.get("added_date"), "podcast": s.get("title"),
                })
            for q in reg.get("pending_qa", []):
                opportunities.append({
                    "question": q.get("q", ""), "answer": q.get("r", ""), "url": None,
                    "published": False, "episode_title": (reg.get("current_episode") or {}).get("title", ""),
                    "added_date": None, "podcast": s.get("title"),
                })
            statuses.append(s["status"])
        sources.append(s)

    if "running" in statuses:
        status = "running"
    elif "error" in statuses:
        status = "error"
    elif "done" in statuses:
        status = "done"
    else:
        status = "idle"
    return {"sources": sources, "opportunities": opportunities, "status": status}


@app.get("/api/dashboard/{client_id}")
def dashboard(client_id: str):
    cid = _normalize_client_id(client_id)
    with _lock:
        client = _load(cid)
    state = _collect(client)
    published = [o for o in state["opportunities"] if o["published"]]
    hubs = [s for s in state["sources"] if s.get("hub_online")]
    return {
        "sources_connected": len(client["sources"]),
        "opportunities_found": len(state["opportunities"]),
        "resources_published": len(published) + len(hubs),
        "strategy": client["strategy"],
        "status": state["status"],
        "last_run_at": client["runs"][-1] if client["runs"] else None,
        "hub_urls": [s["hub_url"] for s in hubs],
        "sources": state["sources"],
    }


@app.get("/api/opportunities/{client_id}")
def opportunities(client_id: str):
    cid = _normalize_client_id(client_id)
    with _lock:
        client = _load(cid)
    return {"opportunities": _collect(client)["opportunities"]}

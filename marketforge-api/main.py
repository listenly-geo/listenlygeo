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
import stripe
from fastapi import FastAPI, Header, HTTPException, Request
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

# Connexion (optionnelle) : si SUPABASE_URL est défini, chaque appel doit porter le jeton
# Supabase de l'utilisateur, et l'email du jeton doit correspondre au client_id.
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Paiement (optionnel) : actif dès que STRIPE_SECRET_KEY est défini.
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICES = json.loads(os.getenv("STRIPE_PRICES", "{}") or "{}")  # {"starter": "price_...", "pro": "price_..."}
PLAN_FICHES = json.loads(os.getenv("PLAN_FICHES", '{"starter": 3, "pro": 5}'))
FREE_RUNS = int(os.getenv("FREE_RUNS", "1"))
APP_URL = os.getenv("APP_URL", "https://marketforge.fr").rstrip("/")
ACTIVE_STATUSES = {"active", "trialing"}

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


# ---------------------------------------------------------------- connexion

_auth_cache: dict[str, tuple[datetime, str]] = {}


def _email_from_token(token: str) -> str:
    """Vérifie le jeton auprès de Supabase (GET /auth/v1/user) et renvoie l'email."""
    now = datetime.now(timezone.utc)
    hit = _auth_cache.get(token)
    if hit and (now - hit[0]).total_seconds() < 60:
        return hit[1]
    try:
        r = httpx.get(f"{SUPABASE_URL}/auth/v1/user", timeout=10,
                      headers={"Authorization": f"Bearer {token}", "apikey": SUPABASE_ANON_KEY})
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Service de connexion injoignable")
    if r.status_code != 200 or not r.json().get("email"):
        raise HTTPException(status_code=401, detail="Session expirée : reconnectez-vous")
    email = r.json()["email"].strip().lower()
    _auth_cache[token] = (now, email)
    return email


def _authorize(client_id: str, authorization: str | None, required: bool = False) -> str:
    """Renvoie le client_id normalisé. Si la connexion est configurée (SUPABASE_URL),
    le jeton doit appartenir à ce client. `required` : refuse aussi quand elle ne l'est pas."""
    cid = _normalize_client_id(client_id)
    if not SUPABASE_URL:
        if required:
            raise HTTPException(status_code=401, detail="Connexion requise (non configurée sur le serveur)")
        return cid
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Connexion requise")
    if _email_from_token(authorization.split(" ", 1)[1].strip()) != cid:
        raise HTTPException(status_code=403, detail="Accès refusé")
    return cid


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
    return {
        "status": "ok",
        "engine_configured": bool(GITHUB_TOKEN),
        "auth_configured": bool(SUPABASE_URL),
        "billing_configured": bool(STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET and STRIPE_PRICES),
    }


@app.post("/api/onboarding/sources")
def add_source(body: SourceIn, authorization: str | None = Header(default=None)):
    cid = _authorize(body.client_id, authorization)
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
def set_strategy(body: StrategyIn, authorization: str | None = Header(default=None)):
    cid = _authorize(body.client_id, authorization)
    _update(cid, lambda d: d.update(strategy=body.strategy))
    return {"ok": True, "strategy": body.strategy}


def _global_runs_today() -> list[str]:
    p = DATA_DIR / "_runs_log.json"
    today = datetime.now(timezone.utc).date().isoformat()
    runs = json.loads(p.read_text()) if p.exists() else []
    return [r for r in runs if r.startswith(today)]


@app.post("/api/run/{client_id}")
def run(client_id: str, authorization: str | None = Header(default=None)):
    cid = _authorize(client_id, authorization)
    with _lock:
        data = _load(cid)
        podcasts = [s for s in data["sources"] if s["type"] == "podcast"]
        if not podcasts:
            raise HTTPException(status_code=400, detail="Aucune source traitable (seuls les podcasts le sont pour l'instant)")

        allowed, fiches = _run_allowance(data)
        if not allowed:
            raise HTTPException(status_code=402, detail="Votre analyse gratuite a été utilisée : choisissez un abonnement pour continuer")

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
                    "max_fiches": str(fiches),
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
def dashboard(client_id: str, authorization: str | None = Header(default=None)):
    cid = _authorize(client_id, authorization)
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
def opportunities(client_id: str, authorization: str | None = Header(default=None)):
    cid = _authorize(client_id, authorization)
    with _lock:
        client = _load(cid)
    return {"opportunities": _collect(client)["opportunities"]}


# ---------------------------------------------------------------- paiement (Stripe)

def _stripe() -> stripe.StripeClient:
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Paiement non configuré sur le serveur")
    return stripe.StripeClient(STRIPE_SECRET_KEY)


def _plain(obj):
    """Objets Stripe -> dict (le SDK 15 n'expose plus .get() sur ses objets)."""
    return obj.to_dict() if hasattr(obj, "to_dict") else obj


def _billing_active() -> bool:
    return bool(STRIPE_SECRET_KEY)


def _run_allowance(client: dict) -> tuple[bool, int]:
    """(autorisé ?, nombre de fiches). Sans Stripe configuré : tout est autorisé (phase de test)."""
    if not _billing_active():
        return True, FICHES_PER_RUN
    billing = client.get("billing") or {}
    if billing.get("status") in ACTIVE_STATUSES:
        return True, int(PLAN_FICHES.get(billing.get("plan"), FICHES_PER_RUN))
    return len(client["runs"]) < FREE_RUNS, FICHES_PER_RUN


def _customers() -> dict:
    p = DATA_DIR / "_stripe_customers.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _plan_for_price(price_id: str) -> str | None:
    return next((plan for plan, pid in STRIPE_PRICES.items() if pid == price_id), None)


_prices_cache: dict = {}


@app.get("/api/billing/plans")
def billing_plans():
    """Plans affichables (montants lus chez Stripe, pour ne jamais les dupliquer dans Bolt)."""
    if not _billing_active():
        return {"enabled": False, "plans": []}
    if not _prices_cache.get("plans") or (datetime.now(timezone.utc) - _prices_cache["at"]).total_seconds() > 3600:
        sc, plans = _stripe(), []
        for plan, price_id in STRIPE_PRICES.items():
            price = _plain(sc.v1.prices.retrieve(price_id, {"expand": ["product"]}))
            recurring = price.get("recurring") or {}
            plans.append({
                "plan": plan,
                "name": price["product"]["name"],
                "amount": (price.get("unit_amount") or 0) / 100,
                "currency": price["currency"],
                "interval": recurring.get("interval"),
                "fiches_per_run": int(PLAN_FICHES.get(plan, FICHES_PER_RUN)),
            })
        _prices_cache.update(plans=plans, at=datetime.now(timezone.utc))
    return {"enabled": True, "plans": _prices_cache["plans"]}


class CheckoutIn(BaseModel):
    client_id: str
    plan: str


@app.post("/api/billing/checkout")
def billing_checkout(body: CheckoutIn, authorization: str | None = Header(default=None)):
    cid = _authorize(body.client_id, authorization)
    price_id = STRIPE_PRICES.get(body.plan)
    if not price_id:
        raise HTTPException(status_code=422, detail="Plan inconnu")
    with _lock:
        billing = _load(cid).get("billing") or {}
    params = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "client_reference_id": cid,
        "metadata": {"client_id": cid},
        "subscription_data": {"metadata": {"client_id": cid}},
        "allow_promotion_codes": True,
        "billing_address_collection": "required",
        "tax_id_collection": {"enabled": True},  # numéro de TVA sur les factures B2B
        "success_url": f"{APP_URL}/app/billing?status=success",
        "cancel_url": f"{APP_URL}/app/billing?status=cancel",
    }
    if billing.get("customer_id"):
        params["customer"] = billing["customer_id"]
        params["customer_update"] = {"address": "auto", "name": "auto"}
    else:
        params["customer_email"] = cid
    session = _plain(_stripe().v1.checkout.sessions.create(params))
    return {"url": session["url"]}


@app.post("/api/billing/portal")
def billing_portal(body: dict, authorization: str | None = Header(default=None)):
    """Portail Stripe (carte bancaire, résiliation, factures). Connexion obligatoire."""
    cid = _authorize(str(body.get("client_id", "")), authorization, required=True)
    with _lock:
        customer_id = (_load(cid).get("billing") or {}).get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=404, detail="Aucun abonnement pour ce compte")
    session = _plain(_stripe().v1.billing_portal.sessions.create(
        {"customer": customer_id, "return_url": f"{APP_URL}/app/billing"}))
    return {"url": session["url"]}


@app.get("/api/billing/{client_id}")
def billing_status(client_id: str, authorization: str | None = Header(default=None)):
    cid = _authorize(client_id, authorization)
    with _lock:
        client = _load(cid)
    billing = client.get("billing") or {}
    allowed, _ = _run_allowance(client)
    return {
        "enabled": _billing_active(),
        "plan": billing.get("plan"),
        "status": billing.get("status"),
        "active": billing.get("status") in ACTIVE_STATUSES,
        "renews_at": billing.get("current_period_end"),
        "cancel_at_period_end": billing.get("cancel_at_period_end", False),
        "free_runs_left": max(0, FREE_RUNS - len(client["runs"])) if _billing_active() else None,
        "can_run": allowed,
    }


@app.get("/api/billing/{client_id}/invoices")
def billing_invoices(client_id: str, authorization: str | None = Header(default=None)):
    """Historique des factures. Connexion obligatoire (données de facturation)."""
    cid = _authorize(client_id, authorization, required=True)
    with _lock:
        customer_id = (_load(cid).get("billing") or {}).get("customer_id")
    if not customer_id:
        return {"invoices": []}
    invoices = _plain(_stripe().v1.invoices.list({"customer": customer_id, "limit": 24}))
    return {"invoices": [
        {
            "number": inv.get("number"),
            "date": datetime.fromtimestamp(inv["created"], timezone.utc).date().isoformat(),
            "amount": (inv.get("amount_paid") or inv.get("amount_due") or 0) / 100,
            "currency": inv.get("currency"),
            "status": inv.get("status"),
            "pdf_url": inv.get("invoice_pdf"),
            "url": inv.get("hosted_invoice_url"),
        }
        for inv in invoices["data"] if inv.get("status") != "draft"
    ]}


def _apply_subscription(sub: dict) -> None:
    cid = (sub.get("metadata") or {}).get("client_id") or _customers().get(sub.get("customer"))
    if not cid:
        log.warning("Abonnement %s sans client connu", sub.get("id"))
        return
    items = (sub.get("items") or {}).get("data") or []
    price_id = items[0]["price"]["id"] if items else None
    period_end = sub.get("current_period_end") or (items[0].get("current_period_end") if items else None)

    def apply(d):
        d["billing"] = {
            **(d.get("billing") or {}),
            "customer_id": sub.get("customer"),
            "subscription_id": sub.get("id"),
            "status": sub.get("status"),
            "plan": _plan_for_price(price_id) or (d.get("billing") or {}).get("plan"),
            "current_period_end": datetime.fromtimestamp(period_end, timezone.utc).date().isoformat() if period_end else None,
            "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
        }
    _update(_normalize_client_id(cid), apply)


@app.post("/api/billing/webhook")
async def billing_webhook(request: Request, stripe_signature: str | None = Header(default=None)):
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook non configuré")
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Signature invalide")
    event = _plain(event)
    obj = event["data"]["object"]
    kind = event["type"]
    if kind == "checkout.session.completed" and obj.get("client_reference_id"):
        cid = _normalize_client_id(obj["client_reference_id"])
        with _lock:
            customers = _customers()
            customers[obj["customer"]] = cid
            (DATA_DIR / "_stripe_customers.json").write_text(json.dumps(customers))
        _update(cid, lambda d: d.update(billing={**(d.get("billing") or {}), "customer_id": obj["customer"]}))
        if obj.get("subscription"):
            _apply_subscription(_plain(_stripe().v1.subscriptions.retrieve(obj["subscription"])))
    elif kind in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
        _apply_subscription(obj)
    return {"received": True}


# ---------------------------------------------------------------- visibilité (Search Console)

def _gsc_pages() -> dict:
    code, body = _gh_get_json("/contents/pages/podcast-btb/data/gsc_pages.json", ref="main")
    if code != 200 or not body.get("content"):
        return {}
    return json.loads(base64.b64decode(body["content"]))


@app.get("/api/visibility/{client_id}")
def visibility(client_id: str, authorization: str | None = Header(default=None)):
    """Clics / impressions Google (28 derniers jours) de chaque page publiée du client."""
    cid = _authorize(client_id, authorization)
    with _lock:
        client = _load(cid)
    gsc = _gsc_pages()
    stats = gsc.get("pages", {})
    pages = []
    for s in client["sources"]:
        if s.get("type") != "podcast":
            continue
        if _hub_exists(s["slug"]):
            pages.append({"url": s["hub_url"], "title": f"Page hub — {s.get('title', '')}", "kind": "hub", "indexable": True})
        reg = _registry(s["slug"]) or {}
        for p in reg.get("published", []):
            pages.append({"url": p["url"], "title": p["question"], "kind": "question",
                          "indexable": not p.get("noindex", False), "published_at": p.get("added_date")})
    for p in pages:
        st = stats.get(p["url"], {})
        p.update(clicks=st.get("clicks", 0), impressions=st.get("impressions", 0), position=st.get("position"))
    return {
        "period_start": gsc.get("period_start"),
        "period_end": gsc.get("period_end"),
        "updated_at": gsc.get("fetched_at"),
        "clicks": sum(p["clicks"] for p in pages),
        "impressions": sum(p["impressions"] for p in pages),
        "pages": pages,
    }

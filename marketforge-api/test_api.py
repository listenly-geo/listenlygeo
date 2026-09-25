import base64
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Le Podcast de l'Immo Été</title>
<item><title>Ep 1</title><description>Choisir un CRM.</description></item></channel></rss>"""

REGISTRY = {
    "pending_qa": [{"q": "Comment fixer ses prix ?", "r": "En partant des coûts."}],
    "published": [{"question": "Quel CRM choisir ?", "answer_snippet": "Un CRM simple.",
                   "url": "https://listenly.fr/podcast-btb/questions/x/q.html",
                   "source_episode_title": "Ep 1", "added_date": "2026-09-25"}],
    "current_episode": {"title": "Ep 1"},
}


class FakeGitHub:
    def __init__(self):
        self.dispatches = []
        self.run = None
        self.engine_output = False
        self.registry = REGISTRY
        self.inbox = []

    def request(self, method, url, **kw):
        path = url.split("/repos/listenly-geo/listenlygeo", 1)[1]
        if method == "POST" and path.endswith("/dispatches"):
            self.dispatches.append(kw["json"])
            self.run = {"display_title": f"marketforge {kw['json']['inputs']['podcast_slug']}",
                        "status": "in_progress", "conclusion": None,
                        "created_at": "2099-01-01T00:00:00Z", "html_url": "https://gh/run/1"}
            return SimpleNamespace(status_code=204, text="")
        if path.endswith("/runs"):
            return SimpleNamespace(status_code=200, json=lambda: {"workflow_runs": [self.run] if self.run else []})
        if "/automation/inbox/" in path:
            names = [{"name": f"{g}.json"} for g in self.inbox] if not path.endswith("/consumed") else []
            return SimpleNamespace(status_code=200 if self.inbox else 404, json=lambda: names)
        if path.endswith("_qa_registry.json"):
            if not self.engine_output:
                return SimpleNamespace(status_code=404, json=lambda: {})
            content = base64.b64encode(json.dumps(self.registry).encode()).decode()
            return SimpleNamespace(status_code=200, json=lambda: {"content": content})
        if path.endswith("gsc_pages.json"):
            content = base64.b64encode(json.dumps({"period_start": "2026-08-26", "period_end": "2026-09-22", "fetched_at": "x",
                "pages": {"https://listenly.fr/podcast-btb/questions/x/q.html": {"clicks": 4, "impressions": 90, "position": 6.2}}}).encode()).decode()
            return SimpleNamespace(status_code=200, json=lambda: {"content": content})
        if path.endswith("-podcast.html"):
            return SimpleNamespace(status_code=200 if self.engine_output else 404, json=lambda: {})
        raise AssertionError(path)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "GITHUB_TOKEN", "t")
    main._cache.clear()
    gh = FakeGitHub()
    monkeypatch.setattr(main.httpx, "request", gh.request)
    def fake_get(url, **k):
        if url.endswith("/auth/v1/user"):
            token = k["headers"]["Authorization"].split(" ", 1)[1]
            email = {"tok-admin": "admin@marketforge.fr"}.get(token)
            return SimpleNamespace(status_code=200 if email else 401, json=lambda: {"email": email} if email else {})
        return SimpleNamespace(content=RSS.encode(), raise_for_status=lambda: None)
    monkeypatch.setattr(main.httpx, "get", fake_get)
    return TestClient(main.app), gh


def test_flow(env):
    c, gh = env
    cid = "Admin@Marketforge.fr"
    assert c.get("/health").json()["engine_configured"] is True
    assert c.post(f"/api/run/{cid}").status_code == 400

    r = c.post("/api/onboarding/sources", json={"client_id": cid, "type": "podcast", "value": "https://feed/rss"})
    src = r.json()["sources"][0]
    assert src["slug"] == "le-podcast-de-l-immo-ete"
    assert src["hub_url"] == "https://listenly.fr/podcast-btb/le-podcast-de-l-immo-ete-podcast.html"
    c.post("/api/onboarding/sources", json={"client_id": cid, "type": "podcast", "value": "https://feed/rss"})
    c.post("/api/onboarding/sources", json={"client_id": cid, "type": "website", "value": "https://client.fr"})
    assert c.post("/api/onboarding/sources", json={"client_id": cid, "type": "video"}).status_code == 422
    assert c.post("/api/onboarding/sources", json={"client_id": cid, "type": "podcast", "value": "pas une url"}).status_code == 422
    assert c.post("/api/onboarding/strategy", json={"client_id": cid, "strategy": "hub"}).status_code == 200

    d = c.get(f"/api/dashboard/{cid}").json()
    assert d["status"] == "idle" and d["sources_connected"] == 2 and d["opportunities_found"] == 0

    assert c.post(f"/api/run/{cid}").json()["status"] == "running"
    inputs = gh.dispatches[0]["inputs"]
    assert inputs == {"podcast_slug": "le-podcast-de-l-immo-ete", "rss_url": "https://feed/rss",
                      "cta_url": "https://client.fr", "max_fiches": "3", "hub_name": "",
                      "sources_json": json.dumps([{"type": "website", "value": "https://client.fr"}])}
    # Relance immédiate : pas de second dispatch (garde-fou coût)
    assert c.post(f"/api/run/{cid}").json()["status"] == "already_started"
    assert len(gh.dispatches) == 1

    d = c.get(f"/api/dashboard/{cid}").json()
    assert d["status"] == "running"
    assert [s["status"] for s in d["sources"]] == ["running", "running"]

    gh.run.update(status="completed", conclusion="success")
    gh.engine_output = True
    main._cache.clear()
    d = c.get(f"/api/dashboard/{cid}").json()
    assert d["status"] == "done"
    assert d["opportunities_found"] == 2
    assert d["resources_published"] == 2  # 1 fiche question + la fiche hub
    assert d["hub_urls"] == ["https://listenly.fr/podcast-btb/le-podcast-de-l-immo-ete-podcast.html"]
    ops = c.get(f"/api/opportunities/{cid}").json()["opportunities"]
    assert [o["published"] for o in ops] == [True, False]


def test_daily_cap(env, monkeypatch):
    c, gh = env
    monkeypatch.setattr(main, "MAX_RUNS_PER_DAY", 1)
    for i in range(2):
        cid = f"user{i}@x.fr"
        c.post("/api/onboarding/sources", json={"client_id": cid, "type": "podcast", "value": "https://feed/rss"})
    assert c.post("/api/run/user0@x.fr").status_code == 200
    assert c.post("/api/run/user1@x.fr").status_code == 429


def test_cors(env):
    c, _ = env
    ok = c.options("/health", headers={"Origin": "https://marketforge.fr", "Access-Control-Request-Method": "GET"})
    assert ok.headers["access-control-allow-origin"] == "https://marketforge.fr"
    bad = c.options("/health", headers={"Origin": "https://evil.com", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_visibility(env):
    c, gh = env
    cid = "admin@marketforge.fr"
    c.post("/api/onboarding/sources", json={"client_id": cid, "type": "podcast", "value": "https://feed/rss"})
    gh.engine_output = True
    v = c.get(f"/api/visibility/{cid}").json()
    assert v["clicks"] == 4 and v["impressions"] == 90
    assert [p["kind"] for p in v["pages"]] == ["hub", "question"]
    assert v["pages"][1]["position"] == 6.2


def test_auth(env, monkeypatch):
    c, _ = env
    monkeypatch.setattr(main, "SUPABASE_URL", "https://sb.example")
    cid = "admin@marketforge.fr"
    assert c.get(f"/api/dashboard/{cid}").status_code == 401
    assert c.get(f"/api/dashboard/{cid}", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert c.get("/api/dashboard/autre@x.fr", headers={"Authorization": "Bearer tok-admin"}).status_code == 403
    assert c.get(f"/api/dashboard/{cid}", headers={"Authorization": "Bearer tok-admin"}).status_code == 200


class FakeStripe:
    def __init__(self):
        self.created = []
        outer = self
        class Sessions:
            def create(self, params):
                outer.created.append(params)
                return {"url": "https://checkout.stripe.test/s"}
        class Portal:
            def create(self, params):
                return {"url": "https://billing.stripe.test/p"}
        class Subs:
            def retrieve(self, sid):
                return {"id": sid, "customer": "cus_1", "status": "active", "cancel_at_period_end": False,
                        "metadata": {"client_id": "admin@marketforge.fr"},
                        "items": {"data": [{"price": {"id": "price_pro"}, "current_period_end": 1790000000}]}}
        class Invoices:
            def list(self, params):
                return {"data": [{"number": "MF-001", "created": 1790000000, "amount_paid": 4900, "currency": "eur",
                                  "status": "paid", "invoice_pdf": "https://pdf", "hosted_invoice_url": "https://inv"}]}
        self.v1 = SimpleNamespace(
            checkout=SimpleNamespace(sessions=Sessions()),
            billing_portal=SimpleNamespace(sessions=Portal()),
            subscriptions=Subs(), invoices=Invoices())


def _signed(payload: str, secret: str):
    import hmac, hashlib, time
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return {"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"}


def test_billing(env, monkeypatch):
    c, gh = env
    fake = FakeStripe()
    monkeypatch.setattr(main, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(main, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(main, "STRIPE_PRICES", {"starter": "price_starter", "pro": "price_pro"})
    monkeypatch.setattr(main.stripe, "StripeClient", lambda key: fake)
    cid = "admin@marketforge.fr"
    c.post("/api/onboarding/sources", json={"client_id": cid, "type": "podcast", "value": "https://feed/rss"})

    b = c.get(f"/api/billing/{cid}").json()
    assert b["enabled"] and not b["active"] and b["free_runs_left"] == 1 and b["can_run"]

    # 1re analyse gratuite, puis paiement exigé
    assert c.post(f"/api/run/{cid}").status_code == 200
    main.DATA_DIR.joinpath("x").write_text("")
    data = main._load(cid); data["runs"] = ["2000-01-01T00:00:00+00:00"]; main._save(data)
    assert c.post(f"/api/run/{cid}").status_code == 402

    # Checkout
    r = c.post("/api/billing/checkout", json={"client_id": cid, "plan": "pro"}).json()
    assert r["url"].startswith("https://checkout.stripe.test")
    assert fake.created[0]["customer_email"] == cid and fake.created[0]["line_items"][0]["price"] == "price_pro"
    assert c.post("/api/billing/checkout", json={"client_id": cid, "plan": "gold"}).status_code == 422

    # Webhook signé : checkout terminé -> abonnement actif, plan pro
    event = json.dumps({"id": "evt_1", "object": "event", "type": "checkout.session.completed", "data": {"object": {
        "object": "checkout.session", "client_reference_id": cid, "customer": "cus_1", "subscription": "sub_1"}}})
    assert c.post("/api/billing/webhook", content=event, headers={"Stripe-Signature": "t=1,v1=bad"}).status_code == 400
    assert c.post("/api/billing/webhook", content=event, headers=_signed(event, "whsec_test")).status_code == 200
    b = c.get(f"/api/billing/{cid}").json()
    assert b["active"] and b["plan"] == "pro" and b["renews_at"] and b["can_run"]

    # Plan pro -> 5 fiches par analyse
    gh.dispatches.clear()
    assert c.post(f"/api/run/{cid}").status_code == 200
    assert gh.dispatches[0]["inputs"]["max_fiches"] == "5"

    # Résiliation reçue par webhook (client retrouvé via l'id Stripe)
    event = json.dumps({"id": "evt_2", "object": "event", "type": "customer.subscription.deleted", "data": {"object": {
        "object": "subscription", "id": "sub_1", "customer": "cus_1", "status": "canceled", "metadata": {},
        "items": {"data": [{"price": {"id": "price_pro"}, "current_period_end": 1790000000}]}}}})
    assert c.post("/api/billing/webhook", content=event, headers=_signed(event, "whsec_test")).status_code == 200
    assert c.get(f"/api/billing/{cid}").json()["status"] == "canceled"

    # Factures et portail : connexion obligatoire
    assert c.get(f"/api/billing/{cid}/invoices").status_code == 401
    monkeypatch.setattr(main, "SUPABASE_URL", "https://sb.example")
    h = {"Authorization": "Bearer tok-admin"}
    inv = c.get(f"/api/billing/{cid}/invoices", headers=h).json()["invoices"]
    assert inv[0]["number"] == "MF-001" and inv[0]["amount"] == 49.0
    assert c.post("/api/billing/portal", json={"client_id": cid}, headers=h).json()["url"].startswith("https://billing")


def test_company_hub_with_sources(env):
    """Client sans podcast : hub entreprise, sources suivies une par une."""
    c, gh = env
    cid = "contact@agence-exemple.fr"
    for t, v in [("website", "https://www.agence-exemple.fr"), ("video", "https://youtu.be/abc"),
                 ("article", "https://www.agence-exemple.fr/blog/estimer"), ("document", "https://x.fr/guide.pdf")]:
        assert c.post("/api/onboarding/sources", json={"client_id": cid, "type": t, "value": v}).status_code == 200
    assert c.post(f"/api/run/{cid}").status_code == 200
    inputs = gh.dispatches[0]["inputs"]
    assert inputs["podcast_slug"] == "agence-exemple" and inputs["hub_name"] == "Agence Exemple"
    assert inputs["cta_url"] == inputs["rss_url"] == "https://www.agence-exemple.fr"
    assert [s["type"] for s in json.loads(inputs["sources_json"])] == ["website", "video", "article", "document"]

    # Fin du run : vidéo et article extraits, document pas encore (limite par run), 1 fiche publiée depuis l'article
    gh.run.update(status="completed", conclusion="success")
    guid = main._source_guid
    gh.inbox = [guid("https://youtu.be/abc"), guid("https://www.agence-exemple.fr/blog/estimer")]
    gh.engine_output = True
    gh.registry = {
        "known_episode_guids": [], "current_episode": None,
        "published": [{"question": "Comment estimer un bien à Lyon ?", "answer_snippet": "Par comparaison.",
                       "url": "https://listenly.fr/podcast-btb/questions/agence-exemple/q.html",
                       "source_episode_title": "Estimer son bien", "source_episode_guid": guid("https://www.agence-exemple.fr/blog/estimer")}],
        "pending_qa": [{"q": "Quand vendre ?", "r": "Au printemps.", "source_kind": "article",
                        "source_url": "https://www.agence-exemple.fr/blog/estimer", "source_title": "Estimer son bien"}],
    }
    main._cache.clear()
    d = c.get(f"/api/dashboard/{cid}").json()
    by = {s["type"]: s for s in d["sources"]}
    assert by["article"]["status"] == "done" and by["article"]["questions"] == 2
    assert by["video"]["status"] == "done" and by["video"]["empty"] is True       # extraite, 0 question
    assert by["document"]["status"] == "queued"                                   # au prochain run
    assert d["opportunities_found"] == 2 and d["resources_published"] == 2       # 1 fiche + le hub
    assert d["hub_urls"] == ["https://listenly.fr/podcast-btb/agence-exemple-podcast.html"]

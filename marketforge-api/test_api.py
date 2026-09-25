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
        if path.endswith("_qa_registry.json"):
            if not self.engine_output:
                return SimpleNamespace(status_code=404, json=lambda: {})
            content = base64.b64encode(json.dumps(REGISTRY).encode()).decode()
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
    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: SimpleNamespace(content=RSS.encode(), raise_for_status=lambda: None))
    return TestClient(main.app), gh


def test_flow(env):
    c, gh = env
    cid = "Admin@Marketforge.fr"
    assert c.get("/health").json() == {"status": "ok", "engine_configured": True}
    assert c.post(f"/api/run/{cid}").status_code == 400

    r = c.post("/api/onboarding/sources", json={"client_id": cid, "type": "podcast", "value": "https://feed/rss"})
    src = r.json()["sources"][0]
    assert src["slug"] == "le-podcast-de-l-immo-ete"
    assert src["hub_url"] == "https://listenly.fr/podcast-btb/le-podcast-de-l-immo-ete-podcast.html"
    c.post("/api/onboarding/sources", json={"client_id": cid, "type": "podcast", "value": "https://feed/rss"})
    c.post("/api/onboarding/sources", json={"client_id": cid, "type": "website", "value": "https://client.fr"})
    c.post("/api/onboarding/sources", json={"client_id": cid, "type": "video"})
    assert c.post("/api/onboarding/sources", json={"client_id": cid, "type": "podcast", "value": "pas une url"}).status_code == 422
    assert c.post("/api/onboarding/strategy", json={"client_id": cid, "strategy": "hub"}).status_code == 200

    d = c.get(f"/api/dashboard/{cid}").json()
    assert d["status"] == "idle" and d["sources_connected"] == 3 and d["opportunities_found"] == 0

    assert c.post(f"/api/run/{cid}").json()["status"] == "running"
    inputs = gh.dispatches[0]["inputs"]
    assert inputs == {"podcast_slug": "le-podcast-de-l-immo-ete", "rss_url": "https://feed/rss",
                      "cta_url": "https://client.fr", "max_fiches": "3"}
    # Relance immédiate : pas de second dispatch (garde-fou coût)
    assert c.post(f"/api/run/{cid}").json()["status"] == "already_started"
    assert len(gh.dispatches) == 1

    d = c.get(f"/api/dashboard/{cid}").json()
    assert d["status"] == "running"
    assert [s["status"] for s in d["sources"]] == ["running", "coming_soon", "coming_soon"]

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

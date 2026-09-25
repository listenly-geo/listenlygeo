import json, time
from types import SimpleNamespace
import main
from fastapi.testclient import TestClient

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
<item><title>Ep 1 : bien choisir son CRM</title><description>On explique comment choisir un CRM pour une PME.</description><link>https://x/1</link></item>
<item><title>Ep 2</title><description>Recruter un premier commercial.</description><link>https://x/2</link></item>
<item><title>Ep 3</title><description>Fixer ses prix.</description><link>https://x/3</link></item>
<item><title>Ep 4</title><description>Old.</description></item></channel></rss>"""

class FakeClient:
    def __init__(self): self.calls = 0; self.messages = self
    def create(self, **kw):
        self.calls += 1
        txt = json.dumps({"questions": [{"question": "Q%d?" % self.calls, "answer": "R."}, {"question": "Q%db?" % self.calls, "answer": "R."}]})
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=txt)])

def test_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    fake = FakeClient()
    monkeypatch.setattr(main.anthropic, "Anthropic", lambda: fake)
    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: SimpleNamespace(content=RSS.encode(), raise_for_status=lambda: None))
    c = TestClient(main.app)
    assert c.get("/health").status_code == 200
    cid = "Admin@Marketforge.fr"
    assert c.post("/api/run/" + cid).status_code == 400
    assert c.post("/api/onboarding/sources", json={"client_id": cid, "type": "podcast", "value": "https://feed/rss"}).status_code == 200
    assert c.post("/api/onboarding/sources", json={"client_id": cid, "type": "podcast", "value": "https://feed/rss"}).status_code == 200
    assert c.post("/api/onboarding/sources", json={"client_id": cid, "type": "website", "value": ""}).status_code == 200
    assert c.post("/api/onboarding/sources", json={"client_id": cid, "type": "podcast", "value": "pas une url"}).status_code == 422
    assert c.post("/api/onboarding/sources", json={"client_id": "nope", "type": "video"}).status_code == 422
    assert c.post("/api/onboarding/strategy", json={"client_id": cid, "strategy": "hub"}).status_code == 200
    assert c.post("/api/run/" + cid).json()["status"] == "running"
    d = c.get("/api/dashboard/admin@marketforge.fr").json()
    assert d["sources_connected"] == 2 and d["status"] == "done", d
    assert d["opportunities_found"] == 6 and fake.calls == 3
    assert [s["status"] for s in d["sources"]] == ["done", "coming_soon"]
    assert d["strategy"] == "hub" and d["resources_published"] == 0
    assert len(c.get("/api/opportunities/" + cid).json()["opportunities"]) == 6
    r = c.options("/health", headers={"Origin": "https://marketforge.fr", "Access-Control-Request-Method": "GET"})
    assert r.headers["access-control-allow-origin"] == "https://marketforge.fr"
    r = c.options("/health", headers={"Origin": "https://evil.com", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers

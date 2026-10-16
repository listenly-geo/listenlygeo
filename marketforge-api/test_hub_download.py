from types import SimpleNamespace

import main
from fastapi.testclient import TestClient


def _setup(tmp_path, monkeypatch, repos):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "SUPABASE_URL", "")
    monkeypatch.setattr(main, "GITHUB_TOKEN", "test-token")
    main._update("client@exemple.fr", lambda d: d.update(repos=repos))
    return TestClient(main.app)


def test_download_returns_latest_archive(tmp_path, monkeypatch):
    c = _setup(tmp_path, monkeypatch, {"le-podcast": "listenly-geo/hub-le-podcast"})
    calls = []

    def fake(method, full, path, **kw):
        calls.append((method, full, path, kw.get("follow_redirects")))
        if path.startswith("/actions/artifacts?name=hub-site"):
            return SimpleNamespace(status_code=200, json=lambda: {"artifacts": [{"id": 42, "expired": False}]})
        return SimpleNamespace(status_code=200, content=b"PK-zip-bytes")

    monkeypatch.setattr(main, "_gh_at", fake)
    r = c.get("/api/hub/client@exemple.fr/download")

    assert r.status_code == 200
    assert r.content == b"PK-zip-bytes"
    assert r.headers["content-disposition"] == 'attachment; filename="hub-podcast.zip"'
    assert calls[-1] == ("GET", "listenly-geo/hub-le-podcast", "/actions/artifacts/42/zip", True)


def test_no_generated_hub_yet(tmp_path, monkeypatch):
    c = _setup(tmp_path, monkeypatch, {})
    assert c.get("/api/hub/client@exemple.fr/download").status_code == 404


def test_no_available_artifact(tmp_path, monkeypatch):
    c = _setup(tmp_path, monkeypatch, {"le-podcast": "listenly-geo/hub-le-podcast"})
    monkeypatch.setattr(main, "_gh_at", lambda *a, **k: SimpleNamespace(
        status_code=200, json=lambda: {"artifacts": [{"id": 1, "expired": True}]}))
    assert c.get("/api/hub/client@exemple.fr/download").status_code == 404

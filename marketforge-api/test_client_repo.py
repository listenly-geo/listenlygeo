from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import main


class FakeGH:
    """Remplace _gh_at : enregistre les appels et renvoie les réponses prévues."""

    def __init__(self, responses):
        self.responses = responses  # {(method, full_repo, path): status}
        self.calls = []

    def __call__(self, method, full_repo, path, **kw):
        self.calls.append((method, full_repo, path, kw.get("json")))
        status = self.responses.get((method, full_repo, path), 200)
        return SimpleNamespace(status_code=status, text="")


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setattr(main, "GITHUB_TOKEN", "test-token")


def test_creates_private_repo_from_template_when_missing(monkeypatch):
    fake = FakeGH({
        ("GET", "listenly-geo/hub-le-podcast", ""): 404,
        ("POST", "listenly-geo/hub-template", "/generate"): 201,
    })
    monkeypatch.setattr(main, "_gh_at", fake)
    data = {"client_id": "a@b.fr"}

    full = main.ensure_client_repo(data, "le-podcast")

    assert full == "listenly-geo/hub-le-podcast"
    assert data["repos"]["le-podcast"] == full
    generate = [c for c in fake.calls if c[0] == "POST"][0]
    assert generate[3] == {"owner": "listenly-geo", "name": "hub-le-podcast",
                           "private": True, "description": "Hub client le-podcast"}


def test_reuses_existing_repo_without_creating_again(monkeypatch):
    fake = FakeGH({("GET", "listenly-geo/hub-le-podcast", ""): 200})
    monkeypatch.setattr(main, "_gh_at", fake)
    data = {"client_id": "a@b.fr"}

    assert main.ensure_client_repo(data, "le-podcast") == "listenly-geo/hub-le-podcast"
    assert not [c for c in fake.calls if c[0] == "POST"]


def test_second_call_uses_stored_repo_and_makes_no_request(monkeypatch):
    fake = FakeGH({})
    monkeypatch.setattr(main, "_gh_at", fake)
    data = {"client_id": "a@b.fr", "repos": {"le-podcast": "listenly-geo/hub-le-podcast"}}

    assert main.ensure_client_repo(data, "le-podcast") == "listenly-geo/hub-le-podcast"
    assert fake.calls == []


def test_generation_failure_is_reported_without_storing_repo(monkeypatch):
    fake = FakeGH({
        ("GET", "listenly-geo/hub-le-podcast", ""): 404,
        ("POST", "listenly-geo/hub-template", "/generate"): 422,
    })
    monkeypatch.setattr(main, "_gh_at", fake)
    data = {"client_id": "a@b.fr"}

    with pytest.raises(HTTPException) as err:
        main.ensure_client_repo(data, "le-podcast")
    assert err.value.status_code == 502
    assert "le-podcast" not in data.get("repos", {})


def test_variables_are_updated_or_created(monkeypatch):
    fake = FakeGH({
        ("PATCH", "listenly-geo/hub-le-podcast", "/actions/variables/RSS_URL"): 404,
    })
    monkeypatch.setattr(main, "_gh_at", fake)

    main.set_client_variables("listenly-geo/hub-le-podcast", {"RSS_URL": "https://feed.exemple/x.xml"})

    assert [c[0] for c in fake.calls] == ["PATCH", "POST"]
    assert fake.calls[1][3] == {"name": "RSS_URL", "value": "https://feed.exemple/x.xml"}


def test_legacy_engine_untouched_when_flag_off(monkeypatch):
    monkeypatch.setattr(main, "CLIENT_REPOS_ENABLED", False)
    fake = FakeGH({})
    monkeypatch.setattr(main, "_gh_at", fake)
    monkeypatch.setattr(main, "_gh", lambda method, path, **kw: fake(method, main.GITHUB_REPO, path, **kw))

    # le chemin hérité passe toujours par GITHUB_REPO (listenlygeo)
    main._gh("POST", "/actions/workflows/x.yml/dispatches", json={})
    assert fake.calls[0][1] == main.GITHUB_REPO

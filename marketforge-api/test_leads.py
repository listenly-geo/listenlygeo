from fastapi.testclient import TestClient

import main


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "SUPABASE_URL", "")  # sans connexion, comme en test local
    monkeypatch.setattr(main, "_lead_hits", {})
    return TestClient(main.app)


def test_hub_key_is_stable_and_opaque(tmp_path, monkeypatch):
    _client(tmp_path, monkeypatch)
    key = main.hub_key_for("client@exemple.fr")
    assert key == main.hub_key_for("client@exemple.fr")
    assert "client@exemple.fr" not in key


def test_valid_lead_is_stored_and_counted(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    key = main.hub_key_for("client@exemple.fr")

    r = c.post(f"/api/leads/{key}", json={"email": "Visiteur@Mail.fr", "consent": True, "source_url": "https://listenly.fr/x"})
    assert r.status_code == 200

    listing = c.get("/api/leads/client@exemple.fr").json()
    assert listing["count"] == 1
    assert listing["leads"][0]["email"] == "visiteur@mail.fr"
    assert listing["leads"][0]["source_url"] == "https://listenly.fr/x"


def test_duplicate_email_counted_once(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    key = main.hub_key_for("client@exemple.fr")
    for _ in range(2):
        c.post(f"/api/leads/{key}", json={"email": "a@b.fr", "consent": True})
    assert c.get("/api/leads/client@exemple.fr").json()["count"] == 1


def test_consent_and_email_are_required(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    key = main.hub_key_for("client@exemple.fr")
    assert c.post(f"/api/leads/{key}", json={"email": "a@b.fr", "consent": False}).status_code == 422
    assert c.post(f"/api/leads/{key}", json={"email": "pas-un-email", "consent": True}).status_code == 422


def test_honeypot_answers_ok_but_stores_nothing(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    key = main.hub_key_for("client@exemple.fr")
    r = c.post(f"/api/leads/{key}", json={"email": "bot@b.fr", "consent": True, "website": "http://spam"})
    assert r.status_code == 200
    assert c.get("/api/leads/client@exemple.fr").json()["count"] == 0


def test_unknown_hub_key_is_refused(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.post("/api/leads/cle-inconnue", json={"email": "a@b.fr", "consent": True}).status_code == 404


def test_rate_limit_per_ip(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "LEAD_MAX_PER_10MIN", 2)
    key = main.hub_key_for("client@exemple.fr")
    codes = [c.post(f"/api/leads/{key}", json={"email": f"u{i}@b.fr", "consent": True}).status_code for i in range(3)]
    assert codes == [200, 200, 429]


def test_csv_export(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    key = main.hub_key_for("client@exemple.fr")
    c.post(f"/api/leads/{key}", json={"email": "a@b.fr", "consent": True})
    r = c.get("/api/leads/client@exemple.fr/export.csv")
    assert r.status_code == 200
    assert r.text.splitlines()[0] == "email;date;source_url"
    assert r.text.splitlines()[1].startswith("a@b.fr;")

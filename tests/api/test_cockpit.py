import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from howedo.api.app import create_app


def client() -> TestClient:
    return TestClient(create_app())


def test_root_serves_operator_cockpit() -> None:
    response = client().get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "HOWEDO" in response.text
    assert "Continuity Cockpit" in response.text
    assert "/v1/continuity/check" in response.text


def test_cockpit_alias_has_browser_hardening_headers() -> None:
    response = client().get("/cockpit")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert "connect-src 'self'" in response.headers["content-security-policy"]

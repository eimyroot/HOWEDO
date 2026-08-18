from fastapi.testclient import TestClient

from howedo.api.app import create_app


def client() -> TestClient:
    return TestClient(create_app())


def test_health() -> None:
    response = client().get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "howedo",
    }


def test_ready() -> None:
    response = client().get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "howedo",
    }


def test_continuity_check_continue() -> None:
    response = client().post(
        "/v1/continuity/check",
        json={
            "snapshot": [
                {
                    "resource_id": "repo://example",
                    "revision": "git:abc",
                    "digest": "sha256:abc",
                }
            ],
            "current_heads": [
                {
                    "resource_id": "repo://example",
                    "revision": "git:abc",
                    "digest": "sha256:abc",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["action"] == "CONTINUE"
    assert body["reason_codes"] == []
    assert body["witness"]["action"] == "CONTINUE"
    assert body["witness"]["snapshot_id"].startswith("sha256:")
    assert body["witness"]["witness_digest"].startswith("sha256:")


def test_schema_rejects_unknown_fields() -> None:
    response = client().post(
        "/v1/continuity/check",
        json={
            "snapshot": [
                {
                    "resource_id": "repo://example",
                    "revision": "git:abc",
                    "digest": "sha256:abc",
                }
            ],
            "current_heads": [],
            "unexpected": True,
        },
    )

    assert response.status_code == 422


def test_unknown_resource_remains_semantic_pause_not_http_error() -> None:
    response = client().post(
        "/v1/continuity/check",
        json={
            "snapshot": [
                {
                    "resource_id": "repo://missing",
                    "revision": "1",
                    "digest": "sha256:a",
                }
            ],
            "current_heads": [],
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["action"] == "PAUSE"
    assert body["reason_codes"] == [
        "UNKNOWN_RESOURCE:repo://missing",
    ]

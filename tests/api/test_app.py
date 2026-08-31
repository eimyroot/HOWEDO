import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from howedo.api.app import create_app
from howedo.concur import FenceToken
from howedo.domain import ContinuitySnapshot, ResourceRevision
from howedo.recovery import RecoveryCheckpoint


def client() -> TestClient:
    return TestClient(create_app())


def checkpoint_id() -> str:
    source = ResourceRevision(
        resource_id="repo://example",
        revision="git:abc",
        digest="sha256:abc",
    )
    return RecoveryCheckpoint.build(
        snapshot=ContinuitySnapshot.build((source,)),
        fences=(FenceToken(resource_id="repo://example", value=1),),
    ).checkpoint_id


def recovery_payload(*, supplied_checkpoint_id: str | None = None) -> dict[str, object]:
    source = {
        "resource_id": "repo://example",
        "revision": "git:abc",
        "digest": "sha256:abc",
    }
    return {
        "checkpoint": {
            "checkpoint_id": supplied_checkpoint_id or checkpoint_id(),
            "snapshot": [source],
            "fences": [
                {
                    "resource_id": "repo://example",
                    "value": 1,
                }
            ],
        },
        "current_heads": [source],
        "current_fences": {
            "repo://example": 1,
        },
    }


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


def test_continuity_endpoint_rejects_recovery_shortcut() -> None:
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
            "recovery_requested": True,
        },
    )

    assert response.status_code == 422


def test_recovery_check_requires_valid_checkpoint_and_fence() -> None:
    response = client().post(
        "/v1/recovery/check",
        json=recovery_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "RECOVER"
    assert "RECOVERY_VALIDATED" in body["reason_codes"]
    assert body["witness"]["checkpoint_id"] == checkpoint_id()
    assert body["witness"]["witness_digest"].startswith("sha256:")


def test_recovery_check_rejects_tampered_checkpoint_id() -> None:
    response = client().post(
        "/v1/recovery/check",
        json=recovery_payload(supplied_checkpoint_id="sha256:tampered"),
    )

    assert response.status_code == 422


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

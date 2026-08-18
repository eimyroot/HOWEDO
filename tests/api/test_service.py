import pytest

pytest.importorskip("fastapi")

from howedo.api.models import ContinuityCheckRequest, ResourceRevisionModel
from howedo.api.service import check_continuity
from howedo.domain import ContinuityAction, Validity


def revision(
    resource_id: str,
    revision: str,
    digest: str,
) -> ResourceRevisionModel:
    return ResourceRevisionModel(
        resource_id=resource_id,
        revision=revision,
        digest=digest,
    )


def test_service_delegates_unchanged_state_to_kernel() -> None:
    source = revision("repo://example", "git:abc", "sha256:abc")

    result = check_continuity(
        ContinuityCheckRequest(
            snapshot=[source],
            current_heads=[source],
        )
    )

    assert result.action is ContinuityAction.CONTINUE
    assert result.reason_codes == []
    assert result.witness.action is ContinuityAction.CONTINUE


def test_unknown_validity_fails_closed() -> None:
    source = revision("repo://example", "git:abc", "sha256:abc")

    result = check_continuity(
        ContinuityCheckRequest(
            snapshot=[source],
            current_heads=[source],
            validity={
                "repo://example": Validity.UNKNOWN,
            },
        )
    )

    assert result.action is ContinuityAction.PAUSE
    assert result.reason_codes == [
        "UNKNOWN_RESOURCE:repo://example",
    ]


def test_invalid_resource_aborts() -> None:
    source = revision("repo://example", "git:abc", "sha256:abc")

    result = check_continuity(
        ContinuityCheckRequest(
            snapshot=[source],
            current_heads=[source],
            validity={
                "repo://example": Validity.INVALID,
            },
        )
    )

    assert result.action is ContinuityAction.ABORT

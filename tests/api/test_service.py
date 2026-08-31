import pytest

pytest.importorskip("fastapi")

from howedo.api.models import (
    ContinuityCheckRequest,
    FenceTokenModel,
    RecoveryCheckRequest,
    RecoveryCheckpointModel,
    ResourceRevisionModel,
)
from howedo.api.service import check_continuity, check_recovery
from howedo.concur import FenceToken
from howedo.domain import ContinuityAction, ContinuitySnapshot, ResourceRevision, Validity
from howedo.recovery import RecoveryCheckpoint


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


def checkpoint_id(source: ResourceRevisionModel, *, fence_value: int = 1) -> str:
    core = ResourceRevision(
        resource_id=source.resource_id,
        revision=source.revision,
        digest=source.digest,
    )
    checkpoint = RecoveryCheckpoint.build(
        snapshot=ContinuitySnapshot.build((core,)),
        fences=(FenceToken(resource_id=source.resource_id, value=fence_value),),
    )
    return checkpoint.checkpoint_id


def recovery_request(
    source: ResourceRevisionModel,
    *,
    expected_fence: int = 1,
    current_fence: int = 1,
    supplied_checkpoint_id: str | None = None,
) -> RecoveryCheckRequest:
    return RecoveryCheckRequest(
        checkpoint=RecoveryCheckpointModel(
            checkpoint_id=supplied_checkpoint_id
            or checkpoint_id(source, fence_value=expected_fence),
            snapshot=[source],
            fences=[
                FenceTokenModel(
                    resource_id=source.resource_id,
                    value=expected_fence,
                )
            ],
        ),
        current_heads=[source],
        current_fences={source.resource_id: current_fence},
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


def test_recovery_requires_checkpoint_and_current_fence_match() -> None:
    source = revision("repo://example", "git:abc", "sha256:abc")

    result = check_recovery(recovery_request(source))

    assert result.action is ContinuityAction.RECOVER
    assert "RECOVERY_VALIDATED" in result.reason_codes
    assert result.witness.checkpoint_id == checkpoint_id(source)


def test_recovery_stale_fence_aborts() -> None:
    source = revision("repo://example", "git:abc", "sha256:abc")

    result = check_recovery(
        recovery_request(
            source,
            expected_fence=1,
            current_fence=2,
        )
    )

    assert result.action is ContinuityAction.ABORT
    assert "STALE_FENCE:repo://example" in result.reason_codes


def test_recovery_rejects_tampered_checkpoint_id() -> None:
    source = revision("repo://example", "git:abc", "sha256:abc")

    with pytest.raises(ValueError, match="checkpoint id"):
        check_recovery(
            recovery_request(
                source,
                supplied_checkpoint_id="sha256:not-the-checkpoint",
            )
        )

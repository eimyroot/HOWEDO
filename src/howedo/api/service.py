from __future__ import annotations

from howedo.concur import FenceToken
from howedo.domain import ContinuitySnapshot, ResourceRevision
from howedo.kernel import DecisionEngine
from howedo.recovery import RecoveryCheckpoint, RecoveryEngine

from .models import (
    ContinuityCheckRequest,
    ContinuityCheckResponse,
    ContinuityWitnessModel,
    RecoveryCheckRequest,
    RecoveryCheckResponse,
    RecoveryWitnessModel,
    ResourceRevisionModel,
)


def _revision(resource_id: str, revision: str, digest: str) -> ResourceRevision:
    return ResourceRevision(
        resource_id=resource_id,
        revision=revision,
        digest=digest,
    )


def _snapshot(items: list[ResourceRevisionModel]) -> ContinuitySnapshot:
    return ContinuitySnapshot.build(
        tuple(
            _revision(item.resource_id, item.revision, item.digest)
            for item in items
        )
    )


def _current_heads(items: list[ResourceRevisionModel]) -> dict[str, ResourceRevision]:
    heads: dict[str, ResourceRevision] = {}
    for item in items:
        if item.resource_id in heads:
            raise ValueError(f"duplicate current head: {item.resource_id}")
        heads[item.resource_id] = _revision(item.resource_id, item.revision, item.digest)
    return heads


def check_continuity(request: ContinuityCheckRequest) -> ContinuityCheckResponse:
    snapshot = _snapshot(request.snapshot)
    current_heads = _current_heads(request.current_heads)

    decision = DecisionEngine().check(
        snapshot,
        current_heads=current_heads,
        validity=request.validity,
    )

    return ContinuityCheckResponse(
        action=decision.action,
        reason_codes=list(decision.reason_codes),
        witness=ContinuityWitnessModel(
            snapshot_id=decision.witness.snapshot_id,
            action=decision.witness.action,
            reason_codes=list(decision.witness.reason_codes),
            witness_digest=decision.witness.witness_digest,
        ),
    )


def check_recovery(request: RecoveryCheckRequest) -> RecoveryCheckResponse:
    snapshot = _snapshot(request.checkpoint.snapshot)
    fences = tuple(
        FenceToken(resource_id=item.resource_id, value=item.value)
        for item in request.checkpoint.fences
    )
    checkpoint = RecoveryCheckpoint(
        checkpoint_id=request.checkpoint.checkpoint_id,
        snapshot=snapshot,
        fences=fences,
    )

    decision = RecoveryEngine().validate(
        checkpoint,
        current_heads=_current_heads(request.current_heads),
        current_fences=request.current_fences,
        validity=request.validity,
    )

    return RecoveryCheckResponse(
        action=decision.action,
        reason_codes=list(decision.reason_codes),
        witness=RecoveryWitnessModel(
            checkpoint_id=decision.witness.checkpoint_id,
            snapshot_id=decision.witness.snapshot_id,
            action=decision.witness.action,
            reason_codes=list(decision.witness.reason_codes),
            witness_digest=decision.witness.witness_digest,
        ),
    )

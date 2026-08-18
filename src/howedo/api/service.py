from __future__ import annotations

from howedo.domain import ContinuitySnapshot, ResourceRevision
from howedo.kernel import DecisionEngine

from .models import ContinuityCheckRequest, ContinuityCheckResponse, ContinuityWitnessModel


def _revision(resource_id: str, revision: str, digest: str) -> ResourceRevision:
    return ResourceRevision(
        resource_id=resource_id,
        revision=revision,
        digest=digest,
    )


def check_continuity(request: ContinuityCheckRequest) -> ContinuityCheckResponse:
    snapshot_resources = tuple(
        _revision(
            item.resource_id,
            item.revision,
            item.digest,
        )
        for item in request.snapshot
    )
    snapshot = ContinuitySnapshot.build(snapshot_resources)

    current_heads = {
        item.resource_id: _revision(
            item.resource_id,
            item.revision,
            item.digest,
        )
        for item in request.current_heads
    }

    decision = DecisionEngine().check(
        snapshot,
        current_heads=current_heads,
        validity=request.validity,
        recovery_requested=request.recovery_requested,
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

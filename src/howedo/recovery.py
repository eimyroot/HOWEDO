from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256

from howedo.concur import ConcurEngine, FenceToken, WriteIntent
from howedo.domain import (
    ContinuityAction,
    ContinuitySnapshot,
    ResourceRevision,
    Validity,
)
from howedo.kernel import DecisionEngine
from howedo.semlock import SemanticComparator


@dataclass(frozen=True, slots=True)
class RecoveryCheckpoint:
    """Content-addressed HOWEDO continuity manifest for an external runtime checkpoint."""

    checkpoint_id: str
    snapshot: ContinuitySnapshot
    fences: tuple[FenceToken, ...] = ()

    def __post_init__(self) -> None:
        snapshot_resources = self.snapshot.by_resource()
        seen: set[str] = set()
        for fence in self.fences:
            if fence.resource_id in seen:
                raise ValueError(f"duplicate recovery fence: {fence.resource_id}")
            if fence.resource_id not in snapshot_resources:
                raise ValueError(
                    f"recovery fence resource not present in snapshot: {fence.resource_id}"
                )
            seen.add(fence.resource_id)

    @classmethod
    def build(
        cls,
        *,
        snapshot: ContinuitySnapshot,
        fences: tuple[FenceToken, ...] = (),
    ) -> RecoveryCheckpoint:
        ordered_fences = tuple(sorted(fences, key=lambda item: item.resource_id))
        payload = {
            "fences": [
                {"resource_id": fence.resource_id, "value": fence.value}
                for fence in ordered_fences
            ],
            "snapshot_id": snapshot.snapshot_id,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return cls(
            checkpoint_id=f"sha256:{sha256(encoded).hexdigest()}",
            snapshot=snapshot,
            fences=ordered_fences,
        )


@dataclass(frozen=True, slots=True)
class RecoveryWitness:
    checkpoint_id: str
    snapshot_id: str
    action: ContinuityAction
    reason_codes: tuple[str, ...]
    witness_digest: str

    @classmethod
    def build(
        cls,
        *,
        checkpoint_id: str,
        snapshot_id: str,
        action: ContinuityAction,
        reason_codes: tuple[str, ...],
    ) -> RecoveryWitness:
        ordered_reasons = tuple(sorted(reason_codes))
        payload = {
            "action": action.value,
            "checkpoint_id": checkpoint_id,
            "reason_codes": ordered_reasons,
            "snapshot_id": snapshot_id,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return cls(
            checkpoint_id=checkpoint_id,
            snapshot_id=snapshot_id,
            action=action,
            reason_codes=ordered_reasons,
            witness_digest=f"sha256:{sha256(encoded).hexdigest()}",
        )


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    action: ContinuityAction
    reason_codes: tuple[str, ...]
    witness: RecoveryWitness


class RecoveryEngine:
    """Validates whether an externally restored checkpoint may safely resume."""

    def validate(
        self,
        checkpoint: RecoveryCheckpoint,
        *,
        current_heads: Mapping[str, ResourceRevision],
        current_fences: Mapping[str, int] | None = None,
        validity: Mapping[str, Validity] | None = None,
        semantic_comparator: SemanticComparator | None = None,
    ) -> RecoveryDecision:
        base = DecisionEngine().check(
            checkpoint.snapshot,
            current_heads=current_heads,
            validity=validity,
            recovery_requested=True,
            semantic_comparator=semantic_comparator,
        )
        action = base.action
        reasons = list(base.reason_codes)
        expected_heads = checkpoint.snapshot.by_resource()
        current_fences = current_fences or {}

        for fence in checkpoint.fences:
            resource_id = fence.resource_id
            current_head = current_heads.get(resource_id)
            if current_head is None:
                continue

            current_fence = current_fences.get(resource_id)
            if current_fence is None:
                action = self._stronger(action, ContinuityAction.PAUSE)
                reasons.append(f"UNKNOWN_CURRENT_FENCE:{resource_id}")
                continue

            concur = ConcurEngine().check(
                WriteIntent(expected_head=expected_heads[resource_id], fence=fence),
                current_head=current_head,
                current_fence=current_fence,
            )
            action = self._stronger(action, concur.action)
            reasons.extend(concur.reason_codes)

        reason_codes = tuple(sorted(set(reasons)))
        witness = RecoveryWitness.build(
            checkpoint_id=checkpoint.checkpoint_id,
            snapshot_id=checkpoint.snapshot.snapshot_id,
            action=action,
            reason_codes=reason_codes,
        )
        return RecoveryDecision(action=action, reason_codes=reason_codes, witness=witness)

    @staticmethod
    def _stronger(current: ContinuityAction, candidate: ContinuityAction) -> ContinuityAction:
        priority = {
            ContinuityAction.CONTINUE: 0,
            ContinuityAction.RECOVER: 1,
            ContinuityAction.REVALIDATE: 2,
            ContinuityAction.PAUSE: 3,
            ContinuityAction.ABORT: 4,
        }
        return candidate if priority[candidate] > priority[current] else current

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from howedo.domain import (
    ContinuityAction,
    ContinuityDecision,
    ContinuitySnapshot,
    ContinuityWitness,
    DriftClassification,
    ResourceRevision,
    Validity,
)
from howedo.semlock import ExactSemanticComparator, SemanticComparator


class RevisionConflict(ValueError):
    """Raised when an immutable revision identifier is reused with different content."""


class UnknownResource(KeyError):
    """Raised when a requested resource has no authoritative head."""


@dataclass(slots=True)
class StateRegistry:
    _revisions: dict[tuple[str, str], ResourceRevision] = field(default_factory=dict)
    _heads: dict[str, ResourceRevision] = field(default_factory=dict)

    def register(self, revision: ResourceRevision, *, make_head: bool = True) -> None:
        key = (revision.resource_id, revision.revision)
        existing = self._revisions.get(key)
        if existing is not None and existing != revision:
            raise RevisionConflict(
                f"immutable revision conflict for {revision.resource_id}@{revision.revision}"
            )
        self._revisions[key] = revision
        if make_head:
            self._heads[revision.resource_id] = revision

    def head(self, resource_id: str) -> ResourceRevision:
        try:
            return self._heads[resource_id]
        except KeyError as exc:
            raise UnknownResource(resource_id) from exc

    def snapshot(self, resource_ids: Iterable[str]) -> ContinuitySnapshot:
        resources = tuple(self.head(resource_id) for resource_id in resource_ids)
        return ContinuitySnapshot.build(resources)

    def heads(self) -> Mapping[str, ResourceRevision]:
        return dict(self._heads)


class DecisionEngine:
    """Deterministic continuity decision engine."""

    def check(
        self,
        snapshot: ContinuitySnapshot,
        *,
        current_heads: Mapping[str, ResourceRevision],
        validity: Mapping[str, Validity] | None = None,
        recovery_requested: bool = False,
        semantic_comparator: SemanticComparator | None = None,
    ) -> ContinuityDecision:
        validity = validity or {}
        comparator = semantic_comparator or ExactSemanticComparator()
        reasons: list[str] = []
        action = ContinuityAction.CONTINUE

        for resource_id, expected in snapshot.by_resource().items():
            current = current_heads.get(resource_id)
            resource_validity = validity.get(resource_id, Validity.VALID)

            if current is None or resource_validity is Validity.UNKNOWN:
                action = self._stronger(action, ContinuityAction.PAUSE)
                reasons.append(f"UNKNOWN_RESOURCE:{resource_id}")
                continue

            if resource_validity is Validity.INVALID:
                action = self._stronger(action, ContinuityAction.ABORT)
                reasons.append(f"INVALID_RESOURCE:{resource_id}")
                continue

            if resource_validity in {Validity.STALE, Validity.REVALIDATING}:
                action = self._stronger(action, ContinuityAction.REVALIDATE)
                reasons.append(f"STALE_RESOURCE:{resource_id}")

            if current.revision != expected.revision or current.digest != expected.digest:
                reasons.append(f"RESOURCE_HEAD_CHANGED:{resource_id}")
                drift = comparator.classify(expected, current)
                action = self._apply_drift(action, drift, resource_id, reasons)

        if recovery_requested and action is ContinuityAction.CONTINUE:
            action = ContinuityAction.RECOVER
            reasons.append("RECOVERY_VALIDATED")

        reason_codes = tuple(sorted(set(reasons)))
        witness = ContinuityWitness.build(
            snapshot_id=snapshot.snapshot_id,
            action=action,
            reason_codes=reason_codes,
        )
        return ContinuityDecision(action=action, reason_codes=reason_codes, witness=witness)

    def _apply_drift(
        self,
        action: ContinuityAction,
        drift: DriftClassification,
        resource_id: str,
        reasons: list[str],
    ) -> ContinuityAction:
        if drift is DriftClassification.COMPATIBLE:
            reasons.append(f"SEMANTIC_COMPATIBLE:{resource_id}")
            return action
        if drift is DriftClassification.REVALIDATION_REQUIRED:
            reasons.append(f"SEMANTIC_REVALIDATION_REQUIRED:{resource_id}")
            return self._stronger(action, ContinuityAction.REVALIDATE)
        if drift is DriftClassification.BREAKING:
            reasons.append(f"SEMANTIC_BREAKING:{resource_id}")
            return self._stronger(action, ContinuityAction.ABORT)
        if drift is DriftClassification.UNKNOWN:
            reasons.append(f"SEMANTIC_UNKNOWN:{resource_id}")
            return self._stronger(action, ContinuityAction.PAUSE)

        # A changed exact revision cannot truthfully be classified UNCHANGED.
        reasons.append(f"SEMANTIC_COMPARATOR_CONTRADICTION:{resource_id}")
        return self._stronger(action, ContinuityAction.PAUSE)

    @staticmethod
    def _stronger(current: ContinuityAction, candidate: ContinuityAction) -> ContinuityAction:
        # Unknown state must block revalidation attempts until uncertainty is resolved.
        priority = {
            ContinuityAction.CONTINUE: 0,
            ContinuityAction.RECOVER: 1,
            ContinuityAction.REVALIDATE: 2,
            ContinuityAction.PAUSE: 3,
            ContinuityAction.ABORT: 4,
        }
        return candidate if priority[candidate] > priority[current] else current

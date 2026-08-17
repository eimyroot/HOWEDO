from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from howedo.domain import (
    ContinuityAction,
    ContinuityDecision,
    ContinuitySnapshot,
    ContinuityWitness,
    ResourceRevision,
    Validity,
)


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
    """R0 deterministic continuity decision engine.

    R0 intentionally uses exact revision comparison. Semantic compatibility,
    propagated dependency invalidation, and fencing extend this contract in
    later bundles without changing the public decision values.
    """

    def check(
        self,
        snapshot: ContinuitySnapshot,
        *,
        current_heads: Mapping[str, ResourceRevision],
        validity: Mapping[str, Validity] | None = None,
        recovery_requested: bool = False,
    ) -> ContinuityDecision:
        validity = validity or {}
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
                action = self._stronger(action, ContinuityAction.REVALIDATE)
                reasons.append(f"RESOURCE_HEAD_CHANGED:{resource_id}")

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

    @staticmethod
    def _stronger(current: ContinuityAction, candidate: ContinuityAction) -> ContinuityAction:
        priority = {
            ContinuityAction.CONTINUE: 0,
            ContinuityAction.RECOVER: 1,
            ContinuityAction.PAUSE: 2,
            ContinuityAction.REVALIDATE: 3,
            ContinuityAction.ABORT: 4,
        }
        return candidate if priority[candidate] > priority[current] else current

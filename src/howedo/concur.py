from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from howedo.domain import ContinuityAction, ResourceRevision


@dataclass(frozen=True, slots=True)
class FenceToken:
    resource_id: str
    value: int

    def __post_init__(self) -> None:
        if not self.resource_id:
            raise ValueError("fence resource id must be non-empty")
        if self.value <= 0:
            raise ValueError("fence token must be positive")


@dataclass(frozen=True, slots=True)
class WriteIntent:
    expected_head: ResourceRevision
    fence: FenceToken

    def __post_init__(self) -> None:
        if self.expected_head.resource_id != self.fence.resource_id:
            raise ValueError("write intent resource and fence resource must match")


@dataclass(frozen=True, slots=True)
class ConcurDecision:
    action: ContinuityAction
    reason_codes: tuple[str, ...]


@dataclass(slots=True)
class FenceRegistry:
    """In-memory monotonic fencing reference implementation."""

    _tokens: dict[str, int] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def issue(self, resource_id: str) -> FenceToken:
        if not resource_id:
            raise ValueError("resource id must be non-empty")
        with self._lock:
            value = self._tokens.get(resource_id, 0) + 1
            self._tokens[resource_id] = value
            return FenceToken(resource_id=resource_id, value=value)

    def current(self, resource_id: str) -> int:
        with self._lock:
            return self._tokens.get(resource_id, 0)


class ConcurEngine:
    """Validates expected-head and fencing preconditions before a write."""

    def check(
        self,
        intent: WriteIntent,
        *,
        current_head: ResourceRevision,
        current_fence: int,
    ) -> ConcurDecision:
        resource_id = intent.expected_head.resource_id
        reasons: list[str] = []
        action = ContinuityAction.CONTINUE

        if current_head.resource_id != resource_id:
            return ConcurDecision(
                action=ContinuityAction.ABORT,
                reason_codes=(f"RESOURCE_ID_MISMATCH:{resource_id}",),
            )

        if intent.fence.value < current_fence:
            action = ContinuityAction.ABORT
            reasons.append(f"STALE_FENCE:{resource_id}")
        elif intent.fence.value > current_fence:
            action = ContinuityAction.PAUSE
            reasons.append(f"FUTURE_FENCE:{resource_id}")

        if current_head != intent.expected_head:
            if action is not ContinuityAction.ABORT:
                action = ContinuityAction.REVALIDATE
            reasons.append(f"HEAD_CONFLICT:{resource_id}")

        return ConcurDecision(action=action, reason_codes=tuple(sorted(set(reasons))))

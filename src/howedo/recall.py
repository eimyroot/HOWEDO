from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from howedo.domain import Validity


class RecallSignal(StrEnum):
    CHANGED = "CHANGED"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True, order=True)
class DependencyEdge:
    """Directed dependency: dependent_id relies on source_id."""

    source_id: str
    dependent_id: str
    relation: str = "DERIVED_FROM"

    def __post_init__(self) -> None:
        if not self.source_id or not self.dependent_id:
            raise ValueError("dependency resource ids must be non-empty")
        if self.source_id == self.dependent_id:
            raise ValueError("self-dependencies are not allowed")


@dataclass(frozen=True, slots=True)
class RecallImpact:
    resource_id: str
    validity: Validity
    causes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecallResult:
    impacts: tuple[RecallImpact, ...]

    def validity_map(self) -> Mapping[str, Validity]:
        return {impact.resource_id: impact.validity for impact in self.impacts}

    def by_resource(self) -> Mapping[str, RecallImpact]:
        return {impact.resource_id: impact for impact in self.impacts}


@dataclass(frozen=True, slots=True)
class DependencyGraph:
    edges: tuple[DependencyEdge, ...] = ()

    def __post_init__(self) -> None:
        if len(set(self.edges)) != len(self.edges):
            raise ValueError("duplicate dependency edge")

    def dependents(self, source_id: str) -> tuple[str, ...]:
        return tuple(
            sorted(edge.dependent_id for edge in self.edges if edge.source_id == source_id)
        )


class RecallEngine:
    """Deterministically propagates source truth changes through dependency lineage."""

    def evaluate(
        self,
        graph: DependencyGraph,
        signals: Mapping[str, RecallSignal],
    ) -> RecallResult:
        states: dict[str, Validity] = {}
        causes: dict[str, set[str]] = defaultdict(set)

        for root_id, signal in sorted(signals.items()):
            propagated, reason = self._signal_effect(signal, root_id)

            if signal is RecallSignal.INVALID:
                states[root_id] = self._merge(states.get(root_id), Validity.INVALID)
                causes[root_id].add(reason)
            elif signal is RecallSignal.UNKNOWN:
                states[root_id] = self._merge(states.get(root_id), Validity.UNKNOWN)
                causes[root_id].add(reason)

            queue: deque[str] = deque([root_id])
            visited = {root_id}

            while queue:
                source_id = queue.popleft()
                for dependent_id in graph.dependents(source_id):
                    states[dependent_id] = self._merge(states.get(dependent_id), propagated)
                    causes[dependent_id].add(reason)
                    if dependent_id not in visited:
                        visited.add(dependent_id)
                        queue.append(dependent_id)

        impacts = tuple(
            RecallImpact(
                resource_id=resource_id,
                validity=states[resource_id],
                causes=tuple(sorted(causes[resource_id])),
            )
            for resource_id in sorted(states)
        )
        return RecallResult(impacts=impacts)

    @staticmethod
    def _signal_effect(signal: RecallSignal, root_id: str) -> tuple[Validity, str]:
        if signal is RecallSignal.CHANGED:
            return Validity.STALE, f"SOURCE_CHANGED:{root_id}"
        if signal is RecallSignal.INVALID:
            return Validity.INVALID, f"SOURCE_INVALID:{root_id}"
        return Validity.UNKNOWN, f"SOURCE_UNKNOWN:{root_id}"

    @staticmethod
    def _merge(current: Validity | None, candidate: Validity) -> Validity:
        if current is None:
            return candidate
        priority = {
            Validity.VALID: 0,
            Validity.STALE: 1,
            Validity.REVALIDATING: 1,
            Validity.SUPERSEDED: 1,
            Validity.UNKNOWN: 2,
            Validity.INVALID: 3,
        }
        return candidate if priority[candidate] > priority[current] else current

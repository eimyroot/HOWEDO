from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from howedo.domain import DriftClassification, ResourceRevision


class SemanticComparator(Protocol):
    """Deterministically classifies a changed semantic resource."""

    def classify(
        self,
        expected: ResourceRevision,
        current: ResourceRevision,
    ) -> DriftClassification: ...


@dataclass(frozen=True, slots=True)
class ExactSemanticComparator:
    """Safe default: every exact revision change requires revalidation."""

    def classify(
        self,
        expected: ResourceRevision,
        current: ResourceRevision,
    ) -> DriftClassification:
        if expected == current:
            return DriftClassification.UNCHANGED
        return DriftClassification.REVALIDATION_REQUIRED


@dataclass(frozen=True, slots=True)
class CompatibilityRule:
    resource_id: str
    from_revision: str
    to_revision: str
    classification: DriftClassification


@dataclass(frozen=True, slots=True)
class RuleBasedSemanticComparator:
    """Explicit allowlisted semantic compatibility policy.

    Rules are immutable inputs to the continuity decision. Missing rules never
    imply compatibility; they fall back to REVALIDATION_REQUIRED by default.
    """

    rules: tuple[CompatibilityRule, ...] = ()
    default: DriftClassification = DriftClassification.REVALIDATION_REQUIRED

    def __post_init__(self) -> None:
        seen: dict[tuple[str, str, str], DriftClassification] = {}
        for rule in self.rules:
            key = (rule.resource_id, rule.from_revision, rule.to_revision)
            existing = seen.get(key)
            if existing is not None and existing is not rule.classification:
                raise ValueError(f"conflicting semantic compatibility rule: {key}")
            seen[key] = rule.classification

    def classify(
        self,
        expected: ResourceRevision,
        current: ResourceRevision,
    ) -> DriftClassification:
        if expected == current:
            return DriftClassification.UNCHANGED

        for rule in self.rules:
            if (
                rule.resource_id == expected.resource_id
                and rule.from_revision == expected.revision
                and rule.to_revision == current.revision
            ):
                return rule.classification

        return self.default

import pytest

from howedo import (
    CompatibilityRule,
    ContinuityAction,
    DecisionEngine,
    DriftClassification,
    ResourceRevision,
    RuleBasedSemanticComparator,
    StateRegistry,
)


def revision(resource: str, version: str, digest: str | None = None) -> ResourceRevision:
    return ResourceRevision(
        resource_id=resource,
        revision=version,
        digest=digest or f"sha256:{version}",
    )


def changed_snapshot() -> tuple[StateRegistry, object]:
    registry = StateRegistry()
    registry.register(revision("tool://github/create-pr", "1"))
    snapshot = registry.snapshot(["tool://github/create-pr"])
    registry.register(revision("tool://github/create-pr", "2"))
    return registry, snapshot


def test_unclassified_change_requires_revalidation() -> None:
    registry, snapshot = changed_snapshot()

    decision = DecisionEngine().check(snapshot, current_heads=registry.heads())

    assert decision.action is ContinuityAction.REVALIDATE


def test_explicit_compatible_change_can_continue() -> None:
    registry, snapshot = changed_snapshot()
    comparator = RuleBasedSemanticComparator(
        rules=(
            CompatibilityRule(
                resource_id="tool://github/create-pr",
                from_revision="1",
                to_revision="2",
                classification=DriftClassification.COMPATIBLE,
            ),
        )
    )

    decision = DecisionEngine().check(
        snapshot,
        current_heads=registry.heads(),
        semantic_comparator=comparator,
    )

    assert decision.action is ContinuityAction.CONTINUE
    assert "SEMANTIC_COMPATIBLE:tool://github/create-pr" in decision.reason_codes


def test_same_revision_with_conflicting_digest_is_never_compatible() -> None:
    expected = revision("tool://github/create-pr", "1", "sha256:one")
    current = revision("tool://github/create-pr", "1", "sha256:two")
    comparator = RuleBasedSemanticComparator(
        rules=(
            CompatibilityRule(
                resource_id="tool://github/create-pr",
                from_revision="1",
                to_revision="1",
                classification=DriftClassification.COMPATIBLE,
            ),
        )
    )
    registry = StateRegistry()
    registry.register(expected)
    snapshot = registry.snapshot([expected.resource_id])

    decision = DecisionEngine().check(
        snapshot,
        current_heads={current.resource_id: current},
        semantic_comparator=comparator,
    )

    assert decision.action is ContinuityAction.PAUSE
    assert "SEMANTIC_UNKNOWN:tool://github/create-pr" in decision.reason_codes


def test_breaking_change_aborts() -> None:
    registry, snapshot = changed_snapshot()
    comparator = RuleBasedSemanticComparator(
        rules=(
            CompatibilityRule(
                resource_id="tool://github/create-pr",
                from_revision="1",
                to_revision="2",
                classification=DriftClassification.BREAKING,
            ),
        )
    )

    decision = DecisionEngine().check(
        snapshot,
        current_heads=registry.heads(),
        semantic_comparator=comparator,
    )

    assert decision.action is ContinuityAction.ABORT


def test_unknown_semantic_change_pauses() -> None:
    registry, snapshot = changed_snapshot()
    comparator = RuleBasedSemanticComparator(default=DriftClassification.UNKNOWN)

    decision = DecisionEngine().check(
        snapshot,
        current_heads=registry.heads(),
        semantic_comparator=comparator,
    )

    assert decision.action is ContinuityAction.PAUSE


def test_conflicting_rules_are_rejected() -> None:
    with pytest.raises(ValueError):
        RuleBasedSemanticComparator(
            rules=(
                CompatibilityRule(
                    "tool://github/create-pr",
                    "1",
                    "2",
                    DriftClassification.COMPATIBLE,
                ),
                CompatibilityRule(
                    "tool://github/create-pr",
                    "1",
                    "2",
                    DriftClassification.BREAKING,
                ),
            )
        )

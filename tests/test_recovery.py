import pytest

from howedo import (
    CompatibilityRule,
    ContinuityAction,
    DependencyEdge,
    DependencyGraph,
    DriftClassification,
    FenceToken,
    RecallEngine,
    RecallSignal,
    RecoveryCheckpoint,
    RecoveryEngine,
    ResourceRevision,
    RuleBasedSemanticComparator,
    StateRegistry,
    Validity,
)


def revision(resource: str, version: str) -> ResourceRevision:
    return ResourceRevision(resource_id=resource, revision=version, digest=f"sha256:{version}")


def checkpoint_with_fence() -> tuple[StateRegistry, RecoveryCheckpoint]:
    registry = StateRegistry()
    head = revision("repo://acme/app", "1")
    registry.register(head)
    snapshot = registry.snapshot(["repo://acme/app"])
    checkpoint = RecoveryCheckpoint.build(
        snapshot=snapshot,
        fences=(FenceToken("repo://acme/app", 2),),
    )
    return registry, checkpoint


def test_exact_checkpoint_and_current_fence_can_recover() -> None:
    registry, checkpoint = checkpoint_with_fence()

    decision = RecoveryEngine().validate(
        checkpoint,
        current_heads=registry.heads(),
        current_fences={"repo://acme/app": 2},
    )

    assert decision.action is ContinuityAction.RECOVER
    assert "RECOVERY_VALIDATED" in decision.reason_codes


def test_read_only_compatible_semantic_drift_can_recover() -> None:
    registry = StateRegistry()
    registry.register(revision("tool://github/create-pr", "1"))
    snapshot = registry.snapshot(["tool://github/create-pr"])
    checkpoint = RecoveryCheckpoint.build(snapshot=snapshot)
    registry.register(revision("tool://github/create-pr", "2"))
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

    decision = RecoveryEngine().validate(
        checkpoint,
        current_heads=registry.heads(),
        semantic_comparator=comparator,
    )

    assert decision.action is ContinuityAction.RECOVER


def test_changed_write_head_requires_revalidation_even_if_semantically_compatible() -> None:
    registry, checkpoint = checkpoint_with_fence()
    registry.register(revision("repo://acme/app", "2"))
    comparator = RuleBasedSemanticComparator(
        rules=(
            CompatibilityRule(
                resource_id="repo://acme/app",
                from_revision="1",
                to_revision="2",
                classification=DriftClassification.COMPATIBLE,
            ),
        )
    )

    decision = RecoveryEngine().validate(
        checkpoint,
        current_heads=registry.heads(),
        current_fences={"repo://acme/app": 2},
        semantic_comparator=comparator,
    )

    assert decision.action is ContinuityAction.REVALIDATE
    assert "HEAD_CONFLICT:repo://acme/app" in decision.reason_codes


def test_stale_checkpoint_fence_aborts() -> None:
    registry, checkpoint = checkpoint_with_fence()

    decision = RecoveryEngine().validate(
        checkpoint,
        current_heads=registry.heads(),
        current_fences={"repo://acme/app": 3},
    )

    assert decision.action is ContinuityAction.ABORT
    assert "STALE_FENCE:repo://acme/app" in decision.reason_codes


def test_unknown_current_fence_pauses() -> None:
    registry, checkpoint = checkpoint_with_fence()

    decision = RecoveryEngine().validate(
        checkpoint,
        current_heads=registry.heads(),
        current_fences={},
    )

    assert decision.action is ContinuityAction.PAUSE
    assert "UNKNOWN_CURRENT_FENCE:repo://acme/app" in decision.reason_codes


def test_invalid_dependency_aborts_recovery() -> None:
    registry = StateRegistry()
    registry.register(revision("policy://deploy", "1"))
    snapshot = registry.snapshot(["policy://deploy"])
    checkpoint = RecoveryCheckpoint.build(snapshot=snapshot)

    decision = RecoveryEngine().validate(
        checkpoint,
        current_heads=registry.heads(),
        validity={"policy://deploy": Validity.INVALID},
    )

    assert decision.action is ContinuityAction.ABORT


def test_unknown_dependency_pauses_recovery() -> None:
    registry = StateRegistry()
    registry.register(revision("policy://deploy", "1"))
    snapshot = registry.snapshot(["policy://deploy"])
    checkpoint = RecoveryCheckpoint.build(snapshot=snapshot)

    decision = RecoveryEngine().validate(
        checkpoint,
        current_heads=registry.heads(),
        validity={"policy://deploy": Validity.UNKNOWN},
    )

    assert decision.action is ContinuityAction.PAUSE


def test_recall_staleness_requires_revalidation_before_recovery() -> None:
    registry = StateRegistry()
    source = revision("source://pricing", "1")
    quote = revision("artifact://quote", "1")
    registry.register(source)
    registry.register(quote)
    snapshot = registry.snapshot(["source://pricing", "artifact://quote"])
    checkpoint = RecoveryCheckpoint.build(snapshot=snapshot)

    recall = RecallEngine().evaluate(
        DependencyGraph(
            edges=(DependencyEdge("source://pricing", "artifact://quote"),),
        ),
        {"source://pricing": RecallSignal.CHANGED},
    )

    decision = RecoveryEngine().validate(
        checkpoint,
        current_heads=registry.heads(),
        validity=recall.validity_map(),
    )

    assert decision.action is ContinuityAction.REVALIDATE
    assert "STALE_RESOURCE:artifact://quote" in decision.reason_codes


def test_recovery_witness_is_reproducible() -> None:
    registry, checkpoint = checkpoint_with_fence()
    engine = RecoveryEngine()

    first = engine.validate(
        checkpoint,
        current_heads=registry.heads(),
        current_fences={"repo://acme/app": 2},
    )
    second = engine.validate(
        checkpoint,
        current_heads=registry.heads(),
        current_fences={"repo://acme/app": 2},
    )

    assert first.witness == second.witness


def test_checkpoint_fence_must_reference_snapshot_resource() -> None:
    registry = StateRegistry()
    registry.register(revision("repo://acme/app", "1"))
    snapshot = registry.snapshot(["repo://acme/app"])

    with pytest.raises(ValueError):
        RecoveryCheckpoint.build(
            snapshot=snapshot,
            fences=(FenceToken("repo://acme/other", 1),),
        )


def test_checkpoint_rejects_duplicate_fences() -> None:
    registry = StateRegistry()
    registry.register(revision("repo://acme/app", "1"))
    snapshot = registry.snapshot(["repo://acme/app"])

    with pytest.raises(ValueError):
        RecoveryCheckpoint.build(
            snapshot=snapshot,
            fences=(
                FenceToken("repo://acme/app", 1),
                FenceToken("repo://acme/app", 2),
            ),
        )

from howedo import (
    ContinuityAction,
    DecisionEngine,
    DependencyEdge,
    DependencyGraph,
    RecallEngine,
    RecallSignal,
    ResourceRevision,
    StateRegistry,
    Validity,
)


def revision(resource: str, version: str) -> ResourceRevision:
    return ResourceRevision(resource_id=resource, revision=version, digest=f"sha256:{version}")


def graph() -> DependencyGraph:
    return DependencyGraph(
        edges=(
            DependencyEdge("source://pricing", "claim://price"),
            DependencyEdge("claim://price", "plan://quote"),
        )
    )


def test_changed_source_marks_transitive_dependents_stale() -> None:
    result = RecallEngine().evaluate(
        graph(),
        {"source://pricing": RecallSignal.CHANGED},
    )

    validity = result.validity_map()
    assert "source://pricing" not in validity
    assert validity["claim://price"] is Validity.STALE
    assert validity["plan://quote"] is Validity.STALE


def test_invalid_source_invalidates_transitive_dependents() -> None:
    result = RecallEngine().evaluate(
        graph(),
        {"source://pricing": RecallSignal.INVALID},
    )

    validity = result.validity_map()
    assert validity["source://pricing"] is Validity.INVALID
    assert validity["claim://price"] is Validity.INVALID
    assert validity["plan://quote"] is Validity.INVALID


def test_unknown_source_propagates_unknown() -> None:
    result = RecallEngine().evaluate(
        graph(),
        {"source://pricing": RecallSignal.UNKNOWN},
    )

    validity = result.validity_map()
    assert validity["source://pricing"] is Validity.UNKNOWN
    assert validity["claim://price"] is Validity.UNKNOWN
    assert validity["plan://quote"] is Validity.UNKNOWN


def test_cycles_do_not_loop_or_mark_changed_root_stale() -> None:
    cyclic = DependencyGraph(
        edges=(
            DependencyEdge("source://a", "claim://b"),
            DependencyEdge("claim://b", "source://a"),
        )
    )

    result = RecallEngine().evaluate(cyclic, {"source://a": RecallSignal.CHANGED})

    validity = result.validity_map()
    assert "source://a" not in validity
    assert validity["claim://b"] is Validity.STALE


def test_multiple_causes_merge_to_safest_validity() -> None:
    shared = DependencyGraph(
        edges=(
            DependencyEdge("source://a", "claim://x"),
            DependencyEdge("source://b", "claim://x"),
        )
    )

    result = RecallEngine().evaluate(
        shared,
        {
            "source://a": RecallSignal.CHANGED,
            "source://b": RecallSignal.UNKNOWN,
        },
    )

    impact = result.by_resource()["claim://x"]
    assert impact.validity is Validity.UNKNOWN
    assert impact.causes == ("SOURCE_CHANGED:source://a", "SOURCE_UNKNOWN:source://b")


def test_recall_validity_drives_continuity_decision() -> None:
    registry = StateRegistry()
    registry.register(revision("claim://price", "1"))
    registry.register(revision("plan://quote", "1"))
    snapshot = registry.snapshot(["claim://price", "plan://quote"])

    recall = RecallEngine().evaluate(
        DependencyGraph(edges=(DependencyEdge("claim://price", "plan://quote"),)),
        {"claim://price": RecallSignal.INVALID},
    )

    decision = DecisionEngine().check(
        snapshot,
        current_heads=registry.heads(),
        validity=recall.validity_map(),
    )

    assert decision.action is ContinuityAction.ABORT
    assert "INVALID_RESOURCE:plan://quote" in decision.reason_codes


def test_unknown_blocks_stale_revalidation() -> None:
    registry = StateRegistry()
    registry.register(revision("resource://unknown", "1"))
    registry.register(revision("resource://stale", "1"))
    snapshot = registry.snapshot(["resource://unknown", "resource://stale"])

    decision = DecisionEngine().check(
        snapshot,
        current_heads=registry.heads(),
        validity={
            "resource://unknown": Validity.UNKNOWN,
            "resource://stale": Validity.STALE,
        },
    )

    assert decision.action is ContinuityAction.PAUSE

import pytest

from howedo import ContinuityAction, DecisionEngine, ResourceRevision, StateRegistry, Validity
from howedo.domain import ContinuitySnapshot
from howedo.kernel import RevisionConflict


def revision(resource: str, version: str, digest: str | None = None) -> ResourceRevision:
    return ResourceRevision(resource_id=resource, revision=version, digest=digest or version)


def test_revision_identity_is_immutable() -> None:
    registry = StateRegistry()
    registry.register(revision("repo://acme/app", "git:abc", "sha256:one"))

    with pytest.raises(RevisionConflict):
        registry.register(revision("repo://acme/app", "git:abc", "sha256:two"))


def test_resource_revision_fields_must_be_non_empty() -> None:
    with pytest.raises(ValueError, match="resource_id"):
        ResourceRevision(resource_id="", revision="1", digest="sha256:one")
    with pytest.raises(ValueError, match="revision"):
        ResourceRevision(resource_id="repo://acme/app", revision="", digest="sha256:one")
    with pytest.raises(ValueError, match="digest"):
        ResourceRevision(resource_id="repo://acme/app", revision="1", digest="")


def test_snapshot_rejects_duplicate_resource_identity() -> None:
    with pytest.raises(ValueError, match="resource ids must be unique"):
        ContinuitySnapshot.build(
            (
                revision("repo://acme/app", "git:abc", "sha256:one"),
                revision("repo://acme/app", "git:def", "sha256:two"),
            )
        )


def test_exact_snapshot_can_continue() -> None:
    registry = StateRegistry()
    registry.register(revision("repo://acme/app", "git:abc"))
    snapshot = registry.snapshot(["repo://acme/app"])

    decision = DecisionEngine().check(snapshot, current_heads=registry.heads())

    assert decision.action is ContinuityAction.CONTINUE
    assert decision.reason_codes == ()


def test_changed_authoritative_head_requires_revalidation() -> None:
    registry = StateRegistry()
    registry.register(revision("repo://acme/app", "git:abc"))
    snapshot = registry.snapshot(["repo://acme/app"])
    registry.register(revision("repo://acme/app", "git:def"))

    decision = DecisionEngine().check(snapshot, current_heads=registry.heads())

    assert decision.action is ContinuityAction.REVALIDATE
    assert "RESOURCE_HEAD_CHANGED:repo://acme/app" in decision.reason_codes


def test_unknown_is_never_promoted_to_valid() -> None:
    registry = StateRegistry()
    registry.register(revision("policy://deploy", "19"))
    snapshot = registry.snapshot(["policy://deploy"])

    decision = DecisionEngine().check(snapshot, current_heads={})

    assert decision.action is ContinuityAction.PAUSE


def test_invalid_dependency_aborts() -> None:
    registry = StateRegistry()
    registry.register(revision("schema://tool/github", "4"))
    snapshot = registry.snapshot(["schema://tool/github"])

    decision = DecisionEngine().check(
        snapshot,
        current_heads=registry.heads(),
        validity={"schema://tool/github": Validity.INVALID},
    )

    assert decision.action is ContinuityAction.ABORT


def test_superseded_dependency_requires_revalidation() -> None:
    registry = StateRegistry()
    registry.register(revision("schema://tool/github", "4"))
    snapshot = registry.snapshot(["schema://tool/github"])

    decision = DecisionEngine().check(
        snapshot,
        current_heads=registry.heads(),
        validity={"schema://tool/github": Validity.SUPERSEDED},
    )

    assert decision.action is ContinuityAction.REVALIDATE
    assert decision.reason_codes == ("SUPERSEDED_RESOURCE:schema://tool/github",)


def test_recovery_requires_current_snapshot_to_still_be_valid() -> None:
    registry = StateRegistry()
    registry.register(revision("data://pricing", "7"))
    snapshot = registry.snapshot(["data://pricing"])
    registry.register(revision("data://pricing", "8"))

    decision = DecisionEngine().check(
        snapshot,
        current_heads=registry.heads(),
        recovery_requested=True,
    )

    assert decision.action is ContinuityAction.REVALIDATE


def test_witness_is_reproducible() -> None:
    registry = StateRegistry()
    registry.register(revision("repo://acme/app", "git:abc"))
    snapshot = registry.snapshot(["repo://acme/app"])
    engine = DecisionEngine()

    first = engine.check(snapshot, current_heads=registry.heads())
    second = engine.check(snapshot, current_heads=registry.heads())

    assert first.witness == second.witness

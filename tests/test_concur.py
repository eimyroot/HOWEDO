import pytest

from howedo import (
    ConcurEngine,
    ContinuityAction,
    FenceRegistry,
    FenceToken,
    HeadConflict,
    ResourceRevision,
    StateRegistry,
    WriteIntent,
)


def revision(resource: str, version: str) -> ResourceRevision:
    return ResourceRevision(resource_id=resource, revision=version, digest=f"sha256:{version}")


def test_fence_tokens_are_monotonic_per_resource() -> None:
    fences = FenceRegistry()

    first = fences.issue("repo://acme/app")
    second = fences.issue("repo://acme/app")
    other = fences.issue("repo://acme/other")

    assert first.value == 1
    assert second.value == 2
    assert other.value == 1


def test_current_fence_zero_before_first_issue() -> None:
    assert FenceRegistry().current("repo://acme/app") == 0


def test_matching_head_and_fence_can_continue() -> None:
    head = revision("repo://acme/app", "1")
    fence = FenceToken("repo://acme/app", 2)
    intent = WriteIntent(expected_head=head, fence=fence)

    decision = ConcurEngine().check(intent, current_head=head, current_fence=2)

    assert decision.action is ContinuityAction.CONTINUE
    assert decision.reason_codes == ()


def test_stale_writer_is_rejected_even_if_head_did_not_change() -> None:
    head = revision("repo://acme/app", "1")
    intent = WriteIntent(
        expected_head=head,
        fence=FenceToken("repo://acme/app", 1),
    )

    decision = ConcurEngine().check(intent, current_head=head, current_fence=2)

    assert decision.action is ContinuityAction.ABORT
    assert "STALE_FENCE:repo://acme/app" in decision.reason_codes


def test_future_fence_pauses() -> None:
    head = revision("repo://acme/app", "1")
    intent = WriteIntent(
        expected_head=head,
        fence=FenceToken("repo://acme/app", 3),
    )

    decision = ConcurEngine().check(intent, current_head=head, current_fence=2)

    assert decision.action is ContinuityAction.PAUSE


def test_head_conflict_requires_revalidation() -> None:
    expected = revision("repo://acme/app", "1")
    current = revision("repo://acme/app", "2")
    intent = WriteIntent(
        expected_head=expected,
        fence=FenceToken("repo://acme/app", 2),
    )

    decision = ConcurEngine().check(intent, current_head=current, current_fence=2)

    assert decision.action is ContinuityAction.REVALIDATE
    assert "HEAD_CONFLICT:repo://acme/app" in decision.reason_codes


def test_stale_fence_outranks_head_conflict() -> None:
    expected = revision("repo://acme/app", "1")
    current = revision("repo://acme/app", "2")
    intent = WriteIntent(
        expected_head=expected,
        fence=FenceToken("repo://acme/app", 1),
    )

    decision = ConcurEngine().check(intent, current_head=current, current_fence=2)

    assert decision.action is ContinuityAction.ABORT


def test_reference_head_activation_accepts_exact_expected_head() -> None:
    registry = StateRegistry()
    first = revision("repo://acme/app", "1")
    second = revision("repo://acme/app", "2")
    registry.register(first)

    registry.activate_if_head(expected=first, replacement=second)

    assert registry.head("repo://acme/app") == second


def test_reference_head_activation_rejects_stale_expected_head() -> None:
    registry = StateRegistry()
    first = revision("repo://acme/app", "1")
    second = revision("repo://acme/app", "2")
    third = revision("repo://acme/app", "3")
    registry.register(first)
    registry.register(second)

    with pytest.raises(HeadConflict):
        registry.activate_if_head(expected=first, replacement=third)


def test_write_intent_requires_matching_resource() -> None:
    with pytest.raises(ValueError):
        WriteIntent(
            expected_head=revision("repo://acme/app", "1"),
            fence=FenceToken("repo://acme/other", 1),
        )

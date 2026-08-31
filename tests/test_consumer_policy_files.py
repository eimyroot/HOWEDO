from __future__ import annotations

import json
from pathlib import Path

from howedo.consumer_trust import ConsumerTrustProfile


def _load(path: str) -> ConsumerTrustProfile:
    record = json.loads(Path(path).read_text())
    return ConsumerTrustProfile.from_record(record)


def test_production_consumer_profile_is_main_only_and_pins_r11_policy() -> None:
    profile = _load("policies/reference/github-actions-consumer-trust-v1.json")
    assert profile.allowed_ref_patterns == ("refs/heads/main",)
    assert profile.allowed_identity_patterns == (
        (
            "https://github.com/eimyroot/HOWEDO/.github/workflows/"
            "consolidation.yml@refs/heads/main"
        ),
    )
    assert profile.allowed_repositories == ("eimyroot/HOWEDO",)
    assert profile.allowed_triggers == ("push", "workflow_dispatch")
    assert profile.expected_workflow_name == "Conformance Matrix"
    assert profile.trusted_policies[0].policy_digest == (
        "sha256:5a757c5ed7de3f78adc5fcc7127a254342246d0ebcaeaff14dfe6c4c6dc9432f"
    )


def test_pr_consumer_profile_is_test_only_and_pins_pr_policy() -> None:
    profile = _load("policies/test/github-actions-pr-consumer-trust-v1.json")
    assert profile.allowed_ref_patterns == ("refs/pull/*/merge",)
    assert profile.allowed_identity_patterns == (
        (
            "https://github.com/eimyroot/HOWEDO/.github/workflows/"
            "consolidation.yml@refs/pull/*/merge"
        ),
    )
    assert profile.allowed_repositories == ("eimyroot/HOWEDO",)
    assert profile.allowed_triggers == ("pull_request",)
    assert profile.expected_workflow_name == "Conformance Matrix"
    assert profile.trusted_policies[0].policy_digest == (
        "sha256:34e39721b8684e09dcdb9db969a90c3cb0f1a5ab6425641e967ec9ea5139760e"
    )

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
            "https://github.com/nulleimy/HOWEDO/.github/workflows/"
            "consolidation.yml@refs/heads/main"
        ),
    )
    assert profile.allowed_triggers == ("push", "workflow_dispatch")
    assert profile.trusted_policies[0].policy_digest == (
        "sha256:df956d0249936667287b42534030ec0594c9e84aad36f348f48614c2cee0e9d7"
    )


def test_pr_consumer_profile_is_test_only_and_pins_pr_policy() -> None:
    profile = _load("policies/test/github-actions-pr-consumer-trust-v1.json")
    assert profile.allowed_ref_patterns == ("refs/pull/*/merge",)
    assert profile.allowed_triggers == ("pull_request",)
    assert profile.trusted_policies[0].policy_digest == (
        "sha256:93733519d6afa8911208abd99c0b1dea0b8e8df01e7892a930b12390af15e5ac"
    )

from __future__ import annotations

from json import loads
from pathlib import Path

from howedo.trust_policy import AttestationTrustPolicy

POLICIES = (
    Path("policies/reference/github-actions-conformance-trust-v1.json"),
    Path("policies/test/github-actions-pr-conformance-trust-v1.json"),
)


def test_shipped_trust_policies_are_content_addressed() -> None:
    for path in POLICIES:
        record = loads(path.read_text())
        policy = AttestationTrustPolicy.from_record(record)
        assert policy.record() == record

from __future__ import annotations

from copy import deepcopy

import pytest

from howedo.adapter_certification import (
    CONFORMANCE_CHECKS_V1,
    ConformanceArtifact,
    ConformanceEnvironment,
)
from howedo.adapter_conformance import ConformanceResult
from howedo.adapter_contract import AdapterCapability, AdapterManifest
from howedo.attestation import build_conformance_statement
from howedo.consumer_trust import (
    ConsumerTrustProfile,
    ConsumerTrustReason,
    TrustedPolicyRef,
    evaluate_consumer_expectations,
)
from howedo.trust_policy import (
    AttestationTrustPolicy,
    SignerVerificationContext,
    build_svr_statement,
    evaluate_attestation_trust,
)

CHECKOUT_SHA = "a" * 40
POLICY_ID = "https://example.test/policies/conformance-v1"
SVR_VERIFIER_ID = "https://github.com/nulleimy/HOWEDO/verifiers/attestation-trust/v1"


def artifact_record() -> dict:
    manifest = AdapterManifest.build(
        adapter_id="test.fake",
        runtime_family="fake",
        adapter_version="1",
        capabilities=(
            AdapterCapability.EXACT_RUNTIME_IDENTITY,
            AdapterCapability.CAPTURE,
            AdapterCapability.VALIDATE_RESUME,
            AdapterCapability.CONTINUE,
        ),
    )
    checks = tuple(
        ConformanceResult(check=name, passed=True, detail="ok")
        for name in CONFORMANCE_CHECKS_V1
    )
    artifact = ConformanceArtifact(
        manifest=manifest,
        checks=checks,
        environment=ConformanceEnvironment(
            python_version="3.12.0",
            python_implementation="CPython",
            platform="linux",
        ),
        evidence_refs=(f"git-checkout://sha/{CHECKOUT_SHA}",),
    )
    return artifact.record()


def policy() -> AttestationTrustPolicy:
    return AttestationTrustPolicy(
        policy_id=POLICY_ID,
        allowed_verifiers=("sigstore-cosign",),
        allowed_issuers=("https://token.actions.githubusercontent.com",),
        allowed_identity_patterns=(
            (
                "https://github.com/nulleimy/HOWEDO/.github/workflows/"
                "consolidation.yml@refs/heads/main"
            ),
        ),
        allowed_repositories=("nulleimy/HOWEDO",),
        allowed_workflows=(".github/workflows/consolidation.yml",),
        allowed_ref_patterns=("refs/heads/main",),
        allowed_triggers=("push",),
        allowed_predicate_types=(
            "https://github.com/nulleimy/HOWEDO/attestations/adapter-conformance/v1",
        ),
        allowed_artifact_versions=("howedo.adapter-conformance-artifact.v1",),
        require_conformant_status=True,
        require_transparency_log=True,
        require_execution_sha_matches_artifact_checkout=True,
    )


def signer(**overrides: object) -> SignerVerificationContext:
    values: dict[str, object] = {
        "verifier_id": "sigstore-cosign",
        "cryptographically_verified": True,
        "issuer": "https://token.actions.githubusercontent.com",
        "identity": (
            "https://github.com/nulleimy/HOWEDO/.github/workflows/"
            "consolidation.yml@refs/heads/main"
        ),
        "repository": "nulleimy/HOWEDO",
        "workflow": ".github/workflows/consolidation.yml",
        "execution_sha": CHECKOUT_SHA,
        "execution_ref": "refs/heads/main",
        "trigger": "push",
        "transparency_log_verified": True,
        "evidence_refs": ("github-actions://run/test", "sigstore://bundle/test"),
    }
    values.update(overrides)
    return SignerVerificationContext(**values)  # type: ignore[arg-type]


def profile(current_policy: AttestationTrustPolicy | None = None) -> ConsumerTrustProfile:
    current_policy = current_policy or policy()
    return ConsumerTrustProfile(
        profile_id="https://example.test/consumer-profile-v1",
        trusted_svr_verifier_ids=(SVR_VERIFIER_ID,),
        trusted_policies=(
            TrustedPolicyRef(
                policy_id=current_policy.policy_id,
                policy_digest=current_policy.digest(),
            ),
        ),
        allowed_crypto_verifiers=("sigstore-cosign",),
        allowed_issuers=("https://token.actions.githubusercontent.com",),
        allowed_identity_patterns=(
            (
                "https://github.com/nulleimy/HOWEDO/.github/workflows/"
                "consolidation.yml@refs/heads/main"
            ),
        ),
        allowed_repositories=("nulleimy/HOWEDO",),
        allowed_workflows=(".github/workflows/consolidation.yml",),
        allowed_ref_patterns=("refs/heads/main",),
        allowed_triggers=("push",),
        require_transparency_log=True,
    )


def svr() -> dict:
    artifact = artifact_record()
    statement = build_conformance_statement(artifact)
    current_policy = policy()
    current_signer = signer()
    evaluation = evaluate_attestation_trust(
        current_policy,
        artifact,
        statement,
        current_signer,
    )
    return build_svr_statement(
        current_policy,
        artifact,
        evaluation,
        time_created="2026-08-17T00:00:00Z",
    )


def test_accepts_consumer_pinned_policy_verifier_and_signer() -> None:
    current_policy = policy()
    evaluation = evaluate_consumer_expectations(
        profile(current_policy),
        current_policy,
        svr(),
        signer(),
    )
    assert evaluation.accepted
    assert evaluation.reason_codes == ()


def test_rejects_untrusted_policy_and_identity() -> None:
    current_policy = policy()
    untrusted_profile = ConsumerTrustProfile(
        profile_id="https://example.test/consumer-profile-v1",
        trusted_svr_verifier_ids=(SVR_VERIFIER_ID,),
        trusted_policies=(
            TrustedPolicyRef(
                policy_id="https://example.test/other-policy",
                policy_digest="sha256:" + "b" * 64,
            ),
        ),
        allowed_crypto_verifiers=("sigstore-cosign",),
        allowed_issuers=("https://token.actions.githubusercontent.com",),
        allowed_identity_patterns=("https://github.com/nulleimy/HOWEDO/allowed",),
        allowed_repositories=("nulleimy/HOWEDO",),
        allowed_workflows=(".github/workflows/consolidation.yml",),
        allowed_ref_patterns=("refs/heads/main",),
        allowed_triggers=("push",),
        require_transparency_log=True,
    )
    evaluation = evaluate_consumer_expectations(
        untrusted_profile,
        current_policy,
        svr(),
        signer(),
    )
    assert not evaluation.accepted
    assert ConsumerTrustReason.POLICY_NOT_TRUSTED in evaluation.reason_codes
    assert ConsumerTrustReason.IDENTITY_NOT_ALLOWED in evaluation.reason_codes


def test_profile_record_is_content_addressed() -> None:
    current = profile()
    record = current.record()
    loaded = ConsumerTrustProfile.from_record(record)
    assert loaded.digest() == record["profile_digest"]

    tampered = deepcopy(record)
    tampered["allowed_triggers"] = ["workflow_dispatch"]
    with pytest.raises(ValueError, match="digest mismatch"):
        ConsumerTrustProfile.from_record(tampered)


def test_segment_glob_does_not_cross_path_segments() -> None:
    current_policy = policy()
    wildcard_profile = ConsumerTrustProfile(
        profile_id="https://example.test/consumer-profile-v1",
        trusted_svr_verifier_ids=(SVR_VERIFIER_ID,),
        trusted_policies=(
            TrustedPolicyRef(
                policy_id=current_policy.policy_id,
                policy_digest=current_policy.digest(),
            ),
        ),
        allowed_crypto_verifiers=("sigstore-cosign",),
        allowed_issuers=("https://token.actions.githubusercontent.com",),
        allowed_identity_patterns=(
            (
                "https://github.com/nulleimy/HOWEDO/.github/workflows/"
                "consolidation.yml@refs/pull/*/merge"
            ),
        ),
        allowed_repositories=("nulleimy/HOWEDO",),
        allowed_workflows=(".github/workflows/consolidation.yml",),
        allowed_ref_patterns=("refs/pull/*/merge",),
        allowed_triggers=("push",),
        require_transparency_log=True,
    )
    bad = signer(
        identity=(
            "https://github.com/nulleimy/HOWEDO/.github/workflows/"
            "consolidation.yml@refs/pull/14/extra/merge"
        ),
        execution_ref="refs/pull/14/extra/merge",
    )
    evaluation = evaluate_consumer_expectations(
        wildcard_profile,
        current_policy,
        svr(),
        bad,
    )
    assert ConsumerTrustReason.IDENTITY_NOT_ALLOWED in evaluation.reason_codes
    assert ConsumerTrustReason.REF_NOT_ALLOWED in evaluation.reason_codes

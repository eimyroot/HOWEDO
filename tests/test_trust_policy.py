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
from howedo.trust_policy import (
    AttestationTrustPolicy,
    SignerVerificationContext,
    SVR_PREDICATE_V02,
    TRUST_ACCEPTED_PROPERTY,
    TrustDecision,
    TrustReasonCode,
    build_svr_statement,
    evaluate_attestation_trust,
    verify_svr_statement,
)

CHECKOUT_SHA = "a" * 40


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
        evidence_refs=(
            f"git-checkout://sha/{CHECKOUT_SHA}",
            "git-source://sha/source",
        ),
    )
    return artifact.record()


def policy() -> AttestationTrustPolicy:
    return AttestationTrustPolicy(
        policy_id="https://example.test/policies/conformance-v1",
        allowed_verifiers=("sigstore-cosign",),
        allowed_issuers=("https://token.actions.githubusercontent.com",),
        allowed_identity_patterns=(
            "https://github.com/nulleimy/HOWEDO/.github/workflows/consolidation.yml@refs/pull/*/merge",
        ),
        allowed_repositories=("nulleimy/HOWEDO",),
        allowed_workflows=(".github/workflows/consolidation.yml",),
        allowed_ref_patterns=("refs/pull/*/merge",),
        allowed_triggers=("pull_request",),
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
            "consolidation.yml@refs/pull/14/merge"
        ),
        "repository": "nulleimy/HOWEDO",
        "workflow": ".github/workflows/consolidation.yml",
        "execution_sha": CHECKOUT_SHA,
        "execution_ref": "refs/pull/14/merge",
        "trigger": "pull_request",
        "transparency_log_verified": True,
        "evidence_refs": ("sigstore://bundle/test",),
    }
    values.update(overrides)
    return SignerVerificationContext(**values)  # type: ignore[arg-type]


def test_accepts_exact_verified_signer_and_artifact_binding() -> None:
    artifact = artifact_record()
    statement = build_conformance_statement(artifact)

    evaluation = evaluate_attestation_trust(policy(), artifact, statement, signer())

    assert evaluation.decision is TrustDecision.ACCEPT
    assert evaluation.reason_codes == ()


def test_rejects_failed_crypto_and_wrong_issuer() -> None:
    artifact = artifact_record()
    statement = build_conformance_statement(artifact)
    context = signer(
        cryptographically_verified=False,
        issuer="https://issuer.example.invalid",
        transparency_log_verified=False,
    )

    evaluation = evaluate_attestation_trust(policy(), artifact, statement, context)

    assert evaluation.decision is TrustDecision.REJECT
    assert TrustReasonCode.CRYPTOGRAPHIC_VERIFICATION_FAILED in evaluation.reason_codes
    assert TrustReasonCode.ISSUER_NOT_ALLOWED in evaluation.reason_codes
    assert TrustReasonCode.TRANSPARENCY_REQUIRED in evaluation.reason_codes


def test_segment_glob_does_not_cross_path_segments() -> None:
    artifact = artifact_record()
    statement = build_conformance_statement(artifact)
    context = signer(
        identity=(
            "https://github.com/nulleimy/HOWEDO/.github/workflows/"
            "consolidation.yml@refs/pull/14/extra/merge"
        ),
        execution_ref="refs/pull/14/extra/merge",
    )

    evaluation = evaluate_attestation_trust(policy(), artifact, statement, context)

    assert TrustReasonCode.IDENTITY_NOT_ALLOWED in evaluation.reason_codes
    assert TrustReasonCode.REF_NOT_ALLOWED in evaluation.reason_codes


def test_rejects_execution_sha_that_does_not_match_r9_checkout() -> None:
    artifact = artifact_record()
    statement = build_conformance_statement(artifact)

    evaluation = evaluate_attestation_trust(
        policy(),
        artifact,
        statement,
        signer(execution_sha="b" * 40),
    )

    assert TrustReasonCode.EXECUTION_SHA_MISMATCH in evaluation.reason_codes


def test_policy_record_is_content_addressed() -> None:
    record = policy().record()
    loaded = AttestationTrustPolicy.from_record(record)
    assert loaded.digest() == record["policy_digest"]

    tampered = deepcopy(record)
    tampered["allowed_triggers"] = ["push"]
    with pytest.raises(ValueError, match="digest mismatch"):
        AttestationTrustPolicy.from_record(tampered)


def test_emits_in_toto_svr_v02_bound_to_policy() -> None:
    artifact = artifact_record()
    statement = build_conformance_statement(artifact)
    current_policy = policy()
    context = signer()
    evaluation = evaluate_attestation_trust(current_policy, artifact, statement, context)

    svr = build_svr_statement(
        current_policy,
        artifact,
        evaluation,
        time_created="2026-08-17T00:00:00Z",
    )

    assert svr["predicateType"] == SVR_PREDICATE_V02
    assert TRUST_ACCEPTED_PROPERTY in svr["predicate"]["properties"]
    assert svr["predicate"]["verifier"]["policies"] == [
        {
            "uri": current_policy.policy_id,
            "digest": {"sha256": current_policy.digest().removeprefix("sha256:")},
        }
    ]
    assert verify_svr_statement(current_policy, artifact, statement, context, svr)


def test_svr_replay_detects_decision_tampering() -> None:
    artifact = artifact_record()
    statement = build_conformance_statement(artifact)
    current_policy = policy()
    context = signer()
    evaluation = evaluate_attestation_trust(current_policy, artifact, statement, context)
    svr = build_svr_statement(
        current_policy,
        artifact,
        evaluation,
        time_created="2026-08-17T00:00:00Z",
    )
    svr["predicate"]["properties"] = ["HOWEDO_ATTESTATION_TRUST_REJECTED"]

    assert not verify_svr_statement(current_policy, artifact, statement, context, svr)

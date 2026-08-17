from __future__ import annotations

import json
from pathlib import Path

from howedo.adapter_certification import (
    CONFORMANCE_CHECKS_V1,
    ConformanceArtifact,
    ConformanceEnvironment,
)
from howedo.adapter_conformance import ConformanceResult
from howedo.adapter_contract import AdapterCapability, AdapterManifest
from howedo.attestation import build_conformance_statement
from howedo.certification_package import (
    CertificationDecision,
    CertificationReasonCode,
    CertificationSigner,
    build_certification_package,
    load_certification_package_manifest,
    verify_certification_package,
)
from howedo.consumer_trust import ConsumerTrustProfile, TrustedPolicyRef
from howedo.sigstore_trust import SigstoreVerificationResult
from howedo.trust_policy import (
    AttestationTrustPolicy,
    SignerVerificationContext,
    build_svr_statement,
    evaluate_attestation_trust,
)

CHECKOUT_SHA = "a" * 40
EVIDENCE_REFS = ("github-actions://run/test", "sigstore://bundle/test")


def _artifact() -> dict:
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
    return ConformanceArtifact(
        manifest=manifest,
        checks=checks,
        environment=ConformanceEnvironment(
            python_version="3.12.0",
            python_implementation="CPython",
            platform="linux",
        ),
        evidence_refs=(f"git-checkout://sha/{CHECKOUT_SHA}",),
    ).record()


def _policy() -> AttestationTrustPolicy:
    return AttestationTrustPolicy(
        policy_id="https://example.test/policies/conformance-v1",
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


def _signer_context() -> SignerVerificationContext:
    return SignerVerificationContext(
        verifier_id="sigstore-cosign",
        cryptographically_verified=True,
        issuer="https://token.actions.githubusercontent.com",
        identity=(
            "https://github.com/nulleimy/HOWEDO/.github/workflows/"
            "consolidation.yml@refs/heads/main"
        ),
        repository="nulleimy/HOWEDO",
        workflow=".github/workflows/consolidation.yml",
        execution_sha=CHECKOUT_SHA,
        execution_ref="refs/heads/main",
        trigger="push",
        transparency_log_verified=True,
        evidence_refs=EVIDENCE_REFS,
    )


def _package_signer() -> CertificationSigner:
    context = _signer_context()
    return CertificationSigner(
        issuer=context.issuer,
        identity=context.identity,
        repository=context.repository,
        workflow=context.workflow,
        execution_sha=context.execution_sha,
        execution_ref=context.execution_ref,
        trigger=context.trigger,
        evidence_refs=context.evidence_refs,
    )


def _profile(current_policy: AttestationTrustPolicy) -> ConsumerTrustProfile:
    return ConsumerTrustProfile(
        profile_id="https://example.test/consumer-profile-v1",
        trusted_svr_verifier_ids=(
            "https://github.com/nulleimy/HOWEDO/verifiers/attestation-trust/v1",
        ),
        trusted_policies=(
            TrustedPolicyRef(
                policy_id=current_policy.policy_id,
                policy_digest=current_policy.digest(),
            ),
        ),
        allowed_crypto_verifiers=("sigstore-cosign",),
        allowed_issuers=("https://token.actions.githubusercontent.com",),
        allowed_identity_patterns=(_package_signer().identity,),
        allowed_repositories=("nulleimy/HOWEDO",),
        allowed_workflows=(".github/workflows/consolidation.yml",),
        allowed_ref_patterns=("refs/heads/main",),
        allowed_triggers=("push",),
        require_transparency_log=True,
    )


def _write_source_files(root: Path) -> dict[str, Path]:
    artifact = _artifact()
    statement = build_conformance_statement(artifact)
    current_policy = _policy()
    signer = _signer_context()
    evaluation = evaluate_attestation_trust(current_policy, artifact, statement, signer)
    svr = build_svr_statement(
        current_policy,
        artifact,
        evaluation,
        time_created="2026-08-17T00:00:00Z",
    )
    values = {
        "artifact": artifact,
        "statement": statement,
        "policy": current_policy.record(),
        "svr": svr,
        "statement_bundle": {"fake": "bundle"},
        "svr_bundle": {"fake": "svr-bundle"},
    }
    paths: dict[str, Path] = {}
    for key, value in values.items():
        path = root / f"{key}.json"
        path.write_text(json.dumps(value, sort_keys=True) + "\n")
        paths[key] = path
    return paths


def _crypto_ok(*args: object, **kwargs: object) -> SigstoreVerificationResult:
    del args, kwargs
    return SigstoreVerificationResult(verified=True, verifier_id="sigstore-cosign")


def _crypto_fail(*args: object, **kwargs: object) -> SigstoreVerificationResult:
    del args, kwargs
    return SigstoreVerificationResult(verified=False, verifier_id="sigstore-cosign")


def _build(tmp_path: Path) -> tuple[Path, AttestationTrustPolicy]:
    source = tmp_path / "source"
    source.mkdir()
    paths = _write_source_files(source)
    package = tmp_path / "package"
    build_certification_package(
        artifact_path=paths["artifact"],
        statement_path=paths["statement"],
        statement_bundle_path=paths["statement_bundle"],
        policy_path=paths["policy"],
        svr_path=paths["svr"],
        svr_bundle_path=paths["svr_bundle"],
        signer=_package_signer(),
        output_dir=package,
    )
    return package, _policy()


def test_builds_content_addressed_fixed_file_package(tmp_path: Path) -> None:
    package, _ = _build(tmp_path)
    record = json.loads((package / "manifest.json").read_text())
    manifest = load_certification_package_manifest(record)
    assert manifest.digest() == record["package_digest"]
    assert {item.path for item in manifest.files.values()} == {
        "artifact.json",
        "policy.json",
        "statement.intoto.json",
        "statement.sigstore.json",
        "svr.json",
        "svr.sigstore.json",
    }


def test_independent_consumer_replay_accepts_complete_chain(tmp_path: Path) -> None:
    package, current_policy = _build(tmp_path)
    result = verify_certification_package(
        package,
        _profile(current_policy),
        crypto_verifier=_crypto_ok,
        expected_profile_digest=_profile(current_policy).digest(),
    )
    assert result.decision is CertificationDecision.ACCEPT
    assert result.reason_codes == ()


def test_rejects_file_tampering_before_semantic_replay(tmp_path: Path) -> None:
    package, current_policy = _build(tmp_path)
    (package / "svr.json").write_text("{}\n")
    result = verify_certification_package(
        package,
        _profile(current_policy),
        crypto_verifier=_crypto_ok,
    )
    assert result.decision is CertificationDecision.REJECT
    assert CertificationReasonCode.FILE_DIGEST_MISMATCH in result.reason_codes


def test_rejects_failed_statement_and_svr_crypto(tmp_path: Path) -> None:
    package, current_policy = _build(tmp_path)
    result = verify_certification_package(
        package,
        _profile(current_policy),
        crypto_verifier=_crypto_fail,
    )
    assert result.decision is CertificationDecision.REJECT
    assert CertificationReasonCode.STATEMENT_SIGNATURE_INVALID in result.reason_codes
    assert CertificationReasonCode.SVR_SIGNATURE_INVALID in result.reason_codes


def test_rejects_consumer_profile_that_does_not_pin_policy(tmp_path: Path) -> None:
    package, current_policy = _build(tmp_path)
    base = _profile(current_policy)
    wrong = ConsumerTrustProfile(
        profile_id=base.profile_id,
        trusted_svr_verifier_ids=base.trusted_svr_verifier_ids,
        trusted_policies=(
            TrustedPolicyRef(
                policy_id="https://example.test/other-policy",
                policy_digest="sha256:" + "b" * 64,
            ),
        ),
        allowed_crypto_verifiers=base.allowed_crypto_verifiers,
        allowed_issuers=base.allowed_issuers,
        allowed_identity_patterns=base.allowed_identity_patterns,
        allowed_repositories=base.allowed_repositories,
        allowed_workflows=base.allowed_workflows,
        allowed_ref_patterns=base.allowed_ref_patterns,
        allowed_triggers=base.allowed_triggers,
        require_transparency_log=True,
    )
    result = verify_certification_package(
        package,
        wrong,
        crypto_verifier=_crypto_ok,
    )
    assert result.decision is CertificationDecision.REJECT
    assert CertificationReasonCode.CONSUMER_EXPECTATION_REJECTED in result.reason_codes


def test_rejects_external_consumer_profile_digest_mismatch(tmp_path: Path) -> None:
    package, current_policy = _build(tmp_path)
    result = verify_certification_package(
        package,
        _profile(current_policy),
        crypto_verifier=_crypto_ok,
        expected_profile_digest="sha256:" + "f" * 64,
    )
    assert result.decision is CertificationDecision.REJECT
    assert CertificationReasonCode.CONSUMER_PROFILE_MISMATCH in result.reason_codes

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
from howedo.attestation import (
    CONFORMANCE_PREDICATE_V1,
    IN_TOTO_STATEMENT_V1,
    AttestationVerificationCode,
    build_conformance_statement,
    verify_conformance_statement,
)


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
        evidence_refs=("git-source://sha/abc", "test://fixture"),
    )
    return artifact.record()


def test_builds_in_toto_statement_bound_to_exact_artifact_digest() -> None:
    record = artifact_record()
    statement = build_conformance_statement(record)

    assert statement["_type"] == IN_TOTO_STATEMENT_V1
    assert statement["predicateType"] == CONFORMANCE_PREDICATE_V1
    assert statement["subject"] == [
        {
            "name": "howedo.adapter-conformance-artifact.v1",
            "digest": {"sha256": record["artifact_digest"].removeprefix("sha256:")},
        }
    ]
    assert statement["predicate"]["conformance"] == {
        "checkCount": 11,
        "passedCount": 11,
        "status": "CONFORMANT",
    }
    assert verify_conformance_statement(record, statement).valid


def test_rejects_subject_digest_tampering() -> None:
    record = artifact_record()
    statement = build_conformance_statement(record)
    statement["subject"][0]["digest"]["sha256"] = "0" * 64

    verification = verify_conformance_statement(record, statement)
    assert not verification.valid
    assert AttestationVerificationCode.SUBJECT_DIGEST_MISMATCH in verification.reason_codes


def test_rejects_predicate_tampering() -> None:
    record = artifact_record()
    statement = build_conformance_statement(record)
    statement["predicate"]["conformance"]["status"] = "NON_CONFORMANT"

    verification = verify_conformance_statement(record, statement)
    assert not verification.valid
    assert AttestationVerificationCode.PREDICATE_MISMATCH in verification.reason_codes


def test_rejects_statement_shape_drift() -> None:
    record = artifact_record()
    statement = build_conformance_statement(record)
    statement["unexpected"] = True

    verification = verify_conformance_statement(record, statement)
    assert not verification.valid
    assert AttestationVerificationCode.INVALID_STATEMENT in verification.reason_codes


def test_invalid_r9_artifact_cannot_be_attested() -> None:
    record = artifact_record()
    record["status"] = "NON_CONFORMANT"

    with pytest.raises(ValueError, match="cannot attest invalid conformance artifact"):
        build_conformance_statement(record)

    valid_statement = build_conformance_statement(artifact_record())
    verification = verify_conformance_statement(record, deepcopy(valid_statement))
    assert not verification.valid
    assert AttestationVerificationCode.ARTIFACT_INVALID in verification.reason_codes

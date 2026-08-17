from __future__ import annotations

from copy import deepcopy

import pytest

from howedo.adapter_certification import (
    CONFORMANCE_CHECKS_V1,
    ArtifactVerificationCode,
    ConformanceArtifact,
    ConformanceEnvironment,
    ConformanceStatus,
    verify_conformance_record,
)
from howedo.adapter_conformance import ConformanceResult
from howedo.adapter_contract import AdapterCapability, AdapterManifest


def manifest() -> AdapterManifest:
    return AdapterManifest.build(
        adapter_id="test.certified",
        runtime_family="fake",
        adapter_version="1.0.0",
        capabilities=(
            AdapterCapability.EXACT_RUNTIME_IDENTITY,
            AdapterCapability.CAPTURE,
            AdapterCapability.VALIDATE_RESUME,
            AdapterCapability.CONTINUE,
        ),
    )


def passing_checks() -> tuple[ConformanceResult, ...]:
    return tuple(
        ConformanceResult(check=name, passed=True, detail=f"proof:{name}")
        for name in CONFORMANCE_CHECKS_V1
    )


def environment() -> ConformanceEnvironment:
    return ConformanceEnvironment(
        python_version="3.12.13",
        python_implementation="CPython",
        platform="linux",
    )


def test_conformance_artifact_is_deterministic_and_self_verifiable() -> None:
    artifact = ConformanceArtifact(
        manifest=manifest(),
        checks=passing_checks(),
        environment=environment(),
        evidence_refs=("ci://31988166578", "sha://fd9e35a9"),
    )
    assert artifact.status is ConformanceStatus.CONFORMANT
    assert artifact.digest() == artifact.digest()

    verification = verify_conformance_record(artifact.record())
    assert verification.valid
    assert verification.reason_codes == ()


def test_tampering_breaks_artifact_digest() -> None:
    artifact = ConformanceArtifact(
        manifest=manifest(),
        checks=passing_checks(),
        environment=environment(),
    )
    tampered = deepcopy(artifact.record())
    tampered["checks"][0]["detail"] = "tampered"

    verification = verify_conformance_record(tampered)
    assert not verification.valid
    assert ArtifactVerificationCode.ARTIFACT_DIGEST_MISMATCH in verification.reason_codes


def test_status_is_derived_from_results() -> None:
    checks = list(passing_checks())
    checks[-1] = ConformanceResult(
        check=checks[-1].check,
        passed=False,
        detail="continuation did not occur",
    )
    artifact = ConformanceArtifact(
        manifest=manifest(),
        checks=tuple(checks),
        environment=environment(),
    )
    assert artifact.status is ConformanceStatus.NON_CONFORMANT
    assert verify_conformance_record(artifact.record()).valid


def test_artifact_rejects_check_omission_and_noncanonical_evidence_refs() -> None:
    with pytest.raises(ValueError, match="frozen v1 check sequence"):
        ConformanceArtifact(
            manifest=manifest(),
            checks=passing_checks()[:-1],
            environment=environment(),
        )

    with pytest.raises(ValueError, match="sorted and unique"):
        ConformanceArtifact(
            manifest=manifest(),
            checks=passing_checks(),
            environment=environment(),
            evidence_refs=("z", "a"),
        )

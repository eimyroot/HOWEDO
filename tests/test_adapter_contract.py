from __future__ import annotations

import pytest

from howedo.adapter_contract import (
    ADAPTER_CONTRACT_VERSION,
    AdapterCapability,
    AdapterFailureCode,
    AdapterManifest,
    RuntimeIdentity,
)


def test_manifest_is_canonical_and_content_addressed() -> None:
    manifest = AdapterManifest.build(
        adapter_id="example.adapter",
        runtime_family="example",
        adapter_version="1.0.0",
        capabilities=(
            AdapterCapability.VALIDATE_RESUME,
            AdapterCapability.CAPTURE,
            AdapterCapability.CONTINUE,
            AdapterCapability.EXACT_RUNTIME_IDENTITY,
            AdapterCapability.CAPTURE,
        ),
    )
    assert manifest.contract_version == ADAPTER_CONTRACT_VERSION
    assert manifest.capabilities == tuple(sorted(set(manifest.capabilities), key=lambda item: item.value))
    assert manifest.digest().startswith("sha256:")
    assert manifest.digest() == manifest.digest()


def test_manifest_rejects_noncanonical_capabilities() -> None:
    with pytest.raises(ValueError, match="sorted and unique"):
        AdapterManifest(
            adapter_id="example.adapter",
            runtime_family="example",
            adapter_version="1.0.0",
            capabilities=(
                AdapterCapability.CONTINUE,
                AdapterCapability.CAPTURE,
            ),
        )


def test_runtime_identity_is_deterministic() -> None:
    identity = RuntimeIdentity(
        runtime_family="temporal",
        namespace="default",
        execution_id="workflow-1",
        execution_revision="run-1",
    )
    assert identity.digest().startswith("sha256:")
    assert identity.digest() == identity.digest()
    assert identity.canonical()["execution_revision"] == "run-1"


def test_failure_codes_are_stable_strings() -> None:
    assert AdapterFailureCode.IDENTITY_MISMATCH.value == "IDENTITY_MISMATCH"
    assert AdapterFailureCode.CONTINUITY_BLOCKED.value == "CONTINUITY_BLOCKED"

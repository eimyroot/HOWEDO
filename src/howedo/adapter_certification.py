from __future__ import annotations

import json
import platform
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Any

from howedo.adapter_conformance import AdapterConformanceSuite, AdapterFixture, ConformanceResult
from howedo.adapter_contract import AdapterCapability, AdapterManifest, RuntimeAdapterV1

CONFORMANCE_ARTIFACT_VERSION = "howedo.adapter-conformance-artifact.v1"
CONFORMANCE_CHECKS_V1 = (
    "runtime-adapter-v1-structural",
    "contract-version",
    "required-capabilities",
    "manifest-content-addressed",
    "identity-runtime-family",
    "identity-content-addressed",
    "binding-manifest-digest",
    "binding-exact-identity",
    "unchanged-reality-recovers",
    "changed-reality-does-not-recover",
    "continue-after-recover",
)
_RECORD_KEYS = {
    "artifact_digest",
    "artifact_version",
    "checks",
    "environment",
    "evidence_refs",
    "manifest",
    "manifest_digest",
    "status",
}


class ConformanceStatus(StrEnum):
    CONFORMANT = "CONFORMANT"
    NON_CONFORMANT = "NON_CONFORMANT"


class ArtifactVerificationCode(StrEnum):
    ARTIFACT_VERSION_MISMATCH = "ARTIFACT_VERSION_MISMATCH"
    ARTIFACT_DIGEST_MISMATCH = "ARTIFACT_DIGEST_MISMATCH"
    MANIFEST_DIGEST_MISMATCH = "MANIFEST_DIGEST_MISMATCH"
    CHECK_SET_MISMATCH = "CHECK_SET_MISMATCH"
    STATUS_MISMATCH = "STATUS_MISMATCH"
    INVALID_RECORD = "INVALID_RECORD"


@dataclass(frozen=True, slots=True)
class ConformanceEnvironment:
    python_version: str
    python_implementation: str
    platform: str

    @classmethod
    def current(cls) -> ConformanceEnvironment:
        return cls(
            python_version=platform.python_version(),
            python_implementation=platform.python_implementation(),
            platform=sys.platform,
        )

    def canonical(self) -> dict[str, str]:
        return {
            "platform": self.platform,
            "python_implementation": self.python_implementation,
            "python_version": self.python_version,
        }


@dataclass(frozen=True, slots=True)
class ConformanceArtifact:
    manifest: AdapterManifest
    checks: tuple[ConformanceResult, ...]
    environment: ConformanceEnvironment
    evidence_refs: tuple[str, ...] = ()
    artifact_version: str = CONFORMANCE_ARTIFACT_VERSION

    def __post_init__(self) -> None:
        if self.artifact_version != CONFORMANCE_ARTIFACT_VERSION:
            raise ValueError("unsupported conformance artifact version")
        if tuple(result.check for result in self.checks) != CONFORMANCE_CHECKS_V1:
            raise ValueError("conformance checks must match the frozen v1 check sequence")
        canonical_refs = tuple(sorted(set(self.evidence_refs)))
        if canonical_refs != self.evidence_refs:
            raise ValueError("evidence_refs must be sorted and unique")

    @property
    def status(self) -> ConformanceStatus:
        if all(result.passed for result in self.checks):
            return ConformanceStatus.CONFORMANT
        return ConformanceStatus.NON_CONFORMANT

    def canonical(self) -> dict[str, Any]:
        return {
            "artifact_version": self.artifact_version,
            "checks": [
                {
                    "check": result.check,
                    "detail": result.detail,
                    "passed": result.passed,
                }
                for result in self.checks
            ],
            "environment": self.environment.canonical(),
            "evidence_refs": list(self.evidence_refs),
            "manifest": _manifest_record(self.manifest),
            "manifest_digest": self.manifest.digest(),
            "status": self.status.value,
        }

    def digest(self) -> str:
        return _digest(self.canonical())

    def record(self) -> dict[str, Any]:
        record = self.canonical()
        record["artifact_digest"] = self.digest()
        return record

    def to_json(self) -> str:
        return json.dumps(self.record(), sort_keys=True, separators=(",", ":"))

    def write(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_json() + "\n")
        return target


@dataclass(frozen=True, slots=True)
class ArtifactVerification:
    valid: bool
    reason_codes: tuple[ArtifactVerificationCode, ...]


class AdapterConformanceArtifactBuilder:
    """Run v1 conformance and bind the result to a content-addressed artifact."""

    async def build(
        self,
        adapter: RuntimeAdapterV1,
        fixture: AdapterFixture,
        *,
        environment: ConformanceEnvironment | None = None,
        evidence_refs: Sequence[str] = (),
    ) -> ConformanceArtifact:
        results = await AdapterConformanceSuite().run(adapter, fixture)
        return ConformanceArtifact(
            manifest=adapter.manifest(),
            checks=tuple(results),
            environment=environment or ConformanceEnvironment.current(),
            evidence_refs=tuple(sorted(set(evidence_refs))),
        )


def verify_conformance_record(record: Mapping[str, Any]) -> ArtifactVerification:
    """Verify record integrity without importing any runtime vendor SDK."""

    reasons: list[ArtifactVerificationCode] = []
    try:
        if set(record) != _RECORD_KEYS:
            reasons.append(ArtifactVerificationCode.INVALID_RECORD)

        canonical = dict(record)
        supplied_digest = canonical.pop("artifact_digest")
        if canonical.get("artifact_version") != CONFORMANCE_ARTIFACT_VERSION:
            reasons.append(ArtifactVerificationCode.ARTIFACT_VERSION_MISMATCH)
        if supplied_digest != _digest(canonical):
            reasons.append(ArtifactVerificationCode.ARTIFACT_DIGEST_MISMATCH)

        manifest_data = canonical["manifest"]
        if not isinstance(manifest_data, Mapping):
            raise TypeError("manifest must be an object")
        manifest = AdapterManifest.build(
            adapter_id=str(manifest_data["adapter_id"]),
            runtime_family=str(manifest_data["runtime_family"]),
            adapter_version=str(manifest_data["adapter_version"]),
            capabilities=tuple(
                AdapterCapability(str(value)) for value in manifest_data["capabilities"]
            ),
        )
        if dict(manifest_data) != _manifest_record(manifest):
            reasons.append(ArtifactVerificationCode.INVALID_RECORD)
        if canonical.get("manifest_digest") != manifest.digest():
            reasons.append(ArtifactVerificationCode.MANIFEST_DIGEST_MISMATCH)

        checks = canonical["checks"]
        if not isinstance(checks, list):
            raise TypeError("checks must be an array")
        for item in checks:
            if not isinstance(item, Mapping) or set(item) != {"check", "detail", "passed"}:
                reasons.append(ArtifactVerificationCode.INVALID_RECORD)
                continue
            if not isinstance(item["check"], str) or not isinstance(item["detail"], str):
                reasons.append(ArtifactVerificationCode.INVALID_RECORD)
            if not isinstance(item["passed"], bool):
                reasons.append(ArtifactVerificationCode.INVALID_RECORD)

        check_names = tuple(str(item["check"]) for item in checks)
        if check_names != CONFORMANCE_CHECKS_V1:
            reasons.append(ArtifactVerificationCode.CHECK_SET_MISMATCH)

        expected_status = (
            ConformanceStatus.CONFORMANT.value
            if all(item["passed"] is True for item in checks)
            else ConformanceStatus.NON_CONFORMANT.value
        )
        if canonical.get("status") != expected_status:
            reasons.append(ArtifactVerificationCode.STATUS_MISMATCH)

        evidence_refs = canonical["evidence_refs"]
        if (
            not isinstance(evidence_refs, list)
            or any(not isinstance(item, str) or not item for item in evidence_refs)
            or evidence_refs != sorted(set(evidence_refs))
        ):
            reasons.append(ArtifactVerificationCode.INVALID_RECORD)

        environment = canonical["environment"]
        expected_environment_keys = {"platform", "python_implementation", "python_version"}
        if (
            not isinstance(environment, Mapping)
            or set(environment) != expected_environment_keys
            or any(
                not isinstance(environment[key], str) or not environment[key]
                for key in environment
            )
        ):
            reasons.append(ArtifactVerificationCode.INVALID_RECORD)
    except (KeyError, TypeError, ValueError):
        reasons.append(ArtifactVerificationCode.INVALID_RECORD)

    unique_reasons = tuple(dict.fromkeys(reasons))
    return ArtifactVerification(valid=not unique_reasons, reason_codes=unique_reasons)


def _manifest_record(manifest: AdapterManifest) -> dict[str, Any]:
    return {
        "adapter_id": manifest.adapter_id,
        "adapter_version": manifest.adapter_version,
        "capabilities": [item.value for item in manifest.capabilities],
        "contract_version": manifest.contract_version,
        "runtime_family": manifest.runtime_family,
    }


def _digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{sha256(encoded).hexdigest()}"

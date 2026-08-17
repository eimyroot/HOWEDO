from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Any

from howedo.adapter_certification import verify_conformance_record
from howedo.attestation import verify_conformance_statement
from howedo.consumer_trust import (
    ConsumerTrustProfile,
    evaluate_consumer_expectations,
)
from howedo.protocol import canonical_digest
from howedo.sigstore_trust import (
    SigstoreGithubClaims,
    SigstoreVerificationResult,
    verify_sigstore_github_bundle,
)
from howedo.trust_policy import (
    SignerVerificationContext,
    evaluate_attestation_trust,
    load_trust_policy,
    verify_svr_statement,
)

CERTIFICATION_PACKAGE_VERSION = "howedo.certification-package.v1"

_FILE_NAMES = {
    "artifact": "artifact.json",
    "policy": "policy.json",
    "statement": "statement.intoto.json",
    "statement_bundle": "statement.sigstore.json",
    "svr": "svr.json",
    "svr_bundle": "svr.sigstore.json",
}
_MANIFEST_KEYS = {
    "artifact_digest",
    "files",
    "package_digest",
    "package_version",
    "policy_digest",
    "signer",
}
_SIGNER_KEYS = {
    "evidence_refs",
    "execution_ref",
    "execution_sha",
    "identity",
    "issuer",
    "repository",
    "trigger",
    "workflow",
}


class CertificationDecision(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


class CertificationReasonCode(StrEnum):
    PACKAGE_INVALID = "PACKAGE_INVALID"
    FILE_DIGEST_MISMATCH = "FILE_DIGEST_MISMATCH"
    ARTIFACT_BINDING_INVALID = "ARTIFACT_BINDING_INVALID"
    POLICY_BINDING_INVALID = "POLICY_BINDING_INVALID"
    CONSUMER_EXPECTATION_REJECTED = "CONSUMER_EXPECTATION_REJECTED"
    CONSUMER_PROFILE_MISMATCH = "CONSUMER_PROFILE_MISMATCH"
    STATEMENT_SIGNATURE_INVALID = "STATEMENT_SIGNATURE_INVALID"
    TRUST_REPLAY_REJECTED = "TRUST_REPLAY_REJECTED"
    SVR_REPLAY_INVALID = "SVR_REPLAY_INVALID"
    SVR_SIGNATURE_INVALID = "SVR_SIGNATURE_INVALID"
    SIGNER_CONTEXT_MISMATCH = "SIGNER_CONTEXT_MISMATCH"


@dataclass(frozen=True, slots=True)
class CertificationSigner:
    issuer: str
    identity: str
    repository: str
    workflow: str
    execution_sha: str
    execution_ref: str
    trigger: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = (
            self.issuer,
            self.identity,
            self.repository,
            self.workflow,
            self.execution_sha,
            self.execution_ref,
            self.trigger,
        )
        if any(not value for value in values):
            raise ValueError("certification signer fields must be non-empty")
        if tuple(sorted(set(self.evidence_refs))) != self.evidence_refs:
            raise ValueError("certification signer evidence_refs must be sorted and unique")

    def canonical(self) -> dict[str, Any]:
        return {
            "evidence_refs": list(self.evidence_refs),
            "execution_ref": self.execution_ref,
            "execution_sha": self.execution_sha,
            "identity": self.identity,
            "issuer": self.issuer,
            "repository": self.repository,
            "trigger": self.trigger,
            "workflow": self.workflow,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> CertificationSigner:
        if set(record) != _SIGNER_KEYS:
            raise ValueError("certification signer shape mismatch")
        evidence_refs = record.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not all(
            isinstance(item, str) and item for item in evidence_refs
        ):
            raise TypeError("evidence_refs must be a list of non-empty strings")
        values = {
            key: _required_string(record, key)
            for key in sorted(_SIGNER_KEYS - {"evidence_refs"})
        }
        return cls(**values, evidence_refs=tuple(evidence_refs))


@dataclass(frozen=True, slots=True)
class PackageFile:
    path: str
    digest: str

    def __post_init__(self) -> None:
        if not self.path or Path(self.path).is_absolute() or ".." in Path(self.path).parts:
            raise ValueError("package file path must be safe and relative")
        if not _is_sha256_digest(self.digest):
            raise ValueError("package file digest must be sha256:<64 lowercase hex>")

    def canonical(self) -> dict[str, str]:
        return {"digest": self.digest, "path": self.path}


@dataclass(frozen=True, slots=True)
class CertificationPackageManifest:
    artifact_digest: str
    policy_digest: str
    signer: CertificationSigner
    files: Mapping[str, PackageFile]
    package_version: str = CERTIFICATION_PACKAGE_VERSION

    def __post_init__(self) -> None:
        if self.package_version != CERTIFICATION_PACKAGE_VERSION:
            raise ValueError("unsupported certification package version")
        if not _is_sha256_digest(self.artifact_digest):
            raise ValueError("artifact_digest must be sha256:<64 lowercase hex>")
        if not _is_sha256_digest(self.policy_digest):
            raise ValueError("policy_digest must be sha256:<64 lowercase hex>")
        if set(self.files) != set(_FILE_NAMES):
            raise ValueError("certification package file set mismatch")
        for key, expected_name in _FILE_NAMES.items():
            if self.files[key].path != expected_name:
                raise ValueError(f"certification package path mismatch for {key}")

    def canonical(self) -> dict[str, Any]:
        return {
            "artifact_digest": self.artifact_digest,
            "files": {key: self.files[key].canonical() for key in sorted(self.files)},
            "package_version": self.package_version,
            "policy_digest": self.policy_digest,
            "signer": self.signer.canonical(),
        }

    def digest(self) -> str:
        return canonical_digest(self.canonical())

    def record(self) -> dict[str, Any]:
        record = self.canonical()
        record["package_digest"] = self.digest()
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> CertificationPackageManifest:
        if set(record) != _MANIFEST_KEYS:
            raise ValueError("certification package manifest shape mismatch")
        raw_files = record.get("files")
        if not isinstance(raw_files, Mapping):
            raise TypeError("files must be an object")
        files: dict[str, PackageFile] = {}
        for key, raw in raw_files.items():
            if not isinstance(key, str) or not isinstance(raw, Mapping):
                raise TypeError("package file entries must be objects")
            if set(raw) != {"path", "digest"}:
                raise ValueError("package file entry shape mismatch")
            files[key] = PackageFile(
                path=_required_string(raw, "path"),
                digest=_required_string(raw, "digest"),
            )
        raw_signer = record.get("signer")
        if not isinstance(raw_signer, Mapping):
            raise TypeError("signer must be an object")
        manifest = cls(
            artifact_digest=_required_string(record, "artifact_digest"),
            policy_digest=_required_string(record, "policy_digest"),
            signer=CertificationSigner.from_record(raw_signer),
            files=files,
            package_version=_required_string(record, "package_version"),
        )
        if record.get("package_digest") != manifest.digest():
            raise ValueError("certification package digest mismatch")
        return manifest


@dataclass(frozen=True, slots=True)
class CertificationVerificationResult:
    decision: CertificationDecision
    reason_codes: tuple[CertificationReasonCode, ...]
    package_digest: str | None
    profile_digest: str
    policy_digest: str | None

    @property
    def accepted(self) -> bool:
        return self.decision is CertificationDecision.ACCEPT


CryptoVerifier = Callable[..., SigstoreVerificationResult]


def build_certification_package(
    *,
    artifact_path: str | Path,
    statement_path: str | Path,
    statement_bundle_path: str | Path,
    policy_path: str | Path,
    svr_path: str | Path,
    svr_bundle_path: str | Path,
    signer: CertificationSigner,
    output_dir: str | Path,
) -> CertificationPackageManifest:
    sources = {
        "artifact": Path(artifact_path),
        "statement": Path(statement_path),
        "statement_bundle": Path(statement_bundle_path),
        "policy": Path(policy_path),
        "svr": Path(svr_path),
        "svr_bundle": Path(svr_bundle_path),
    }
    for source in sources.values():
        if not source.is_file():
            raise FileNotFoundError(source)

    artifact = _load_object(sources["artifact"])
    statement = _load_object(sources["statement"])
    policy = load_trust_policy(_load_object(sources["policy"]))
    artifact_check = verify_conformance_record(artifact)
    if not artifact_check.valid:
        raise ValueError("cannot package invalid conformance artifact")
    statement_check = verify_conformance_statement(artifact, statement)
    if not statement_check.valid:
        raise ValueError("cannot package invalid conformance statement")

    artifact_digest = artifact.get("artifact_digest")
    if not isinstance(artifact_digest, str) or not _is_sha256_digest(artifact_digest):
        raise ValueError("artifact missing valid artifact_digest")

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    files: dict[str, PackageFile] = {}
    for key, source in sources.items():
        target = root / _FILE_NAMES[key]
        target.write_bytes(source.read_bytes())
        files[key] = PackageFile(path=_FILE_NAMES[key], digest=_file_digest(target))

    manifest = CertificationPackageManifest(
        artifact_digest=artifact_digest,
        policy_digest=policy.digest(),
        signer=signer,
        files=files,
    )
    (root / "manifest.json").write_text(
        json.dumps(manifest.record(), sort_keys=True, separators=(",", ":")) + "\n"
    )
    return manifest


def load_certification_package_manifest(record: Mapping[str, Any]) -> CertificationPackageManifest:
    return CertificationPackageManifest.from_record(record)


def verify_certification_package(
    package_dir: str | Path,
    profile: ConsumerTrustProfile,
    *,
    crypto_verifier: CryptoVerifier = verify_sigstore_github_bundle,
    cosign_executable: str = "cosign",
    expected_profile_digest: str | None = None,
) -> CertificationVerificationResult:
    root = Path(package_dir)
    reasons: list[CertificationReasonCode] = []
    if expected_profile_digest is not None and profile.digest() != expected_profile_digest:
        reasons.append(CertificationReasonCode.CONSUMER_PROFILE_MISMATCH)
        return _result(reasons, None, profile, None)
    manifest: CertificationPackageManifest | None = None
    policy_digest: str | None = None
    try:
        manifest = load_certification_package_manifest(_load_object(root / "manifest.json"))
        resolved = _resolve_and_verify_files(root, manifest)
        artifact = _load_object(resolved["artifact"])
        statement = _load_object(resolved["statement"])
        policy = load_trust_policy(_load_object(resolved["policy"]))
        svr = _load_object(resolved["svr"])
        policy_digest = policy.digest()
    except FileDigestMismatch:
        reasons.append(CertificationReasonCode.FILE_DIGEST_MISMATCH)
        return _result(reasons, manifest, profile, policy_digest)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        reasons.append(CertificationReasonCode.PACKAGE_INVALID)
        return _result(reasons, manifest, profile, policy_digest)

    if artifact.get("artifact_digest") != manifest.artifact_digest:
        reasons.append(CertificationReasonCode.ARTIFACT_BINDING_INVALID)
    if policy.digest() != manifest.policy_digest:
        reasons.append(CertificationReasonCode.POLICY_BINDING_INVALID)
    if not verify_conformance_record(artifact).valid:
        reasons.append(CertificationReasonCode.ARTIFACT_BINDING_INVALID)
    if not verify_conformance_statement(artifact, statement).valid:
        reasons.append(CertificationReasonCode.ARTIFACT_BINDING_INVALID)

    claims = SigstoreGithubClaims(
        identity=manifest.signer.identity,
        issuer=manifest.signer.issuer,
        repository=manifest.signer.repository,
        workflow_sha=manifest.signer.execution_sha,
        workflow_ref=manifest.signer.execution_ref,
        workflow_trigger=manifest.signer.trigger,
        workflow_name=profile.expected_workflow_name,
    )
    statement_crypto = crypto_verifier(
        resolved["statement"],
        resolved["statement_bundle"],
        claims,
        cosign_executable=cosign_executable,
    )
    statement_signer = _signer_context(manifest.signer, statement_crypto)
    if not statement_crypto.verified:
        reasons.append(CertificationReasonCode.STATEMENT_SIGNATURE_INVALID)

    consumer_check = evaluate_consumer_expectations(profile, policy, svr, statement_signer)
    if not consumer_check.accepted:
        reasons.append(CertificationReasonCode.CONSUMER_EXPECTATION_REJECTED)

    trust_evaluation = evaluate_attestation_trust(policy, artifact, statement, statement_signer)
    if not trust_evaluation.accepted:
        reasons.append(CertificationReasonCode.TRUST_REPLAY_REJECTED)
    if not verify_svr_statement(policy, artifact, statement, statement_signer, svr):
        reasons.append(CertificationReasonCode.SVR_REPLAY_INVALID)

    svr_crypto = crypto_verifier(
        resolved["svr"],
        resolved["svr_bundle"],
        claims,
        cosign_executable=cosign_executable,
    )
    svr_signer = _signer_context(manifest.signer, svr_crypto)
    if not svr_crypto.verified:
        reasons.append(CertificationReasonCode.SVR_SIGNATURE_INVALID)
    if statement_signer.digest() != svr_signer.digest():
        reasons.append(CertificationReasonCode.SIGNER_CONTEXT_MISMATCH)
    svr_consumer_check = evaluate_consumer_expectations(profile, policy, svr, svr_signer)
    if not svr_consumer_check.accepted:
        reasons.append(CertificationReasonCode.CONSUMER_EXPECTATION_REJECTED)

    return _result(reasons, manifest, profile, policy_digest)


def _signer_context(
    signer: CertificationSigner,
    crypto: SigstoreVerificationResult,
) -> SignerVerificationContext:
    return SignerVerificationContext(
        verifier_id=crypto.verifier_id,
        cryptographically_verified=crypto.verified,
        issuer=signer.issuer,
        identity=signer.identity,
        repository=signer.repository,
        workflow=signer.workflow,
        execution_sha=signer.execution_sha,
        execution_ref=signer.execution_ref,
        trigger=signer.trigger,
        transparency_log_verified=crypto.verified,
        evidence_refs=signer.evidence_refs,
    )


def _resolve_and_verify_files(
    root: Path,
    manifest: CertificationPackageManifest,
) -> dict[str, Path]:
    root_resolved = root.resolve()
    resolved: dict[str, Path] = {}
    for key, item in manifest.files.items():
        path = root / item.path
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"invalid package file: {item.path}")
        actual = path.resolve()
        if actual.parent != root_resolved:
            raise ValueError(f"package file escapes root: {item.path}")
        if _file_digest(actual) != item.digest:
            raise FileDigestMismatch(item.path)
        resolved[key] = actual
    return resolved


def _result(
    reasons: list[CertificationReasonCode],
    manifest: CertificationPackageManifest | None,
    profile: ConsumerTrustProfile,
    policy_digest: str | None,
) -> CertificationVerificationResult:
    unique = tuple(dict.fromkeys(reasons))
    return CertificationVerificationResult(
        decision=CertificationDecision.REJECT if unique else CertificationDecision.ACCEPT,
        reason_codes=unique,
        package_digest=manifest.digest() if manifest is not None else None,
        profile_digest=profile.digest(),
        policy_digest=policy_digest,
    )


def _load_object(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, Mapping):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _file_digest(path: Path) -> str:
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def _required_string(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{key} must be a non-empty string")
    return value


def _is_sha256_digest(value: str) -> bool:
    return re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None


class FileDigestMismatch(ValueError):
    pass

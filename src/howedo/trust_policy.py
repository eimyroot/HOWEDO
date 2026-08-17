from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any

from howedo.adapter_certification import ConformanceStatus, verify_conformance_record
from howedo.attestation import verify_conformance_statement

TRUST_POLICY_VERSION = "howedo.attestation-trust-policy.v1"
SVR_STATEMENT_V1 = "https://in-toto.io/Statement/v1"
SVR_PREDICATE_V02 = "https://in-toto.io/attestation/svr/v0.2"
TRUST_VERIFIER_ID = "https://github.com/nulleimy/HOWEDO/verifiers/attestation-trust/v1"
TRUST_ACCEPTED_PROPERTY = "HOWEDO_ATTESTATION_TRUST_ACCEPTED"
TRUST_REJECTED_PROPERTY = "HOWEDO_ATTESTATION_TRUST_REJECTED"

_POLICY_KEYS = {
    "allowed_artifact_versions",
    "allowed_identity_patterns",
    "allowed_issuers",
    "allowed_predicate_types",
    "allowed_ref_patterns",
    "allowed_repositories",
    "allowed_triggers",
    "allowed_verifiers",
    "allowed_workflows",
    "policy_digest",
    "policy_id",
    "policy_version",
    "require_conformant_status",
    "require_execution_sha_matches_artifact_checkout",
    "require_transparency_log",
}


class TrustDecision(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


class TrustReasonCode(StrEnum):
    ARTIFACT_INVALID = "ARTIFACT_INVALID"
    STATEMENT_INVALID = "STATEMENT_INVALID"
    CRYPTOGRAPHIC_VERIFICATION_FAILED = "CRYPTOGRAPHIC_VERIFICATION_FAILED"
    VERIFIER_NOT_ALLOWED = "VERIFIER_NOT_ALLOWED"
    ISSUER_NOT_ALLOWED = "ISSUER_NOT_ALLOWED"
    IDENTITY_NOT_ALLOWED = "IDENTITY_NOT_ALLOWED"
    REPOSITORY_NOT_ALLOWED = "REPOSITORY_NOT_ALLOWED"
    WORKFLOW_NOT_ALLOWED = "WORKFLOW_NOT_ALLOWED"
    REF_NOT_ALLOWED = "REF_NOT_ALLOWED"
    TRIGGER_NOT_ALLOWED = "TRIGGER_NOT_ALLOWED"
    PREDICATE_TYPE_NOT_ALLOWED = "PREDICATE_TYPE_NOT_ALLOWED"
    ARTIFACT_VERSION_NOT_ALLOWED = "ARTIFACT_VERSION_NOT_ALLOWED"
    CONFORMANCE_STATUS_NOT_ALLOWED = "CONFORMANCE_STATUS_NOT_ALLOWED"
    TRANSPARENCY_REQUIRED = "TRANSPARENCY_REQUIRED"
    ARTIFACT_CHECKOUT_SHA_MISSING = "ARTIFACT_CHECKOUT_SHA_MISSING"
    EXECUTION_SHA_MISMATCH = "EXECUTION_SHA_MISMATCH"


@dataclass(frozen=True, slots=True)
class SignerVerificationContext:
    verifier_id: str
    cryptographically_verified: bool
    issuer: str
    identity: str
    repository: str
    workflow: str
    execution_sha: str
    execution_ref: str
    trigger: str
    transparency_log_verified: bool
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = (
            self.verifier_id,
            self.issuer,
            self.identity,
            self.repository,
            self.workflow,
            self.execution_sha,
            self.execution_ref,
            self.trigger,
        )
        if any(not value for value in values):
            raise ValueError("signer verification context fields must be non-empty")
        if tuple(sorted(set(self.evidence_refs))) != self.evidence_refs:
            raise ValueError("evidence_refs must be sorted and unique")

    def canonical(self) -> dict[str, Any]:
        return {
            "cryptographically_verified": self.cryptographically_verified,
            "evidence_refs": list(self.evidence_refs),
            "execution_ref": self.execution_ref,
            "execution_sha": self.execution_sha,
            "identity": self.identity,
            "issuer": self.issuer,
            "repository": self.repository,
            "transparency_log_verified": self.transparency_log_verified,
            "trigger": self.trigger,
            "verifier_id": self.verifier_id,
            "workflow": self.workflow,
        }

    def digest(self) -> str:
        return _digest(self.canonical())


@dataclass(frozen=True, slots=True)
class AttestationTrustPolicy:
    policy_id: str
    allowed_verifiers: tuple[str, ...]
    allowed_issuers: tuple[str, ...]
    allowed_identity_patterns: tuple[str, ...]
    allowed_repositories: tuple[str, ...]
    allowed_workflows: tuple[str, ...]
    allowed_ref_patterns: tuple[str, ...]
    allowed_triggers: tuple[str, ...]
    allowed_predicate_types: tuple[str, ...]
    allowed_artifact_versions: tuple[str, ...]
    require_conformant_status: bool
    require_transparency_log: bool
    require_execution_sha_matches_artifact_checkout: bool
    policy_version: str = TRUST_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.policy_version != TRUST_POLICY_VERSION:
            raise ValueError("unsupported trust policy version")
        if not self.policy_id:
            raise ValueError("policy_id must be non-empty")
        for values in (
            self.allowed_verifiers,
            self.allowed_issuers,
            self.allowed_identity_patterns,
            self.allowed_repositories,
            self.allowed_workflows,
            self.allowed_ref_patterns,
            self.allowed_triggers,
            self.allowed_predicate_types,
            self.allowed_artifact_versions,
        ):
            if not values or tuple(sorted(set(values))) != values:
                raise ValueError("policy allow-lists must be non-empty, sorted, and unique")
            if any(not value for value in values):
                raise ValueError("policy allow-list entries must be non-empty")

    def canonical(self) -> dict[str, Any]:
        return {
            "allowed_artifact_versions": list(self.allowed_artifact_versions),
            "allowed_identity_patterns": list(self.allowed_identity_patterns),
            "allowed_issuers": list(self.allowed_issuers),
            "allowed_predicate_types": list(self.allowed_predicate_types),
            "allowed_ref_patterns": list(self.allowed_ref_patterns),
            "allowed_repositories": list(self.allowed_repositories),
            "allowed_triggers": list(self.allowed_triggers),
            "allowed_verifiers": list(self.allowed_verifiers),
            "allowed_workflows": list(self.allowed_workflows),
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "require_conformant_status": self.require_conformant_status,
            "require_execution_sha_matches_artifact_checkout": (
                self.require_execution_sha_matches_artifact_checkout
            ),
            "require_transparency_log": self.require_transparency_log,
        }

    def digest(self) -> str:
        return _digest(self.canonical())

    def record(self) -> dict[str, Any]:
        record = self.canonical()
        record["policy_digest"] = self.digest()
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> AttestationTrustPolicy:
        if set(record) != _POLICY_KEYS:
            raise ValueError("trust policy record shape mismatch")
        policy = cls(
            policy_id=_required_string(record, "policy_id"),
            allowed_verifiers=_string_tuple(record, "allowed_verifiers"),
            allowed_issuers=_string_tuple(record, "allowed_issuers"),
            allowed_identity_patterns=_string_tuple(record, "allowed_identity_patterns"),
            allowed_repositories=_string_tuple(record, "allowed_repositories"),
            allowed_workflows=_string_tuple(record, "allowed_workflows"),
            allowed_ref_patterns=_string_tuple(record, "allowed_ref_patterns"),
            allowed_triggers=_string_tuple(record, "allowed_triggers"),
            allowed_predicate_types=_string_tuple(record, "allowed_predicate_types"),
            allowed_artifact_versions=_string_tuple(record, "allowed_artifact_versions"),
            require_conformant_status=_required_bool(record, "require_conformant_status"),
            require_transparency_log=_required_bool(record, "require_transparency_log"),
            require_execution_sha_matches_artifact_checkout=_required_bool(
                record, "require_execution_sha_matches_artifact_checkout"
            ),
            policy_version=_required_string(record, "policy_version"),
        )
        if record.get("policy_digest") != policy.digest():
            raise ValueError("trust policy digest mismatch")
        return policy


@dataclass(frozen=True, slots=True)
class TrustEvaluation:
    decision: TrustDecision
    reason_codes: tuple[TrustReasonCode, ...]
    policy_digest: str
    signer_context_digest: str

    @property
    def accepted(self) -> bool:
        return self.decision is TrustDecision.ACCEPT


def evaluate_attestation_trust(
    policy: AttestationTrustPolicy,
    artifact: Mapping[str, Any],
    statement: Mapping[str, Any],
    signer: SignerVerificationContext,
) -> TrustEvaluation:
    reasons: list[TrustReasonCode] = []

    if not verify_conformance_record(artifact).valid:
        reasons.append(TrustReasonCode.ARTIFACT_INVALID)
    if not verify_conformance_statement(artifact, statement).valid:
        reasons.append(TrustReasonCode.STATEMENT_INVALID)
    if not signer.cryptographically_verified:
        reasons.append(TrustReasonCode.CRYPTOGRAPHIC_VERIFICATION_FAILED)
    if signer.verifier_id not in policy.allowed_verifiers:
        reasons.append(TrustReasonCode.VERIFIER_NOT_ALLOWED)
    if signer.issuer not in policy.allowed_issuers:
        reasons.append(TrustReasonCode.ISSUER_NOT_ALLOWED)
    if not _matches_any(signer.identity, policy.allowed_identity_patterns):
        reasons.append(TrustReasonCode.IDENTITY_NOT_ALLOWED)
    if signer.repository not in policy.allowed_repositories:
        reasons.append(TrustReasonCode.REPOSITORY_NOT_ALLOWED)
    if signer.workflow not in policy.allowed_workflows:
        reasons.append(TrustReasonCode.WORKFLOW_NOT_ALLOWED)
    if not _matches_any(signer.execution_ref, policy.allowed_ref_patterns):
        reasons.append(TrustReasonCode.REF_NOT_ALLOWED)
    if signer.trigger not in policy.allowed_triggers:
        reasons.append(TrustReasonCode.TRIGGER_NOT_ALLOWED)
    if statement.get("predicateType") not in policy.allowed_predicate_types:
        reasons.append(TrustReasonCode.PREDICATE_TYPE_NOT_ALLOWED)
    if artifact.get("artifact_version") not in policy.allowed_artifact_versions:
        reasons.append(TrustReasonCode.ARTIFACT_VERSION_NOT_ALLOWED)
    if (
        policy.require_conformant_status
        and artifact.get("status") != ConformanceStatus.CONFORMANT.value
    ):
        reasons.append(TrustReasonCode.CONFORMANCE_STATUS_NOT_ALLOWED)
    if policy.require_transparency_log and not signer.transparency_log_verified:
        reasons.append(TrustReasonCode.TRANSPARENCY_REQUIRED)

    if policy.require_execution_sha_matches_artifact_checkout:
        checkout_sha = _artifact_checkout_sha(artifact)
        if checkout_sha is None:
            reasons.append(TrustReasonCode.ARTIFACT_CHECKOUT_SHA_MISSING)
        elif signer.execution_sha != checkout_sha:
            reasons.append(TrustReasonCode.EXECUTION_SHA_MISMATCH)

    unique_reasons = tuple(dict.fromkeys(reasons))
    decision = TrustDecision.ACCEPT if not unique_reasons else TrustDecision.REJECT
    return TrustEvaluation(
        decision=decision,
        reason_codes=unique_reasons,
        policy_digest=policy.digest(),
        signer_context_digest=signer.digest(),
    )


def build_svr_statement(
    policy: AttestationTrustPolicy,
    artifact: Mapping[str, Any],
    evaluation: TrustEvaluation,
    *,
    time_created: str,
) -> dict[str, Any]:
    """Build an in-toto Simple Verification Result v0.2 for one trust decision."""

    if not time_created:
        raise ValueError("time_created must be non-empty")
    artifact_digest = _sha256_hex(str(artifact["artifact_digest"]))
    properties = [
        TRUST_ACCEPTED_PROPERTY if evaluation.accepted else TRUST_REJECTED_PROPERTY,
        f"HOWEDO_POLICY_DIGEST={evaluation.policy_digest}",
        f"HOWEDO_SIGNER_CONTEXT_DIGEST={evaluation.signer_context_digest}",
    ]
    properties.extend(f"HOWEDO_REASON={code.value}" for code in evaluation.reason_codes)
    return {
        "_type": SVR_STATEMENT_V1,
        "subject": [
            {
                "name": "howedo.adapter-conformance-artifact.v1",
                "digest": {"sha256": artifact_digest},
            }
        ],
        "predicateType": SVR_PREDICATE_V02,
        "predicate": {
            "verifier": {
                "id": TRUST_VERIFIER_ID,
                "policies": [
                    {
                        "uri": policy.policy_id,
                        "digest": {"sha256": _sha256_hex(policy.digest())},
                    }
                ],
            },
            "timeCreated": time_created,
            "properties": sorted(properties),
        },
    }


def verify_svr_statement(
    policy: AttestationTrustPolicy,
    artifact: Mapping[str, Any],
    statement: Mapping[str, Any],
    signer: SignerVerificationContext,
    svr: Mapping[str, Any],
) -> bool:
    evaluation = evaluate_attestation_trust(policy, artifact, statement, signer)
    try:
        time_created = svr["predicate"]["timeCreated"]
    except (KeyError, TypeError):
        return False
    if not isinstance(time_created, str) or not time_created:
        return False
    return dict(svr) == build_svr_statement(
        policy,
        artifact,
        evaluation,
        time_created=time_created,
    )


def load_trust_policy(record: Mapping[str, Any]) -> AttestationTrustPolicy:
    return AttestationTrustPolicy.from_record(record)


def _artifact_checkout_sha(artifact: Mapping[str, Any]) -> str | None:
    refs = artifact.get("evidence_refs")
    if not isinstance(refs, list):
        return None
    prefix = "git-checkout://sha/"
    values = {
        ref[len(prefix) :]
        for ref in refs
        if isinstance(ref, str) and ref.startswith(prefix)
    }
    if len(values) != 1:
        return None
    return next(iter(values))


def _matches_any(value: str, patterns: Sequence[str]) -> bool:
    return any(_segment_glob_match(value, pattern) for pattern in patterns)


def _segment_glob_match(value: str, pattern: str) -> bool:
    """Match a frozen v1 glob where `*` matches one non-empty slash-delimited segment."""

    expression = re.escape(pattern).replace(r"\*", r"[^/]+")
    return re.fullmatch(expression, value) is not None


def _required_string(record: Mapping[str, Any], key: str) -> str:
    value = record[key]
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _string_tuple(record: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = record[key]
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{key} must be an array of non-empty strings")
    result = tuple(value)
    if tuple(sorted(set(result))) != result:
        raise ValueError(f"{key} must be sorted and unique")
    return result


def _required_bool(record: Mapping[str, Any], key: str) -> bool:
    value = record[key]
    if not isinstance(value, bool):
        raise TypeError(f"{key} must be a boolean")
    return value


def _sha256_hex(value: str) -> str:
    prefix = "sha256:"
    if not value.startswith(prefix):
        raise ValueError("expected sha256-addressed value")
    digest = value[len(prefix) :]
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("invalid sha256 digest")
    return digest


def _digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{sha256(encoded).hexdigest()}"

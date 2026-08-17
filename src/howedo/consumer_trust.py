from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from howedo.protocol import canonical_digest
from howedo.trust_policy import AttestationTrustPolicy, SignerVerificationContext

CONSUMER_TRUST_PROFILE_VERSION = "howedo.consumer-trust-profile.v1"

_PROFILE_KEYS = {
    "allowed_crypto_verifiers",
    "allowed_identity_patterns",
    "allowed_issuers",
    "allowed_ref_patterns",
    "allowed_repositories",
    "allowed_triggers",
    "allowed_workflows",
    "expected_workflow_name",
    "profile_digest",
    "profile_id",
    "profile_version",
    "require_transparency_log",
    "trusted_policies",
    "trusted_svr_verifier_ids",
}


class ConsumerTrustReason(StrEnum):
    POLICY_NOT_TRUSTED = "POLICY_NOT_TRUSTED"
    SVR_VERIFIER_NOT_TRUSTED = "SVR_VERIFIER_NOT_TRUSTED"
    CRYPTO_VERIFIER_NOT_TRUSTED = "CRYPTO_VERIFIER_NOT_TRUSTED"
    ISSUER_NOT_ALLOWED = "ISSUER_NOT_ALLOWED"
    IDENTITY_NOT_ALLOWED = "IDENTITY_NOT_ALLOWED"
    REPOSITORY_NOT_ALLOWED = "REPOSITORY_NOT_ALLOWED"
    WORKFLOW_NOT_ALLOWED = "WORKFLOW_NOT_ALLOWED"
    REF_NOT_ALLOWED = "REF_NOT_ALLOWED"
    TRIGGER_NOT_ALLOWED = "TRIGGER_NOT_ALLOWED"
    TRANSPARENCY_REQUIRED = "TRANSPARENCY_REQUIRED"


@dataclass(frozen=True, slots=True, order=True)
class TrustedPolicyRef:
    policy_id: str
    policy_digest: str

    def __post_init__(self) -> None:
        if not self.policy_id:
            raise ValueError("trusted policy id must be non-empty")
        if not _is_sha256_digest(self.policy_digest):
            raise ValueError("trusted policy digest must be sha256:<64 lowercase hex>")

    def canonical(self) -> dict[str, str]:
        return {"policy_digest": self.policy_digest, "policy_id": self.policy_id}


@dataclass(frozen=True, slots=True)
class ConsumerTrustProfile:
    profile_id: str
    expected_workflow_name: str
    trusted_svr_verifier_ids: tuple[str, ...]
    trusted_policies: tuple[TrustedPolicyRef, ...]
    allowed_crypto_verifiers: tuple[str, ...]
    allowed_issuers: tuple[str, ...]
    allowed_identity_patterns: tuple[str, ...]
    allowed_repositories: tuple[str, ...]
    allowed_workflows: tuple[str, ...]
    allowed_ref_patterns: tuple[str, ...]
    allowed_triggers: tuple[str, ...]
    require_transparency_log: bool
    profile_version: str = CONSUMER_TRUST_PROFILE_VERSION

    def __post_init__(self) -> None:
        if self.profile_version != CONSUMER_TRUST_PROFILE_VERSION:
            raise ValueError("unsupported consumer trust profile version")
        if not self.profile_id:
            raise ValueError("profile_id must be non-empty")
        if not self.expected_workflow_name:
            raise ValueError("expected_workflow_name must be non-empty")
        for values in (
            self.trusted_svr_verifier_ids,
            self.allowed_crypto_verifiers,
            self.allowed_issuers,
            self.allowed_identity_patterns,
            self.allowed_repositories,
            self.allowed_workflows,
            self.allowed_ref_patterns,
            self.allowed_triggers,
        ):
            _require_sorted_unique_strings(values)
        if not self.trusted_policies:
            raise ValueError("trusted_policies must be non-empty")
        if tuple(sorted(set(self.trusted_policies))) != self.trusted_policies:
            raise ValueError("trusted_policies must be sorted and unique")

    def canonical(self) -> dict[str, Any]:
        return {
            "allowed_crypto_verifiers": list(self.allowed_crypto_verifiers),
            "allowed_identity_patterns": list(self.allowed_identity_patterns),
            "allowed_issuers": list(self.allowed_issuers),
            "allowed_ref_patterns": list(self.allowed_ref_patterns),
            "allowed_repositories": list(self.allowed_repositories),
            "allowed_triggers": list(self.allowed_triggers),
            "allowed_workflows": list(self.allowed_workflows),
            "expected_workflow_name": self.expected_workflow_name,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "require_transparency_log": self.require_transparency_log,
            "trusted_policies": [item.canonical() for item in self.trusted_policies],
            "trusted_svr_verifier_ids": list(self.trusted_svr_verifier_ids),
        }

    def digest(self) -> str:
        return canonical_digest(self.canonical())

    def record(self) -> dict[str, Any]:
        record = self.canonical()
        record["profile_digest"] = self.digest()
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ConsumerTrustProfile:
        if set(record) != _PROFILE_KEYS:
            raise ValueError("consumer trust profile record shape mismatch")
        raw_policies = record.get("trusted_policies")
        if not isinstance(raw_policies, list):
            raise TypeError("trusted_policies must be a list")
        policies: list[TrustedPolicyRef] = []
        for raw in raw_policies:
            if not isinstance(raw, Mapping) or set(raw) != {"policy_id", "policy_digest"}:
                raise ValueError("trusted policy reference shape mismatch")
            policies.append(
                TrustedPolicyRef(
                    policy_id=_required_string(raw, "policy_id"),
                    policy_digest=_required_string(raw, "policy_digest"),
                )
            )
        profile = cls(
            profile_id=_required_string(record, "profile_id"),
            expected_workflow_name=_required_string(record, "expected_workflow_name"),
            trusted_svr_verifier_ids=_string_tuple(record, "trusted_svr_verifier_ids"),
            trusted_policies=tuple(policies),
            allowed_crypto_verifiers=_string_tuple(record, "allowed_crypto_verifiers"),
            allowed_issuers=_string_tuple(record, "allowed_issuers"),
            allowed_identity_patterns=_string_tuple(record, "allowed_identity_patterns"),
            allowed_repositories=_string_tuple(record, "allowed_repositories"),
            allowed_workflows=_string_tuple(record, "allowed_workflows"),
            allowed_ref_patterns=_string_tuple(record, "allowed_ref_patterns"),
            allowed_triggers=_string_tuple(record, "allowed_triggers"),
            require_transparency_log=_required_bool(record, "require_transparency_log"),
            profile_version=_required_string(record, "profile_version"),
        )
        if record.get("profile_digest") != profile.digest():
            raise ValueError("consumer trust profile digest mismatch")
        return profile


@dataclass(frozen=True, slots=True)
class ConsumerTrustEvaluation:
    accepted: bool
    reason_codes: tuple[ConsumerTrustReason, ...]
    profile_digest: str


def evaluate_consumer_expectations(
    profile: ConsumerTrustProfile,
    policy: AttestationTrustPolicy,
    svr: Mapping[str, Any],
    signer: SignerVerificationContext,
) -> ConsumerTrustEvaluation:
    reasons: list[ConsumerTrustReason] = []
    policy_ref = TrustedPolicyRef(policy_id=policy.policy_id, policy_digest=policy.digest())
    if policy_ref not in profile.trusted_policies:
        reasons.append(ConsumerTrustReason.POLICY_NOT_TRUSTED)
    if _svr_verifier_id(svr) not in profile.trusted_svr_verifier_ids:
        reasons.append(ConsumerTrustReason.SVR_VERIFIER_NOT_TRUSTED)
    if signer.verifier_id not in profile.allowed_crypto_verifiers:
        reasons.append(ConsumerTrustReason.CRYPTO_VERIFIER_NOT_TRUSTED)
    if signer.issuer not in profile.allowed_issuers:
        reasons.append(ConsumerTrustReason.ISSUER_NOT_ALLOWED)
    if not _matches_any(signer.identity, profile.allowed_identity_patterns):
        reasons.append(ConsumerTrustReason.IDENTITY_NOT_ALLOWED)
    if signer.repository not in profile.allowed_repositories:
        reasons.append(ConsumerTrustReason.REPOSITORY_NOT_ALLOWED)
    if signer.workflow not in profile.allowed_workflows:
        reasons.append(ConsumerTrustReason.WORKFLOW_NOT_ALLOWED)
    if not _matches_any(signer.execution_ref, profile.allowed_ref_patterns):
        reasons.append(ConsumerTrustReason.REF_NOT_ALLOWED)
    if signer.trigger not in profile.allowed_triggers:
        reasons.append(ConsumerTrustReason.TRIGGER_NOT_ALLOWED)
    if profile.require_transparency_log and not signer.transparency_log_verified:
        reasons.append(ConsumerTrustReason.TRANSPARENCY_REQUIRED)
    unique = tuple(dict.fromkeys(reasons))
    return ConsumerTrustEvaluation(
        accepted=not unique,
        reason_codes=unique,
        profile_digest=profile.digest(),
    )


def load_consumer_trust_profile(record: Mapping[str, Any]) -> ConsumerTrustProfile:
    return ConsumerTrustProfile.from_record(record)


def _svr_verifier_id(svr: Mapping[str, Any]) -> str | None:
    try:
        value = svr["predicate"]["verifier"]["id"]
    except (KeyError, TypeError):
        return None
    return value if isinstance(value, str) and value else None


def _matches_any(value: str, patterns: Sequence[str]) -> bool:
    return any(_segment_glob_match(value, pattern) for pattern in patterns)


def _segment_glob_match(value: str, pattern: str) -> bool:
    parts = pattern.split("*")
    regex = "[^/]*".join(re.escape(part) for part in parts)
    return re.fullmatch(regex, value) is not None


def _require_sorted_unique_strings(values: tuple[str, ...]) -> None:
    if not values or tuple(sorted(set(values))) != values:
        raise ValueError("consumer trust allow-lists must be non-empty, sorted, and unique")
    if any(not value for value in values):
        raise ValueError("consumer trust allow-list entries must be non-empty")


def _string_tuple(record: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = record.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{key} must be a list of strings")
    return tuple(value)


def _required_string(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{key} must be a non-empty string")
    return value


def _required_bool(record: Mapping[str, Any], key: str) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise TypeError(f"{key} must be a boolean")
    return value


def _is_sha256_digest(value: str) -> bool:
    return re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None

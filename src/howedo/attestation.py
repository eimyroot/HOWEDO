from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from howedo.adapter_certification import verify_conformance_record

IN_TOTO_STATEMENT_V1 = "https://in-toto.io/Statement/v1"
CONFORMANCE_PREDICATE_V1 = (
    "https://github.com/nulleimy/HOWEDO/attestations/adapter-conformance/v1"
)
CONFORMANCE_SUBJECT_NAME = "howedo.adapter-conformance-artifact.v1"
_STATEMENT_KEYS = {"_type", "subject", "predicateType", "predicate"}


class AttestationVerificationCode(StrEnum):
    ARTIFACT_INVALID = "ARTIFACT_INVALID"
    STATEMENT_TYPE_MISMATCH = "STATEMENT_TYPE_MISMATCH"
    SUBJECT_SET_MISMATCH = "SUBJECT_SET_MISMATCH"
    SUBJECT_DIGEST_MISMATCH = "SUBJECT_DIGEST_MISMATCH"
    PREDICATE_TYPE_MISMATCH = "PREDICATE_TYPE_MISMATCH"
    PREDICATE_MISMATCH = "PREDICATE_MISMATCH"
    INVALID_STATEMENT = "INVALID_STATEMENT"


@dataclass(frozen=True, slots=True)
class AttestationVerification:
    valid: bool
    reason_codes: tuple[AttestationVerificationCode, ...]


def build_conformance_statement(record: Mapping[str, Any]) -> dict[str, Any]:
    """Build an in-toto Statement/v1 bound to one valid R9 conformance artifact."""

    verification = verify_conformance_record(record)
    if not verification.valid:
        detail = ",".join(code.value for code in verification.reason_codes)
        raise ValueError(f"cannot attest invalid conformance artifact: {detail}")

    artifact_digest = _sha256_hex(str(record["artifact_digest"]))
    return {
        "_type": IN_TOTO_STATEMENT_V1,
        "subject": [
            {
                "name": CONFORMANCE_SUBJECT_NAME,
                "digest": {"sha256": artifact_digest},
            }
        ],
        "predicateType": CONFORMANCE_PREDICATE_V1,
        "predicate": _predicate(record),
    }


def verify_conformance_statement(
    record: Mapping[str, Any],
    statement: Mapping[str, Any],
) -> AttestationVerification:
    """Verify semantic binding between a R9 artifact and an in-toto Statement/v1.

    This function intentionally does not verify a cryptographic signature. R10
    composes this semantic check with an external Sigstore bundle verification.
    """

    reasons: list[AttestationVerificationCode] = []
    artifact_verification = verify_conformance_record(record)
    if not artifact_verification.valid:
        reasons.append(AttestationVerificationCode.ARTIFACT_INVALID)

    try:
        if set(statement) != _STATEMENT_KEYS:
            reasons.append(AttestationVerificationCode.INVALID_STATEMENT)

        if statement.get("_type") != IN_TOTO_STATEMENT_V1:
            reasons.append(AttestationVerificationCode.STATEMENT_TYPE_MISMATCH)

        subject = statement["subject"]
        expected_subject = [
            {
                "name": CONFORMANCE_SUBJECT_NAME,
                "digest": {"sha256": _sha256_hex(str(record["artifact_digest"]))},
            }
        ]
        if not isinstance(subject, list) or len(subject) != 1:
            reasons.append(AttestationVerificationCode.SUBJECT_SET_MISMATCH)
        elif subject != expected_subject:
            reasons.append(AttestationVerificationCode.SUBJECT_DIGEST_MISMATCH)

        if statement.get("predicateType") != CONFORMANCE_PREDICATE_V1:
            reasons.append(AttestationVerificationCode.PREDICATE_TYPE_MISMATCH)

        predicate = statement["predicate"]
        if not isinstance(predicate, Mapping) or dict(predicate) != _predicate(record):
            reasons.append(AttestationVerificationCode.PREDICATE_MISMATCH)
    except (KeyError, TypeError, ValueError):
        reasons.append(AttestationVerificationCode.INVALID_STATEMENT)

    unique_reasons = tuple(dict.fromkeys(reasons))
    return AttestationVerification(valid=not unique_reasons, reason_codes=unique_reasons)


def write_conformance_statement(
    record: Mapping[str, Any],
    path: str | Path,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(build_conformance_statement(record), sort_keys=True, separators=(",", ":"))
        + "\n"
    )
    return target


def _predicate(record: Mapping[str, Any]) -> dict[str, Any]:
    manifest = record["manifest"]
    checks = record["checks"]
    if not isinstance(manifest, Mapping) or not isinstance(checks, list):
        raise TypeError("invalid conformance artifact structure")

    passed_count = sum(item["passed"] is True for item in checks)
    return {
        "adapter": {
            "adapterId": manifest["adapter_id"],
            "adapterVersion": manifest["adapter_version"],
            "manifestDigest": record["manifest_digest"],
            "runtimeFamily": manifest["runtime_family"],
        },
        "artifactVersion": record["artifact_version"],
        "conformance": {
            "checkCount": len(checks),
            "passedCount": passed_count,
            "status": record["status"],
        },
        "evidenceRefs": list(record["evidence_refs"]),
    }


def _sha256_hex(value: str) -> str:
    prefix = "sha256:"
    if not value.startswith(prefix):
        raise ValueError("expected sha256-addressed value")
    digest = value[len(prefix) :]
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("invalid sha256 digest")
    return digest

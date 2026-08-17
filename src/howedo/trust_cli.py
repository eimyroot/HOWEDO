from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from howedo.sigstore_trust import SigstoreGithubClaims, verify_sigstore_github_bundle
from howedo.trust_policy import (
    SignerVerificationContext,
    build_svr_statement,
    evaluate_attestation_trust,
    load_trust_policy,
    verify_svr_statement,
)


def _load_object(path: str) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, Mapping):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _write_json(path: str, value: Mapping[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    return target


def sigstore_main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify a signed HOWEDO conformance attestation through Cosign, evaluate "
            "a deterministic HOWEDO trust policy, and emit an in-toto SVR v0.2 receipt."
        )
    )
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--statement", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--identity", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--execution-sha", required=True)
    parser.add_argument("--execution-ref", required=True)
    parser.add_argument("--trigger", required=True)
    parser.add_argument("--time-created", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--cosign", default="cosign")
    args = parser.parse_args()

    try:
        artifact = _load_object(args.artifact)
        statement = _load_object(args.statement)
        policy_record = _load_object(args.policy)
        policy = load_trust_policy(policy_record)

        claims = SigstoreGithubClaims(
            identity=args.identity,
            issuer=args.issuer,
            repository=args.repository,
            workflow_sha=args.execution_sha,
            workflow_ref=args.execution_ref,
            workflow_trigger=args.trigger,
        )
        crypto = verify_sigstore_github_bundle(
            args.statement,
            args.bundle,
            claims,
            cosign_executable=args.cosign,
        )
        evidence_refs = tuple(sorted(set(args.evidence_ref)))
        signer = SignerVerificationContext(
            verifier_id=crypto.verifier_id,
            cryptographically_verified=crypto.verified,
            issuer=args.issuer,
            identity=args.identity,
            repository=args.repository,
            workflow=args.workflow,
            execution_sha=args.execution_sha,
            execution_ref=args.execution_ref,
            trigger=args.trigger,
            transparency_log_verified=crypto.verified,
            evidence_refs=evidence_refs,
        )
        evaluation = evaluate_attestation_trust(policy, artifact, statement, signer)
        svr = build_svr_statement(
            policy,
            artifact,
            evaluation,
            time_created=args.time_created,
        )
        if not verify_svr_statement(policy, artifact, statement, signer, svr):
            raise ValueError("generated SVR failed deterministic replay")
        target = _write_json(args.output, svr)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"HOWEDO_TRUST_POLICY=FAIL:{exc}")
        return 1

    if evaluation.accepted:
        print(f"HOWEDO_TRUST_POLICY=ACCEPT:{target}")
        return 0

    reasons = ",".join(code.value for code in evaluation.reason_codes)
    detail = crypto.detail.replace("\n", " ")[:500]
    if detail:
        print(f"HOWEDO_TRUST_CRYPTO_DETAIL={detail}")
    print(f"HOWEDO_TRUST_POLICY=REJECT:{reasons}:{target}")
    return 1

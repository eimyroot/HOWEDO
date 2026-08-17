from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from howedo.certification_package import (
    CertificationSigner,
    build_certification_package,
    verify_certification_package,
)
from howedo.consumer_trust import load_consumer_trust_profile


def _load_object(path: str | Path) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, Mapping):
        raise TypeError(f"expected JSON object: {path}")
    return value


def build_main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a portable HOWEDO R12 consumer certification package."
    )
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--statement", required=True)
    parser.add_argument("--statement-bundle", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--svr", required=True)
    parser.add_argument("--svr-bundle", required=True)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--identity", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--execution-sha", required=True)
    parser.add_argument("--execution-ref", required=True)
    parser.add_argument("--trigger", required=True)
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        manifest = build_certification_package(
            artifact_path=args.artifact,
            statement_path=args.statement,
            statement_bundle_path=args.statement_bundle,
            policy_path=args.policy,
            svr_path=args.svr,
            svr_bundle_path=args.svr_bundle,
            signer=CertificationSigner(
                issuer=args.issuer,
                identity=args.identity,
                repository=args.repository,
                workflow=args.workflow,
                execution_sha=args.execution_sha,
                execution_ref=args.execution_ref,
                trigger=args.trigger,
                evidence_refs=tuple(sorted(set(args.evidence_ref))),
            ),
            output_dir=args.output_dir,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"HOWEDO_CERTIFICATION_PACKAGE=FAIL:{exc}")
        return 1

    print(f"HOWEDO_CERTIFICATION_PACKAGE=BUILT:{manifest.digest()}:{args.output_dir}")
    return 0


def verify_main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Independently replay a HOWEDO R9-R11 certification package against a "
            "consumer-pinned trust profile."
        )
    )
    parser.add_argument("package_dir")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--expected-profile-digest", required=True)
    parser.add_argument("--cosign", default="cosign")
    args = parser.parse_args()

    try:
        profile = load_consumer_trust_profile(_load_object(args.profile))
        result = verify_certification_package(
            args.package_dir,
            profile,
            cosign_executable=args.cosign,
            expected_profile_digest=args.expected_profile_digest,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"HOWEDO_CONSUMER_VERIFICATION=FAIL:{exc}")
        return 1

    if result.accepted:
        print(
            "HOWEDO_CONSUMER_VERIFICATION=ACCEPT:"
            f"{result.package_digest}:{result.profile_digest}"
        )
        return 0

    reasons = ",".join(code.value for code in result.reason_codes)
    print(
        "HOWEDO_CONSUMER_VERIFICATION=REJECT:"
        f"{reasons}:{result.package_digest}:{result.profile_digest}"
    )
    return 1

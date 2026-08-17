from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from howedo.trust_publication import (
    build_trust_root_publication_manifest,
    load_publication_policy,
    verify_trust_root_publication,
)


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise argparse.ArgumentTypeError("timestamp must be timezone-aware UTC")
    return parsed.astimezone(UTC).replace(microsecond=0)


def build_main() -> int:
    parser = argparse.ArgumentParser(description="Build a HOWEDO TUF trust-root publication manifest")
    parser.add_argument("--root", action="append", required=True, dest="roots")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--publication-id", required=True)
    parser.add_argument("--metadata-base-url", required=True)
    parser.add_argument("--target-base-url", required=True)
    parser.add_argument("--target-path", required=True)
    parser.add_argument("--consumer-profile-id", required=True)
    parser.add_argument("--verified-at", type=_parse_time)
    args = parser.parse_args()

    root_history = tuple(Path(path).read_bytes() for path in args.roots)
    policy_record = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    if not isinstance(policy_record, dict):
        raise SystemExit("policy must contain a JSON object")
    policy = load_publication_policy(policy_record)
    verified_at = args.verified_at or datetime.now(UTC).replace(microsecond=0)
    manifest = build_trust_root_publication_manifest(
        root_history=root_history,
        policy=policy,
        publication_id=args.publication_id,
        metadata_base_url=args.metadata_base_url,
        target_base_url=args.target_base_url,
        target_path=args.target_path,
        consumer_profile_id=args.consumer_profile_id,
        verified_at=verified_at,
    )
    Path(args.output).write_text(
        json.dumps(manifest.record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"HOWEDO_TRUST_ROOT_PUBLICATION_MANIFEST={manifest.digest()}")
    return 0


def verify_main() -> int:
    parser = argparse.ArgumentParser(description="Verify a HOWEDO TUF trust-root publication manifest")
    parser.add_argument("--root", action="append", required=True, dest="roots")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--policy", required=True)
    args = parser.parse_args()

    root_history = tuple(Path(path).read_bytes() for path in args.roots)
    manifest_record = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    policy_record = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    if not isinstance(manifest_record, dict) or not isinstance(policy_record, dict):
        raise SystemExit("manifest and policy must contain JSON objects")
    policy = load_publication_policy(policy_record)
    manifest = verify_trust_root_publication(
        root_history=root_history,
        manifest_record=manifest_record,
        policy=policy,
    )
    print(f"HOWEDO_TRUST_ROOT_PUBLICATION_VERIFIED={manifest.digest()}")
    return 0

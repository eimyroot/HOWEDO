from __future__ import annotations

import argparse
import json
from pathlib import Path

from howedo.trust_distribution import (
    DEFAULT_CONSUMER_TRUST_TARGET,
    fetch_consumer_trust_profile,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch a HOWEDO consumer trust profile through a TUF trust root."
    )
    parser.add_argument("--bootstrap-root", required=True, type=Path)
    parser.add_argument("--metadata-dir", required=True, type=Path)
    parser.add_argument("--metadata-base-url", required=True)
    parser.add_argument("--target-dir", required=True, type=Path)
    parser.add_argument("--target-base-url", required=True)
    parser.add_argument("--target-path", default=DEFAULT_CONSUMER_TRUST_TARGET)
    parser.add_argument("--expected-profile-id")
    parser.add_argument("--profile-output", required=True, type=Path)
    parser.add_argument("--receipt-output", required=True, type=Path)
    args = parser.parse_args()

    update = fetch_consumer_trust_profile(
        bootstrap_root=args.bootstrap_root.read_bytes(),
        metadata_dir=args.metadata_dir,
        metadata_base_url=args.metadata_base_url,
        target_dir=args.target_dir,
        target_base_url=args.target_base_url,
        target_path=args.target_path,
        expected_profile_id=args.expected_profile_id,
    )
    args.profile_output.parent.mkdir(parents=True, exist_ok=True)
    args.receipt_output.parent.mkdir(parents=True, exist_ok=True)
    args.profile_output.write_text(
        json.dumps(update.profile.record(), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    args.receipt_output.write_text(
        json.dumps(update.receipt.record(), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"HOWEDO_TRUST_PROFILE_DIGEST={update.profile.digest()}")
    print(f"HOWEDO_TUF_TRUSTED_ROOT_VERSION={update.receipt.trusted_root_version}")
    print(f"HOWEDO_TRUST_DISTRIBUTION_RECEIPT={update.receipt.digest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

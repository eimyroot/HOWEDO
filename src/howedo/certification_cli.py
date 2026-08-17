from __future__ import annotations

import argparse
import json
from pathlib import Path

from howedo.adapter_certification import verify_conformance_record


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="howedo-verify-conformance",
        description="Verify a HOWEDO adapter conformance artifact without runtime vendor SDKs.",
    )
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()

    record = json.loads(args.artifact.read_text())
    verification = verify_conformance_record(record)
    payload = {
        "valid": verification.valid,
        "reason_codes": [code.value for code in verification.reason_codes],
    }
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0 if verification.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

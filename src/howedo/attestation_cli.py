from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from howedo.attestation import verify_conformance_statement, write_conformance_statement


def _load_object(path: str) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, Mapping):
        raise TypeError(f"expected JSON object: {path}")
    return value


def build_main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an in-toto Statement/v1 bound to a HOWEDO R9 conformance artifact."
    )
    parser.add_argument("artifact")
    parser.add_argument("output")
    args = parser.parse_args()

    try:
        record = _load_object(args.artifact)
        target = write_conformance_statement(record, args.output)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"HOWEDO_ATTESTATION_BUILD=FAIL:{exc}")
        return 1

    print(f"HOWEDO_ATTESTATION_BUILD=PASS:{target}")
    return 0


def verify_main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify HOWEDO semantic binding between a R9 artifact and R10 statement."
    )
    parser.add_argument("artifact")
    parser.add_argument("statement")
    args = parser.parse_args()

    try:
        record = _load_object(args.artifact)
        statement = _load_object(args.statement)
        verification = verify_conformance_statement(record, statement)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"HOWEDO_ATTESTATION_BINDING=FAIL:{exc}")
        return 1

    if verification.valid:
        print("HOWEDO_ATTESTATION_BINDING=PASS")
        return 0

    reasons = ",".join(code.value for code in verification.reason_codes)
    print(f"HOWEDO_ATTESTATION_BINDING=FAIL:{reasons}")
    return 1

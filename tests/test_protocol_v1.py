import json
from pathlib import Path

import pytest

from howedo import PROTOCOL_VERSION, WitnessRecord, canonical_digest, canonical_json


SCHEMA_DIR = Path(__file__).parents[1] / "schemas" / "v1"


def test_protocol_version_is_stable_v1() -> None:
    assert PROTOCOL_VERSION == "howedo.protocol.v1"


def test_canonical_json_and_digest_ignore_mapping_order() -> None:
    left = {"b": 2, "a": 1}
    right = {"a": 1, "b": 2}

    assert canonical_json(left) == canonical_json(right)
    assert canonical_digest(left) == canonical_digest(right)


def test_witness_record_rejects_forged_digest() -> None:
    with pytest.raises(ValueError, match="does not match"):
        WitnessRecord(
            witness_digest="sha256:" + "0" * 64,
            witness_kind="continuity",
            payload={"action": "CONTINUE"},
        )


def test_v1_schema_files_are_valid_json_with_unique_urn_ids() -> None:
    schema_files = sorted(SCHEMA_DIR.glob("*.schema.json"))
    assert {path.name for path in schema_files} == {
        "continuity-event.schema.json",
        "continuity-snapshot.schema.json",
        "recovery-checkpoint.schema.json",
        "resource-revision.schema.json",
        "witness-record.schema.json",
    }

    ids = []
    for path in schema_files:
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].startswith("urn:howedo:protocol:v1:")
        ids.append(schema["$id"])

    assert len(ids) == len(set(ids))

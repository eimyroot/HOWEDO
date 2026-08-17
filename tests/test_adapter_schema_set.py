from pathlib import Path


def test_runtime_adapter_v1_schema_set_is_frozen() -> None:
    expected = {
        "adapter-manifest.schema.json",
        "failure.schema.json",
        "runtime-identity.schema.json",
    }
    actual = {path.name for path in Path("schemas/runtime-adapter-v1").glob("*.json")}
    assert actual == expected

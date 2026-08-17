def test_adapter_sdk_imports_without_optional_runtimes() -> None:
    import howedo.adapter_sdk as sdk

    assert sdk.ADAPTER_CONTRACT_VERSION == "howedo.runtime-adapter.v1"

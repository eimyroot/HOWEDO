from __future__ import annotations

import asyncio
import importlib.util

import pytest

from howedo.adapter_contract import (
    AdapterBinding,
    AdapterContractError,
    AdapterFailureCode,
    RuntimeIdentity,
)


def test_langgraph_v1_bridge_is_optional_and_normalizes_protocol_failure() -> None:
    if importlib.util.find_spec("langgraph") is None:
        pytest.skip("LangGraph optional extra not installed")
    from howedo.adapters.langgraph_v1 import LangGraphRuntimeAdapterV1

    adapter = LangGraphRuntimeAdapterV1()
    manifest = adapter.manifest()
    assert manifest.runtime_family == "langgraph"

    binding = AdapterBinding(
        identity=RuntimeIdentity(
            runtime_family="langgraph",
            namespace="default",
            execution_id="thread-1",
            execution_revision="checkpoint-1",
        ),
        recovery_binding=object(),
        adapter_manifest_digest=manifest.digest(),
    )

    async def scenario() -> None:
        with pytest.raises(AdapterContractError) as exc_info:
            await adapter.validate_resume(object(), binding, current_heads={})
        assert exc_info.value.code is AdapterFailureCode.PROTOCOL_VIOLATION

    asyncio.run(scenario())


def test_temporal_v1_bridge_is_optional_and_normalizes_protocol_failure() -> None:
    if importlib.util.find_spec("temporalio") is None:
        pytest.skip("Temporal optional extra not installed")
    from howedo.adapters.temporal_v1 import TemporalRuntimeAdapterV1

    adapter = TemporalRuntimeAdapterV1()
    manifest = adapter.manifest()
    assert manifest.runtime_family == "temporal"

    binding = AdapterBinding(
        identity=RuntimeIdentity(
            runtime_family="temporal",
            namespace="default",
            execution_id="workflow-1",
            execution_revision="run-1",
        ),
        recovery_binding=object(),
        adapter_manifest_digest=manifest.digest(),
    )

    async def scenario() -> None:
        with pytest.raises(AdapterContractError) as exc_info:
            await adapter.validate_resume(object(), binding, current_heads={})
        assert exc_info.value.code is AdapterFailureCode.PROTOCOL_VIOLATION

    asyncio.run(scenario())

from __future__ import annotations

import importlib.util

import pytest


def test_langgraph_v1_bridge_is_optional() -> None:
    if importlib.util.find_spec("langgraph") is None:
        pytest.skip("LangGraph optional extra not installed")
    from howedo.adapters.langgraph_v1 import LangGraphRuntimeAdapterV1

    manifest = LangGraphRuntimeAdapterV1().manifest()
    assert manifest.runtime_family == "langgraph"


def test_temporal_v1_bridge_is_optional() -> None:
    if importlib.util.find_spec("temporalio") is None:
        pytest.skip("Temporal optional extra not installed")
    from howedo.adapters.temporal_v1 import TemporalRuntimeAdapterV1

    manifest = TemporalRuntimeAdapterV1().manifest()
    assert manifest.runtime_family == "temporal"

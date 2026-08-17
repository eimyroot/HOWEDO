from __future__ import annotations

import asyncio
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, TypedDict

import pytest

pytest.importorskip("langgraph")

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from howedo.adapter_conformance import AdapterConformanceSuite
from howedo.adapters.langgraph_v1 import LangGraphRuntimeAdapterV1
from howedo.domain import ResourceRevision


class ApprovalState(TypedDict):
    approved: bool | None


def revision(resource_id: str, version: str) -> ResourceRevision:
    return ResourceRevision(
        resource_id=resource_id,
        revision=version,
        digest=f"sha256:{sha256(version.encode()).hexdigest()}",
    )


def build_interrupted_graph(thread_id: str):
    def approval_node(state: ApprovalState) -> dict[str, bool]:
        approved = interrupt("approve?")
        return {"approved": bool(approved)}

    builder = StateGraph(ApprovalState)
    builder.add_node("approval", approval_node)
    builder.add_edge(START, "approval")
    builder.add_edge("approval", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"approved": None}, config=config)
    assert "__interrupt__" in result
    return graph, config


@dataclass
class LangGraphFixture:
    runtime: Any
    target: Any
    resources: tuple[ResourceRevision, ...]
    current_heads: dict[str, ResourceRevision]
    continuation: Any = Command(resume=True)

    async def changed_heads(self) -> dict[str, ResourceRevision]:
        return {"policy://deploy": revision("policy://deploy", "2")}

    async def verify_continuation(self, result: Any) -> bool:
        return bool(result["approved"] is True)


def test_langgraph_reference_bridge_passes_runtime_adapter_v1() -> None:
    async def scenario() -> None:
        graph, config = build_interrupted_graph("r8-contract")
        policy = revision("policy://deploy", "1")
        fixture = LangGraphFixture(
            runtime=graph,
            target=config,
            resources=(policy,),
            current_heads={policy.resource_id: policy},
        )
        results = await AdapterConformanceSuite().run(
            LangGraphRuntimeAdapterV1(),
            fixture,
        )
        AdapterConformanceSuite.assert_passed(results)
        assert next(item for item in results if item.check == "continue-after-recover").passed

    asyncio.run(scenario())

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, TypedDict

import pytest

pytest.importorskip("langgraph")

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from howedo.adapter_certification import (
    AdapterConformanceArtifactBuilder,
    ConformanceStatus,
    verify_conformance_record,
)
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
    continuation: Any

    async def changed_heads(self) -> dict[str, ResourceRevision]:
        return {"policy://deploy": revision("policy://deploy", "2")}

    async def verify_continuation(self, result: Any) -> bool:
        return bool(result["approved"] is True)


def evidence_refs() -> tuple[str, ...]:
    refs = ["test://langgraph-real-checkpoint"]
    if run_id := os.environ.get("GITHUB_RUN_ID"):
        refs.append(f"github-actions://run/{run_id}")
    if source_sha := os.environ.get("HOWEDO_SOURCE_SHA"):
        refs.append(f"git-source://sha/{source_sha}")
    if checkout_sha := os.environ.get("GITHUB_SHA"):
        refs.append(f"git-checkout://sha/{checkout_sha}")
    return tuple(sorted(refs))


def test_langgraph_reference_bridge_issues_conformance_artifact() -> None:
    async def scenario() -> None:
        graph, config = build_interrupted_graph("r9-conformance-artifact")
        policy = revision("policy://deploy", "1")
        fixture = LangGraphFixture(
            runtime=graph,
            target=config,
            resources=(policy,),
            current_heads={policy.resource_id: policy},
            continuation=Command(resume=True),
        )
        artifact = await AdapterConformanceArtifactBuilder().build(
            LangGraphRuntimeAdapterV1(),
            fixture,
            evidence_refs=evidence_refs(),
        )
        assert artifact.status is ConformanceStatus.CONFORMANT
        assert verify_conformance_record(artifact.record()).valid
        assert artifact.manifest.runtime_family == "langgraph"

        output_dir = os.environ.get("HOWEDO_CONFORMANCE_ARTIFACT_DIR")
        if output_dir:
            version = artifact.environment.python_version.replace(".", "")
            artifact.write(Path(output_dir) / f"langgraph-py{version}.json")

    asyncio.run(scenario())

from __future__ import annotations

from hashlib import sha256
from typing import TypedDict

import pytest

pytest.importorskip("langgraph")

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from howedo import ContinuityAction, ResourceRevision
from howedo.adapters.langgraph import (
    RUNTIME_RESOURCE_ID,
    LangGraphCheckpointRef,
    LangGraphRecoveryBinding,
    LangGraphRuntimeAdapter,
    ResumeBlocked,
)


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


def test_capture_binds_exact_langgraph_checkpoint_and_runtime_revision() -> None:
    graph, config = build_interrupted_graph("capture-thread")
    policy = revision("policy://deploy", "1")
    adapter = LangGraphRuntimeAdapter()

    binding = adapter.capture(graph, config, resources=(policy,))

    assert binding.checkpoint.thread_id == "capture-thread"
    assert binding.checkpoint.checkpoint_id
    resources = binding.recovery_checkpoint.snapshot.by_resource()
    assert resources["policy://deploy"] == policy
    assert resources[RUNTIME_RESOURCE_ID] == adapter.runtime_revision()


def test_valid_checkpoint_resumes_real_langgraph_interrupt() -> None:
    graph, config = build_interrupted_graph("resume-thread")
    policy = revision("policy://deploy", "1")
    adapter = LangGraphRuntimeAdapter()
    binding = adapter.capture(graph, config, resources=(policy,))

    decision = adapter.validate_resume(
        graph,
        binding,
        current_heads={policy.resource_id: policy},
    )
    assert decision.action is ContinuityAction.RECOVER

    result = adapter.resume_interrupt(
        graph,
        binding,
        True,
        current_heads={policy.resource_id: policy},
    )
    assert result["approved"] is True


def test_changed_reality_blocks_langgraph_before_resume() -> None:
    graph, config = build_interrupted_graph("blocked-thread")
    policy_v1 = revision("policy://deploy", "1")
    policy_v2 = revision("policy://deploy", "2")
    adapter = LangGraphRuntimeAdapter()
    binding = adapter.capture(graph, config, resources=(policy_v1,))

    with pytest.raises(ResumeBlocked) as exc_info:
        adapter.resume_interrupt(
            graph,
            binding,
            True,
            current_heads={policy_v2.resource_id: policy_v2},
        )

    assert exc_info.value.decision.action is ContinuityAction.REVALIDATE
    still_paused = graph.get_state(binding.checkpoint.config())
    assert still_paused.interrupts


def test_binding_rejects_digest_forgery() -> None:
    graph, config = build_interrupted_graph("forge-thread")
    policy = revision("policy://deploy", "1")
    adapter = LangGraphRuntimeAdapter()
    binding = adapter.capture(graph, config, resources=(policy,))

    with pytest.raises(ValueError, match="digest mismatch"):
        LangGraphRecoveryBinding(
            checkpoint=binding.checkpoint,
            recovery_checkpoint=binding.recovery_checkpoint,
            binding_digest="sha256:" + "0" * 64,
        )


def test_checkpoint_ref_config_preserves_namespace() -> None:
    ref = LangGraphCheckpointRef(
        thread_id="thread-1",
        checkpoint_id="checkpoint-1",
        checkpoint_ns="subgraph:one",
    )

    assert ref.config() == {
        "configurable": {
            "thread_id": "thread-1",
            "checkpoint_id": "checkpoint-1",
            "checkpoint_ns": "subgraph:one",
        }
    }

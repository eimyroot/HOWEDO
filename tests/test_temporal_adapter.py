from __future__ import annotations

import asyncio
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

import pytest

pytest.importorskip("temporalio")
from temporalio.client import WorkflowExecutionStatus

from howedo import ContinuityAction, ResourceRevision
from howedo.adapters.temporal import (
    RUNTIME_RESOURCE_ID,
    TemporalExecutionMismatch,
    TemporalExecutionNotRunning,
    TemporalRecoveryBinding,
    TemporalResumeBlocked,
    TemporalRuntimeAdapter,
)


def revision(resource_id: str, version: str) -> ResourceRevision:
    return ResourceRevision(
        resource_id=resource_id,
        revision=version,
        digest=f"sha256:{sha256(version.encode()).hexdigest()}",
    )


@dataclass
class FakeDescription:
    run_id: str
    status: WorkflowExecutionStatus | None = WorkflowExecutionStatus.RUNNING


class FakeHandle:
    def __init__(
        self,
        *,
        workflow_id: str,
        run_id: str | None,
        result_run_id: str | None,
        first_execution_run_id: str | None,
        description_run_id: str,
        status: WorkflowExecutionStatus | None = WorkflowExecutionStatus.RUNNING,
    ) -> None:
        self.id = workflow_id
        self.run_id = run_id
        self.result_run_id = result_run_id
        self.first_execution_run_id = first_execution_run_id
        self.description = FakeDescription(description_run_id, status)
        self.signals: list[tuple[str, tuple[Any, ...]]] = []

    async def describe(self) -> FakeDescription:
        return self.description

    async def signal(self, signal: str, *, args: tuple[Any, ...]) -> None:
        self.signals.append((signal, args))


class FakeClient:
    def __init__(self, namespace: str, exact_handle: FakeHandle) -> None:
        self.namespace = namespace
        self.exact_handle = exact_handle
        self.requests: list[tuple[str, str | None, str | None]] = []

    def get_workflow_handle(
        self,
        workflow_id: str,
        *,
        run_id: str | None = None,
        first_execution_run_id: str | None = None,
    ) -> FakeHandle:
        self.requests.append((workflow_id, run_id, first_execution_run_id))
        return self.exact_handle


def test_capture_binds_exact_result_run_and_runtime_revision() -> None:
    async def scenario() -> None:
        original = FakeHandle(
            workflow_id="approval-1",
            run_id=None,
            result_run_id="run-1",
            first_execution_run_id="run-1",
            description_run_id="run-1",
        )
        exact = FakeHandle(
            workflow_id="approval-1",
            run_id="run-1",
            result_run_id="run-1",
            first_execution_run_id="run-1",
            description_run_id="run-1",
        )
        client = FakeClient("default", exact)
        policy = revision("policy://deploy", "1")
        adapter = TemporalRuntimeAdapter()

        binding = await adapter.capture(client, original, resources=(policy,))  # type: ignore[arg-type]

        assert binding.execution.namespace == "default"
        assert binding.execution.workflow_id == "approval-1"
        assert binding.execution.run_id == "run-1"
        assert binding.execution.first_execution_run_id == "run-1"
        resources = binding.recovery_checkpoint.snapshot.by_resource()
        assert resources["policy://deploy"] == policy
        assert resources[RUNTIME_RESOURCE_ID] == adapter.runtime_revision()
        assert client.requests[-1] == ("approval-1", "run-1", "run-1")

    asyncio.run(scenario())


def test_validate_and_signal_target_only_bound_run() -> None:
    async def scenario() -> None:
        handle = FakeHandle(
            workflow_id="approval-2",
            run_id="run-2",
            result_run_id="run-2",
            first_execution_run_id="run-2",
            description_run_id="run-2",
        )
        client = FakeClient("default", handle)
        policy = revision("policy://deploy", "1")
        adapter = TemporalRuntimeAdapter()
        binding = await adapter.capture(client, handle, resources=(policy,))  # type: ignore[arg-type]

        decision = await adapter.signal_after_validate(
            client,  # type: ignore[arg-type]
            binding,
            "approve",
            args=(True,),
            current_heads={policy.resource_id: policy},
        )

        assert decision.action is ContinuityAction.RECOVER
        assert handle.signals == [("approve", (True,))]
        assert all(request[1] == "run-2" for request in client.requests)

    asyncio.run(scenario())


def test_changed_reality_blocks_signal() -> None:
    async def scenario() -> None:
        handle = FakeHandle(
            workflow_id="approval-3",
            run_id="run-3",
            result_run_id="run-3",
            first_execution_run_id="run-3",
            description_run_id="run-3",
        )
        client = FakeClient("default", handle)
        policy_v1 = revision("policy://deploy", "1")
        policy_v2 = revision("policy://deploy", "2")
        adapter = TemporalRuntimeAdapter()
        binding = await adapter.capture(client, handle, resources=(policy_v1,))  # type: ignore[arg-type]

        with pytest.raises(TemporalResumeBlocked) as exc_info:
            await adapter.signal_after_validate(
                client,  # type: ignore[arg-type]
                binding,
                "approve",
                args=(True,),
                current_heads={policy_v2.resource_id: policy_v2},
            )

        assert exc_info.value.decision.action is ContinuityAction.REVALIDATE
        assert handle.signals == []

    asyncio.run(scenario())


def test_closed_exact_run_is_rejected() -> None:
    async def scenario() -> None:
        handle = FakeHandle(
            workflow_id="approval-4",
            run_id="run-4",
            result_run_id="run-4",
            first_execution_run_id="run-4",
            description_run_id="run-4",
            status=WorkflowExecutionStatus.COMPLETED,
        )
        client = FakeClient("default", handle)
        adapter = TemporalRuntimeAdapter()

        with pytest.raises(TemporalExecutionNotRunning):
            await adapter.capture(client, handle, resources=())  # type: ignore[arg-type]

    asyncio.run(scenario())


def test_namespace_drift_is_rejected() -> None:
    async def scenario() -> None:
        handle = FakeHandle(
            workflow_id="approval-5",
            run_id="run-5",
            result_run_id="run-5",
            first_execution_run_id="run-5",
            description_run_id="run-5",
        )
        client = FakeClient("namespace-a", handle)
        adapter = TemporalRuntimeAdapter()
        binding = await adapter.capture(client, handle, resources=())  # type: ignore[arg-type]
        client.namespace = "namespace-b"

        with pytest.raises(TemporalExecutionMismatch):
            await adapter.validate_resume(client, binding, current_heads={})  # type: ignore[arg-type]

    asyncio.run(scenario())


def test_binding_rejects_digest_forgery() -> None:
    async def scenario() -> None:
        handle = FakeHandle(
            workflow_id="approval-6",
            run_id="run-6",
            result_run_id="run-6",
            first_execution_run_id="run-6",
            description_run_id="run-6",
        )
        client = FakeClient("default", handle)
        adapter = TemporalRuntimeAdapter()
        binding = await adapter.capture(client, handle, resources=())  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="digest mismatch"):
            TemporalRecoveryBinding(
                execution=binding.execution,
                recovery_checkpoint=binding.recovery_checkpoint,
                binding_digest="sha256:" + "0" * 64,
            )

    asyncio.run(scenario())

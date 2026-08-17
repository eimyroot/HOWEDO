from __future__ import annotations

import asyncio
import os
from hashlib import sha256

import pytest

if os.environ.get("HOWEDO_TEST_TEMPORAL") != "1":
    pytest.skip("real Temporal integration is disabled", allow_module_level=True)

pytest.importorskip("temporalio")
from temporalio import workflow
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from howedo import ContinuityAction, ResourceRevision
from howedo.adapters.temporal import (
    TemporalExecutionNotRunning,
    TemporalResumeBlocked,
    TemporalRuntimeAdapter,
)


@workflow.defn
class GateWorkflow:
    def __init__(self) -> None:
        self._decision: bool | None = None

    @workflow.run
    async def run(self) -> bool:
        await workflow.wait_condition(lambda: self._decision is not None)
        return bool(self._decision)

    @workflow.signal
    def resume(self, decision: bool) -> None:
        self._decision = decision


def revision(resource_id: str, version: str) -> ResourceRevision:
    return ResourceRevision(
        resource_id=resource_id,
        revision=version,
        digest=f"sha256:{sha256(version.encode()).hexdigest()}",
    )


def test_real_temporal_exact_run_safe_signal_boundary() -> None:
    async def scenario() -> None:
        task_queue = "howedo-r7-temporal"
        policy_v1 = revision("policy://deploy", "1")
        policy_v2 = revision("policy://deploy", "2")
        adapter = TemporalRuntimeAdapter()

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(env.client, task_queue=task_queue, workflows=[GateWorkflow]):
                valid = await env.client.start_workflow(
                    GateWorkflow.run,
                    id="howedo-temporal-valid",
                    task_queue=task_queue,
                )
                binding = await adapter.capture(
                    env.client,
                    valid,
                    resources=(policy_v1,),
                )
                assert binding.execution.run_id == valid.result_run_id

                decision = await adapter.signal_after_validate(
                    env.client,
                    binding,
                    "resume",
                    args=(True,),
                    current_heads={policy_v1.resource_id: policy_v1},
                )
                assert decision.action is ContinuityAction.RECOVER
                assert await valid.result() is True

                stale = await env.client.start_workflow(
                    GateWorkflow.run,
                    id="howedo-temporal-stale",
                    task_queue=task_queue,
                )
                stale_binding = await adapter.capture(
                    env.client,
                    stale,
                    resources=(policy_v1,),
                )

                with pytest.raises(TemporalResumeBlocked) as exc_info:
                    await adapter.signal_after_validate(
                        env.client,
                        stale_binding,
                        "resume",
                        args=(True,),
                        current_heads={policy_v2.resource_id: policy_v2},
                    )
                assert exc_info.value.decision.action is ContinuityAction.REVALIDATE

                await stale.signal(GateWorkflow.resume, False)
                assert await stale.result() is False

                closed = await env.client.start_workflow(
                    GateWorkflow.run,
                    id="howedo-temporal-closed",
                    task_queue=task_queue,
                )
                closed_binding = await adapter.capture(
                    env.client,
                    closed,
                    resources=(policy_v1,),
                )
                await closed.signal(GateWorkflow.resume, True)
                assert await closed.result() is True

                with pytest.raises(TemporalExecutionNotRunning):
                    await adapter.validate_resume(
                        env.client,
                        closed_binding,
                        current_heads={policy_v1.resource_id: policy_v1},
                    )

    asyncio.run(scenario())

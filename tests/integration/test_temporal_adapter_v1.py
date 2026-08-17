from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

if os.environ.get("HOWEDO_TEST_TEMPORAL") != "1":
    pytest.skip("real Temporal integration is disabled", allow_module_level=True)

pytest.importorskip("temporalio")

from temporalio import workflow
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from howedo.adapter_certification import (
    AdapterConformanceArtifactBuilder,
    ConformanceStatus,
    verify_conformance_record,
)
from howedo.adapters.temporal_v1 import TemporalRuntimeAdapterV1
from howedo.domain import ResourceRevision


@workflow.defn
class ContractWorkflow:
    def __init__(self) -> None:
        self._done = False

    @workflow.run
    async def run(self) -> bool:
        await workflow.wait_condition(lambda: self._done)
        return self._done

    @workflow.signal
    def resume(self) -> None:
        self._done = True


def revision(resource_id: str, version: str) -> ResourceRevision:
    return ResourceRevision(
        resource_id=resource_id,
        revision=version,
        digest=f"sha256:{sha256(version.encode()).hexdigest()}",
    )


@dataclass
class TemporalFixture:
    runtime: Any
    target: Any
    resources: tuple[ResourceRevision, ...]
    current_heads: dict[str, ResourceRevision]
    continuation: Any = ("resume", ())

    async def changed_heads(self) -> dict[str, ResourceRevision]:
        return {"policy://deploy": revision("policy://deploy", "2")}

    async def verify_continuation(self, result: Any) -> bool:
        return bool(await self.target.result())


def test_temporal_reference_bridge_issues_conformance_artifact() -> None:
    async def scenario() -> None:
        task_queue = "howedo-r9-conformance-artifact"
        policy = revision("policy://deploy", "1")
        adapter = TemporalRuntimeAdapterV1()

        async with await WorkflowEnvironment.start_time_skipping() as env, Worker(
            env.client,
            task_queue=task_queue,
            workflows=[ContractWorkflow],
        ):
            handle = await env.client.start_workflow(
                ContractWorkflow.run,
                id="howedo-r9-conformance-artifact",
                task_queue=task_queue,
            )
            fixture = TemporalFixture(
                runtime=env.client,
                target=handle,
                resources=(policy,),
                current_heads={policy.resource_id: policy},
            )
            artifact = await AdapterConformanceArtifactBuilder().build(
                adapter,
                fixture,
                evidence_refs=("test://temporal-real-run",),
            )
            assert artifact.status is ConformanceStatus.CONFORMANT
            assert verify_conformance_record(artifact.record()).valid
            assert artifact.manifest.runtime_family == "temporal"

            output_dir = os.environ.get("HOWEDO_CONFORMANCE_ARTIFACT_DIR")
            if output_dir:
                version = artifact.environment.python_version.replace(".", "")
                artifact.write(Path(output_dir) / f"temporal-py{version}.json")

    asyncio.run(scenario())

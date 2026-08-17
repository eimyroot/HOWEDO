from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version as package_version
from typing import Any

from temporalio.client import Client, WorkflowExecutionStatus, WorkflowHandle

from howedo.concur import FenceToken
from howedo.domain import ContinuityAction, ContinuitySnapshot, ResourceRevision, Validity
from howedo.protocol import PROTOCOL_VERSION
from howedo.recovery import RecoveryCheckpoint, RecoveryDecision, RecoveryEngine
from howedo.semlock import SemanticComparator

RUNTIME_RESOURCE_ID = "runtime://temporal-python"


class TemporalProtocolError(RuntimeError):
    """Raised when Temporal execution metadata cannot satisfy the adapter contract."""


class TemporalExecutionMismatch(RuntimeError):
    """Raised when Temporal does not resolve the exact execution bound by HOWEDO."""


class TemporalExecutionNotRunning(RuntimeError):
    """Raised when a bound Temporal run is no longer eligible for continuation."""


class TemporalResumeBlocked(RuntimeError):
    """Raised when HOWEDO does not return RECOVER for a requested Temporal signal."""

    def __init__(self, decision: RecoveryDecision) -> None:
        self.decision = decision
        super().__init__(
            f"Temporal continuation blocked by HOWEDO: {decision.action.value} "
            f"{decision.reason_codes}"
        )


@dataclass(frozen=True, slots=True)
class TemporalExecutionRef:
    namespace: str
    workflow_id: str
    run_id: str
    first_execution_run_id: str | None = None

    def __post_init__(self) -> None:
        if not self.namespace:
            raise ValueError("namespace must be non-empty")
        if not self.workflow_id:
            raise ValueError("workflow_id must be non-empty")
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if self.first_execution_run_id == "":
            raise ValueError("first_execution_run_id must be non-empty when present")


@dataclass(frozen=True, slots=True)
class TemporalRecoveryBinding:
    execution: TemporalExecutionRef
    recovery_checkpoint: RecoveryCheckpoint
    binding_digest: str
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError("unsupported HOWEDO protocol version")
        expected = self.compute_digest(
            execution=self.execution,
            recovery_checkpoint=self.recovery_checkpoint,
            protocol_version=self.protocol_version,
        )
        if expected != self.binding_digest:
            raise ValueError("Temporal recovery binding digest mismatch")

    @classmethod
    def build(
        cls,
        *,
        execution: TemporalExecutionRef,
        recovery_checkpoint: RecoveryCheckpoint,
    ) -> TemporalRecoveryBinding:
        return cls(
            execution=execution,
            recovery_checkpoint=recovery_checkpoint,
            binding_digest=cls.compute_digest(
                execution=execution,
                recovery_checkpoint=recovery_checkpoint,
                protocol_version=PROTOCOL_VERSION,
            ),
        )

    @staticmethod
    def compute_digest(
        *,
        execution: TemporalExecutionRef,
        recovery_checkpoint: RecoveryCheckpoint,
        protocol_version: str,
    ) -> str:
        payload = {
            "first_execution_run_id": execution.first_execution_run_id,
            "howedo_checkpoint_id": recovery_checkpoint.checkpoint_id,
            "namespace": execution.namespace,
            "protocol_version": protocol_version,
            "run_id": execution.run_id,
            "runtime": "temporal-python",
            "workflow_id": execution.workflow_id,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return f"sha256:{sha256(encoded).hexdigest()}"


class TemporalRuntimeAdapter:
    """Binds an exact Temporal workflow run to HOWEDO recovery validity checks."""

    def runtime_revision(self) -> ResourceRevision:
        runtime_version = package_version("temporalio")
        digest = f"sha256:{sha256(runtime_version.encode()).hexdigest()}"
        return ResourceRevision(
            resource_id=RUNTIME_RESOURCE_ID,
            revision=runtime_version,
            digest=digest,
        )

    async def capture(
        self,
        client: Client,
        handle: WorkflowHandle[Any, Any],
        *,
        resources: Sequence[ResourceRevision],
        fences: Sequence[FenceToken] = (),
    ) -> TemporalRecoveryBinding:
        run_id = handle.run_id or handle.result_run_id
        if not run_id:
            description = await handle.describe()
            run_id = description.run_id
        if not run_id:
            raise TemporalProtocolError("Temporal workflow handle did not expose an exact run_id")

        execution = TemporalExecutionRef(
            namespace=client.namespace,
            workflow_id=handle.id,
            run_id=run_id,
            first_execution_run_id=handle.first_execution_run_id,
        )
        await self._assert_running_exact(client, execution)

        snapshot = ContinuitySnapshot.build(self._with_runtime_revision(resources))
        recovery_checkpoint = RecoveryCheckpoint.build(
            snapshot=snapshot,
            fences=tuple(fences),
        )
        return TemporalRecoveryBinding.build(
            execution=execution,
            recovery_checkpoint=recovery_checkpoint,
        )

    async def validate_resume(
        self,
        client: Client,
        binding: TemporalRecoveryBinding,
        *,
        current_heads: Mapping[str, ResourceRevision],
        current_fences: Mapping[str, int] | None = None,
        validity: Mapping[str, Validity] | None = None,
        semantic_comparator: SemanticComparator | None = None,
    ) -> RecoveryDecision:
        await self._assert_running_exact(client, binding.execution)

        heads = dict(current_heads)
        heads[RUNTIME_RESOURCE_ID] = self.runtime_revision()
        return RecoveryEngine().validate(
            binding.recovery_checkpoint,
            current_heads=heads,
            current_fences=current_fences,
            validity=validity,
            semantic_comparator=semantic_comparator,
        )

    async def signal_after_validate(
        self,
        client: Client,
        binding: TemporalRecoveryBinding,
        signal: str,
        *,
        args: Sequence[Any] = (),
        current_heads: Mapping[str, ResourceRevision],
        current_fences: Mapping[str, int] | None = None,
        validity: Mapping[str, Validity] | None = None,
        semantic_comparator: SemanticComparator | None = None,
    ) -> RecoveryDecision:
        decision = await self.validate_resume(
            client,
            binding,
            current_heads=current_heads,
            current_fences=current_fences,
            validity=validity,
            semantic_comparator=semantic_comparator,
        )
        if decision.action is not ContinuityAction.RECOVER:
            raise TemporalResumeBlocked(decision)

        handle = self._exact_handle(client, binding.execution)
        await handle.signal(signal, args=tuple(args))
        return decision

    def _with_runtime_revision(
        self, resources: Sequence[ResourceRevision]
    ) -> tuple[ResourceRevision, ...]:
        runtime = self.runtime_revision()
        by_resource = {item.resource_id: item for item in resources}
        existing = by_resource.get(RUNTIME_RESOURCE_ID)
        if existing is not None and existing != runtime:
            raise TemporalProtocolError(
                "caller supplied a conflicting runtime://temporal-python revision"
            )
        by_resource[RUNTIME_RESOURCE_ID] = runtime
        return tuple(by_resource.values())

    @staticmethod
    def _exact_handle(client: Client, execution: TemporalExecutionRef) -> WorkflowHandle[Any, Any]:
        return client.get_workflow_handle(
            execution.workflow_id,
            run_id=execution.run_id,
            first_execution_run_id=execution.first_execution_run_id,
        )

    async def _assert_running_exact(
        self,
        client: Client,
        execution: TemporalExecutionRef,
    ) -> None:
        if client.namespace != execution.namespace:
            raise TemporalExecutionMismatch(
                f"Temporal namespace changed: expected {execution.namespace!r}, "
                f"got {client.namespace!r}"
            )

        description = await self._exact_handle(client, execution).describe()
        if description.run_id != execution.run_id:
            raise TemporalExecutionMismatch(
                "Temporal did not resolve the exact workflow run bound by HOWEDO"
            )
        if description.status is not WorkflowExecutionStatus.RUNNING:
            status = description.status.name if description.status is not None else "UNKNOWN"
            raise TemporalExecutionNotRunning(
                f"Temporal run {execution.run_id} is not running: {status}"
            )

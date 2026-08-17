from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from howedo.adapter_contract import (
    AdapterBinding,
    AdapterCapability,
    AdapterManifest,
    RuntimeIdentity,
)
from howedo.adapters.temporal import TemporalRecoveryBinding, TemporalRuntimeAdapter
from howedo.concur import FenceToken
from howedo.domain import ResourceRevision, Validity
from howedo.recovery import RecoveryDecision
from howedo.semlock import SemanticComparator


class TemporalRuntimeAdapterV1:
    """RuntimeAdapterV1 bridge for the Temporal reference adapter."""

    def __init__(self) -> None:
        self._adapter = TemporalRuntimeAdapter()

    def manifest(self) -> AdapterManifest:
        return AdapterManifest.build(
            adapter_id="howedo.temporal",
            runtime_family="temporal",
            adapter_version="1",
            capabilities=(
                AdapterCapability.EXACT_RUNTIME_IDENTITY,
                AdapterCapability.CAPTURE,
                AdapterCapability.VALIDATE_RESUME,
                AdapterCapability.CONTINUE,
                AdapterCapability.READ_ONLY_VALIDATE,
            ),
        )

    def runtime_revision(self) -> ResourceRevision:
        return self._adapter.runtime_revision()

    async def resolve_identity(self, runtime: Any, target: Any) -> RuntimeIdentity:
        execution = await self._adapter.resolve_execution(runtime, target)
        return RuntimeIdentity(
            runtime_family="temporal",
            namespace=execution.namespace,
            execution_id=execution.workflow_id,
            execution_revision=execution.run_id,
        )

    async def capture(
        self,
        runtime: Any,
        target: Any,
        *,
        resources: Sequence[ResourceRevision],
        fences: Sequence[FenceToken] = (),
    ) -> AdapterBinding:
        recovery_binding = await self._adapter.capture(
            runtime,
            target,
            resources=resources,
            fences=fences,
        )
        return AdapterBinding(
            identity=RuntimeIdentity(
                runtime_family="temporal",
                namespace=recovery_binding.execution.namespace,
                execution_id=recovery_binding.execution.workflow_id,
                execution_revision=recovery_binding.execution.run_id,
            ),
            recovery_binding=recovery_binding,
            adapter_manifest_digest=self.manifest().digest(),
        )

    async def validate_resume(
        self,
        runtime: Any,
        binding: AdapterBinding,
        *,
        current_heads: Mapping[str, ResourceRevision],
        current_fences: Mapping[str, int] | None = None,
        validity: Mapping[str, Validity] | None = None,
        semantic_comparator: SemanticComparator | None = None,
    ) -> RecoveryDecision:
        recovery_binding = self._recovery_binding(binding)
        return await self._adapter.validate_resume(
            runtime,
            recovery_binding,
            current_heads=current_heads,
            current_fences=current_fences,
            validity=validity,
            semantic_comparator=semantic_comparator,
        )

    async def continue_after_validate(
        self,
        runtime: Any,
        binding: AdapterBinding,
        continuation: Any,
        *,
        current_heads: Mapping[str, ResourceRevision],
        current_fences: Mapping[str, int] | None = None,
        validity: Mapping[str, Validity] | None = None,
        semantic_comparator: SemanticComparator | None = None,
    ) -> Any:
        signal_name, args = self._continuation(continuation)
        return await self._adapter.signal_after_validate(
            runtime,
            self._recovery_binding(binding),
            signal_name,
            args=args,
            current_heads=current_heads,
            current_fences=current_fences,
            validity=validity,
            semantic_comparator=semantic_comparator,
        )

    def _recovery_binding(self, binding: AdapterBinding) -> TemporalRecoveryBinding:
        if binding.adapter_manifest_digest != self.manifest().digest():
            raise ValueError("Temporal adapter manifest digest mismatch")
        if not isinstance(binding.recovery_binding, TemporalRecoveryBinding):
            raise TypeError("binding does not contain a Temporal recovery binding")
        expected = binding.recovery_binding.execution
        identity = binding.identity
        if (
            identity.runtime_family != "temporal"
            or identity.namespace != expected.namespace
            or identity.execution_id != expected.workflow_id
            or identity.execution_revision != expected.run_id
        ):
            raise ValueError("Temporal adapter binding identity mismatch")
        return binding.recovery_binding

    @staticmethod
    def _continuation(continuation: Any) -> tuple[str, tuple[Any, ...]]:
        if not isinstance(continuation, tuple) or len(continuation) != 2:
            raise TypeError("Temporal continuation must be (signal_name, args)")
        signal_name, args = continuation
        if not isinstance(signal_name, str) or not signal_name:
            raise TypeError("Temporal signal name must be a non-empty string")
        if not isinstance(args, tuple):
            raise TypeError("Temporal signal args must be a tuple")
        return signal_name, args

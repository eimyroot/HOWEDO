from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from howedo.adapter_contract import (
    AdapterBinding,
    AdapterCapability,
    AdapterContractError,
    AdapterFailureCode,
    AdapterManifest,
    RuntimeIdentity,
    require_recover,
)
from howedo.adapters.langgraph import (
    LangGraphCheckpointMismatch,
    LangGraphProtocolError,
    LangGraphRecoveryBinding,
    LangGraphRuntimeAdapter,
)
from howedo.concur import FenceToken
from howedo.domain import ResourceRevision, Validity
from howedo.recovery import RecoveryDecision
from howedo.semlock import SemanticComparator


class LangGraphRuntimeAdapterV1:
    """RuntimeAdapterV1 bridge for the existing LangGraph reference adapter."""

    def __init__(self) -> None:
        self._adapter = LangGraphRuntimeAdapter()

    def manifest(self) -> AdapterManifest:
        return AdapterManifest.build(
            adapter_id="howedo.langgraph",
            runtime_family="langgraph",
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
        try:
            state = runtime.get_state(target)
            checkpoint = self._adapter._checkpoint_ref(state)
        except LangGraphProtocolError as exc:
            raise AdapterContractError(
                AdapterFailureCode.IDENTITY_UNRESOLVED,
                str(exc),
            ) from exc
        return RuntimeIdentity(
            runtime_family="langgraph",
            namespace=checkpoint.checkpoint_ns or "default",
            execution_id=checkpoint.thread_id,
            execution_revision=checkpoint.checkpoint_id,
        )

    async def capture(
        self,
        runtime: Any,
        target: Any,
        *,
        resources: Sequence[ResourceRevision],
        fences: Sequence[FenceToken] = (),
    ) -> AdapterBinding:
        recovery_binding = self._adapter.capture(
            runtime,
            target,
            resources=resources,
            fences=fences,
        )
        return AdapterBinding(
            identity=await self.resolve_identity(runtime, target),
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
        try:
            return self._adapter.validate_resume(
                runtime,
                recovery_binding,
                current_heads=current_heads,
                current_fences=current_fences,
                validity=validity,
                semantic_comparator=semantic_comparator,
            )
        except LangGraphCheckpointMismatch as exc:
            raise AdapterContractError(
                AdapterFailureCode.IDENTITY_MISMATCH,
                str(exc),
            ) from exc
        except LangGraphProtocolError as exc:
            raise AdapterContractError(
                AdapterFailureCode.PROTOCOL_VIOLATION,
                str(exc),
            ) from exc

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
        decision = await self.validate_resume(
            runtime,
            binding,
            current_heads=current_heads,
            current_fences=current_fences,
            validity=validity,
            semantic_comparator=semantic_comparator,
        )
        require_recover(decision)
        recovery_binding = self._recovery_binding(binding)
        return runtime.invoke(continuation, config=recovery_binding.checkpoint.config())

    def _recovery_binding(self, binding: AdapterBinding) -> LangGraphRecoveryBinding:
        if binding.adapter_manifest_digest != self.manifest().digest():
            raise AdapterContractError(
                AdapterFailureCode.PROTOCOL_VIOLATION,
                "LangGraph adapter manifest digest mismatch",
            )
        if not isinstance(binding.recovery_binding, LangGraphRecoveryBinding):
            raise AdapterContractError(
                AdapterFailureCode.PROTOCOL_VIOLATION,
                "binding does not contain a LangGraph recovery binding",
            )
        expected = binding.recovery_binding.checkpoint
        identity = binding.identity
        if (
            identity.runtime_family != "langgraph"
            or identity.execution_id != expected.thread_id
            or identity.execution_revision != expected.checkpoint_id
            or identity.namespace != (expected.checkpoint_ns or "default")
        ):
            raise AdapterContractError(
                AdapterFailureCode.IDENTITY_MISMATCH,
                "LangGraph adapter binding identity mismatch",
            )
        return binding.recovery_binding

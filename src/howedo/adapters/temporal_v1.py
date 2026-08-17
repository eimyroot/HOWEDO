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
from howedo.adapters.temporal import (
    TemporalExecutionMismatch,
    TemporalExecutionNotRunning,
    TemporalProtocolError,
    TemporalRecoveryBinding,
    TemporalRuntimeAdapter,
)
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
        run_id = target.run_id or target.result_run_id
        if not run_id:
            description = await target.describe()
            run_id = description.run_id
        if not run_id:
            raise AdapterContractError(
                AdapterFailureCode.IDENTITY_UNRESOLVED,
                "Temporal target did not expose an exact run id",
            )

        exact = runtime.get_workflow_handle(
            target.id,
            run_id=run_id,
            first_execution_run_id=target.first_execution_run_id,
        )
        description = await exact.describe()
        if description.run_id != run_id:
            raise AdapterContractError(
                AdapterFailureCode.IDENTITY_MISMATCH,
                "Temporal exact run identity mismatch",
            )

        return RuntimeIdentity(
            runtime_family="temporal",
            namespace=runtime.namespace,
            execution_id=target.id,
            execution_revision=run_id,
        )

    async def capture(
        self,
        runtime: Any,
        target: Any,
        *,
        resources: Sequence[ResourceRevision],
        fences: Sequence[FenceToken] = (),
    ) -> AdapterBinding:
        try:
            recovery_binding = await self._adapter.capture(
                runtime,
                target,
                resources=resources,
                fences=fences,
            )
        except TemporalExecutionMismatch as exc:
            raise AdapterContractError(
                AdapterFailureCode.IDENTITY_MISMATCH,
                str(exc),
            ) from exc
        except TemporalExecutionNotRunning as exc:
            raise AdapterContractError(
                AdapterFailureCode.EXECUTION_NOT_CONTINUABLE,
                str(exc),
            ) from exc
        except TemporalProtocolError as exc:
            raise AdapterContractError(
                AdapterFailureCode.PROTOCOL_VIOLATION,
                str(exc),
            ) from exc

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
        try:
            return await self._adapter.validate_resume(
                runtime,
                recovery_binding,
                current_heads=current_heads,
                current_fences=current_fences,
                validity=validity,
                semantic_comparator=semantic_comparator,
            )
        except TemporalExecutionMismatch as exc:
            raise AdapterContractError(
                AdapterFailureCode.IDENTITY_MISMATCH,
                str(exc),
            ) from exc
        except TemporalExecutionNotRunning as exc:
            raise AdapterContractError(
                AdapterFailureCode.EXECUTION_NOT_CONTINUABLE,
                str(exc),
            ) from exc
        except TemporalProtocolError as exc:
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
    ) -> RecoveryDecision:
        signal_name, args = self._continuation(continuation)
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
        execution = recovery_binding.execution
        exact_handle = runtime.get_workflow_handle(
            execution.workflow_id,
            run_id=execution.run_id,
            first_execution_run_id=execution.first_execution_run_id,
        )
        await exact_handle.signal(signal_name, args=args)
        return decision

    def _recovery_binding(self, binding: AdapterBinding) -> TemporalRecoveryBinding:
        if binding.adapter_manifest_digest != self.manifest().digest():
            raise AdapterContractError(
                AdapterFailureCode.PROTOCOL_VIOLATION,
                "Temporal adapter manifest digest mismatch",
            )
        if not isinstance(binding.recovery_binding, TemporalRecoveryBinding):
            raise AdapterContractError(
                AdapterFailureCode.PROTOCOL_VIOLATION,
                "binding does not contain a Temporal recovery binding",
            )
        expected = binding.recovery_binding.execution
        identity = binding.identity
        if (
            identity.runtime_family != "temporal"
            or identity.namespace != expected.namespace
            or identity.execution_id != expected.workflow_id
            or identity.execution_revision != expected.run_id
        ):
            raise AdapterContractError(
                AdapterFailureCode.IDENTITY_MISMATCH,
                "Temporal adapter binding identity mismatch",
            )
        return binding.recovery_binding

    @staticmethod
    def _continuation(continuation: Any) -> tuple[str, tuple[Any, ...]]:
        if not isinstance(continuation, tuple) or len(continuation) != 2:
            raise AdapterContractError(
                AdapterFailureCode.PROTOCOL_VIOLATION,
                "Temporal continuation must be (signal_name, args)",
            )
        signal_name, args = continuation
        if not isinstance(signal_name, str) or not signal_name:
            raise AdapterContractError(
                AdapterFailureCode.PROTOCOL_VIOLATION,
                "Temporal signal name must be a non-empty string",
            )
        if not isinstance(args, tuple):
            raise AdapterContractError(
                AdapterFailureCode.PROTOCOL_VIOLATION,
                "Temporal signal args must be a tuple",
            )
        return signal_name, args

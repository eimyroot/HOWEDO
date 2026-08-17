"""Minimal third-party HOWEDO runtime adapter skeleton.

This example intentionally leaves vendor operations abstract. A real adapter must
bind exact runtime identity and use HOWEDO RecoveryEngine semantics rather than
inventing a local allow/deny policy.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from howedo.adapter_sdk import (
    AdapterBinding,
    AdapterCapability,
    AdapterManifest,
    RuntimeIdentity,
    require_recover,
)
from howedo.domain import ContinuitySnapshot, ResourceRevision, Validity
from howedo.recovery import RecoveryCheckpoint, RecoveryDecision, RecoveryEngine
from howedo.semlock import SemanticComparator


class ExampleRuntimeAdapter:
    def manifest(self) -> AdapterManifest:
        return AdapterManifest.build(
            adapter_id="vendor.example",
            runtime_family="example-runtime",
            adapter_version="1.0.0",
            capabilities=(
                AdapterCapability.EXACT_RUNTIME_IDENTITY,
                AdapterCapability.CAPTURE,
                AdapterCapability.VALIDATE_RESUME,
                AdapterCapability.CONTINUE,
            ),
        )

    def runtime_revision(self) -> ResourceRevision:
        raise NotImplementedError("return the exact runtime/SDK revision")

    async def resolve_identity(self, runtime: Any, target: Any) -> RuntimeIdentity:
        raise NotImplementedError("resolve an exact, non-retargeting execution identity")

    async def capture(
        self,
        runtime: Any,
        target: Any,
        *,
        resources: Sequence[ResourceRevision],
        fences: Sequence[Any] = (),
    ) -> AdapterBinding:
        identity = await self.resolve_identity(runtime, target)
        snapshot = ContinuitySnapshot.build(tuple(resources) + (self.runtime_revision(),))
        checkpoint = RecoveryCheckpoint.build(snapshot=snapshot, fences=tuple(fences))
        return AdapterBinding(
            identity=identity,
            recovery_binding=checkpoint,
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
        heads = dict(current_heads)
        runtime_revision = self.runtime_revision()
        heads[runtime_revision.resource_id] = runtime_revision
        return RecoveryEngine().validate(
            binding.recovery_binding,
            current_heads=heads,
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
        decision = await self.validate_resume(
            runtime,
            binding,
            current_heads=current_heads,
            current_fences=current_fences,
            validity=validity,
            semantic_comparator=semantic_comparator,
        )
        require_recover(decision)
        raise NotImplementedError("deliver continuation to binding.identity exactly")

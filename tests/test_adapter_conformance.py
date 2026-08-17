from __future__ import annotations

import asyncio
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from howedo.adapter_conformance import AdapterConformanceSuite
from howedo.adapter_contract import (
    AdapterBinding,
    AdapterCapability,
    AdapterManifest,
    RuntimeIdentity,
)
from howedo.domain import ResourceRevision
from howedo.recovery import RecoveryCheckpoint, RecoveryEngine


def revision(resource_id: str, version: str) -> ResourceRevision:
    return ResourceRevision(
        resource_id=resource_id,
        revision=version,
        digest=f"sha256:{sha256(version.encode()).hexdigest()}",
    )


class FakeAdapter:
    def manifest(self) -> AdapterManifest:
        return AdapterManifest.build(
            adapter_id="test.fake",
            runtime_family="fake",
            adapter_version="1",
            capabilities=(
                AdapterCapability.EXACT_RUNTIME_IDENTITY,
                AdapterCapability.CAPTURE,
                AdapterCapability.VALIDATE_RESUME,
                AdapterCapability.CONTINUE,
            ),
        )

    def runtime_revision(self) -> ResourceRevision:
        return revision("runtime://fake", "1")

    async def resolve_identity(self, runtime: Any, target: Any) -> RuntimeIdentity:
        return RuntimeIdentity(
            runtime_family="fake",
            namespace="default",
            execution_id=str(target),
            execution_revision="run-1",
        )

    async def capture(self, runtime: Any, target: Any, *, resources, fences=()) -> AdapterBinding:
        identity = await self.resolve_identity(runtime, target)
        all_resources = tuple(resources) + (self.runtime_revision(),)
        from howedo.domain import ContinuitySnapshot

        checkpoint = RecoveryCheckpoint.build(
            snapshot=ContinuitySnapshot.build(all_resources),
            fences=tuple(fences),
        )
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
        current_heads,
        current_fences=None,
        validity=None,
        semantic_comparator=None,
    ):
        heads = dict(current_heads)
        heads[self.runtime_revision().resource_id] = self.runtime_revision()
        return RecoveryEngine().validate(
            binding.recovery_binding,
            current_heads=heads,
            current_fences=current_fences,
            validity=validity,
            semantic_comparator=semantic_comparator,
        )

    async def continue_after_validate(self, runtime, binding, continuation, **kwargs):
        return continuation


@dataclass
class FakeFixture:
    runtime: Any
    target: Any
    resources: tuple[ResourceRevision, ...]
    current_heads: dict[str, ResourceRevision]

    async def changed_heads(self) -> dict[str, ResourceRevision]:
        return {"policy://deploy": revision("policy://deploy", "2")}

    async def closed_target(self) -> Any:
        return self.target


def test_vendor_neutral_conformance_suite() -> None:
    async def scenario() -> None:
        policy = revision("policy://deploy", "1")
        fixture = FakeFixture(
            runtime=object(),
            target="execution-1",
            resources=(policy,),
            current_heads={policy.resource_id: policy},
        )
        results = await AdapterConformanceSuite().run(FakeAdapter(), fixture)
        AdapterConformanceSuite.assert_passed(results)
        assert {item.check for item in results} >= {
            "contract-version",
            "required-capabilities",
            "binding-exact-identity",
            "unchanged-reality-recovers",
            "changed-reality-does-not-recover",
        }

    asyncio.run(scenario())

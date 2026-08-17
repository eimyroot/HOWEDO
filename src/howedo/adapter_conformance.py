from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from howedo.adapter_contract import (
    ADAPTER_CONTRACT_VERSION,
    AdapterCapability,
    AdapterManifest,
    RuntimeAdapterV1,
    RuntimeIdentity,
)
from howedo.domain import ContinuityAction, ResourceRevision


class AdapterFixture(Protocol):
    """Runtime-specific fixture consumed by the vendor-neutral conformance kit."""

    runtime: Any
    target: Any
    resources: Sequence[ResourceRevision]
    current_heads: Mapping[str, ResourceRevision]
    continuation: Any

    async def changed_heads(self) -> Mapping[str, ResourceRevision]: ...

    async def verify_continuation(self, result: Any) -> bool: ...


@dataclass(frozen=True, slots=True)
class ConformanceResult:
    check: str
    passed: bool
    detail: str = ""


class AdapterConformanceSuite:
    """Executable contract checks shared by first- and third-party adapters."""

    async def run(
        self,
        adapter: RuntimeAdapterV1,
        fixture: AdapterFixture,
    ) -> tuple[ConformanceResult, ...]:
        results: list[ConformanceResult] = []
        results.append(
            ConformanceResult(
                check="runtime-adapter-v1-structural",
                passed=isinstance(adapter, RuntimeAdapterV1),
                detail=type(adapter).__name__,
            )
        )

        manifest = adapter.manifest()
        self._manifest_checks(manifest, results)

        identity = await adapter.resolve_identity(fixture.runtime, fixture.target)
        self._identity_checks(manifest, identity, results)

        binding = await adapter.capture(
            fixture.runtime,
            fixture.target,
            resources=fixture.resources,
        )
        results.append(
            ConformanceResult(
                check="binding-manifest-digest",
                passed=binding.adapter_manifest_digest == manifest.digest(),
                detail=binding.adapter_manifest_digest,
            )
        )
        results.append(
            ConformanceResult(
                check="binding-exact-identity",
                passed=binding.identity == identity,
                detail=binding.identity.digest(),
            )
        )

        current = await adapter.validate_resume(
            fixture.runtime,
            binding,
            current_heads=fixture.current_heads,
        )
        results.append(
            ConformanceResult(
                check="unchanged-reality-recovers",
                passed=current.action is ContinuityAction.RECOVER,
                detail=current.action.value,
            )
        )

        changed = await adapter.validate_resume(
            fixture.runtime,
            binding,
            current_heads=await fixture.changed_heads(),
        )
        results.append(
            ConformanceResult(
                check="changed-reality-does-not-recover",
                passed=changed.action is not ContinuityAction.RECOVER,
                detail=changed.action.value,
            )
        )

        continuation_result = await adapter.continue_after_validate(
            fixture.runtime,
            binding,
            fixture.continuation,
            current_heads=fixture.current_heads,
        )
        continuation_verified = await fixture.verify_continuation(continuation_result)
        results.append(
            ConformanceResult(
                check="continue-after-recover",
                passed=continuation_verified,
                detail=type(continuation_result).__name__,
            )
        )

        return tuple(results)

    @staticmethod
    def assert_passed(results: Sequence[ConformanceResult]) -> None:
        failed = [result for result in results if not result.passed]
        if failed:
            detail = "; ".join(f"{item.check}: {item.detail}" for item in failed)
            raise AssertionError(f"runtime adapter conformance failed: {detail}")

    @staticmethod
    def _manifest_checks(
        manifest: AdapterManifest,
        results: list[ConformanceResult],
    ) -> None:
        required = {
            AdapterCapability.EXACT_RUNTIME_IDENTITY,
            AdapterCapability.CAPTURE,
            AdapterCapability.VALIDATE_RESUME,
            AdapterCapability.CONTINUE,
        }
        actual = set(manifest.capabilities)
        results.extend(
            (
                ConformanceResult(
                    check="contract-version",
                    passed=manifest.contract_version == ADAPTER_CONTRACT_VERSION,
                    detail=manifest.contract_version,
                ),
                ConformanceResult(
                    check="required-capabilities",
                    passed=required.issubset(actual),
                    detail=",".join(sorted(item.value for item in actual)),
                ),
                ConformanceResult(
                    check="manifest-content-addressed",
                    passed=manifest.digest().startswith("sha256:"),
                    detail=manifest.digest(),
                ),
            )
        )

    @staticmethod
    def _identity_checks(
        manifest: AdapterManifest,
        identity: RuntimeIdentity,
        results: list[ConformanceResult],
    ) -> None:
        results.extend(
            (
                ConformanceResult(
                    check="identity-runtime-family",
                    passed=identity.runtime_family == manifest.runtime_family,
                    detail=identity.runtime_family,
                ),
                ConformanceResult(
                    check="identity-content-addressed",
                    passed=identity.digest().startswith("sha256:"),
                    detail=identity.digest(),
                ),
            )
        )

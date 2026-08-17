from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any, Protocol, runtime_checkable

from howedo.domain import ContinuityAction, ResourceRevision, Validity
from howedo.recovery import RecoveryDecision
from howedo.semlock import SemanticComparator

ADAPTER_CONTRACT_VERSION = "howedo.runtime-adapter.v1"


class AdapterCapability(StrEnum):
    EXACT_RUNTIME_IDENTITY = "EXACT_RUNTIME_IDENTITY"
    CAPTURE = "CAPTURE"
    VALIDATE_RESUME = "VALIDATE_RESUME"
    CONTINUE = "CONTINUE"
    READ_ONLY_VALIDATE = "READ_ONLY_VALIDATE"
    FENCED_WRITES = "FENCED_WRITES"


class AdapterFailureCode(StrEnum):
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    EXECUTION_NOT_CONTINUABLE = "EXECUTION_NOT_CONTINUABLE"
    CONTINUITY_BLOCKED = "CONTINUITY_BLOCKED"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    PROTOCOL_VIOLATION = "PROTOCOL_VIOLATION"


@dataclass(frozen=True, slots=True)
class AdapterManifest:
    adapter_id: str
    runtime_family: str
    adapter_version: str
    contract_version: str = ADAPTER_CONTRACT_VERSION
    capabilities: tuple[AdapterCapability, ...] = ()

    def __post_init__(self) -> None:
        if not self.adapter_id:
            raise ValueError("adapter_id must be non-empty")
        if not self.runtime_family:
            raise ValueError("runtime_family must be non-empty")
        if not self.adapter_version:
            raise ValueError("adapter_version must be non-empty")
        if self.contract_version != ADAPTER_CONTRACT_VERSION:
            raise ValueError("unsupported runtime adapter contract version")
        canonical = tuple(sorted(set(self.capabilities), key=lambda item: item.value))
        if self.capabilities != canonical:
            raise ValueError("adapter capabilities must be sorted and unique")

    @classmethod
    def build(
        cls,
        *,
        adapter_id: str,
        runtime_family: str,
        adapter_version: str,
        capabilities: Sequence[AdapterCapability],
    ) -> AdapterManifest:
        return cls(
            adapter_id=adapter_id,
            runtime_family=runtime_family,
            adapter_version=adapter_version,
            capabilities=tuple(sorted(set(capabilities), key=lambda item: item.value)),
        )

    def digest(self) -> str:
        payload = {
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "capabilities": [item.value for item in self.capabilities],
            "contract_version": self.contract_version,
            "runtime_family": self.runtime_family,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return f"sha256:{sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    runtime_family: str
    namespace: str
    execution_id: str
    execution_revision: str

    def __post_init__(self) -> None:
        for name, value in (
            ("runtime_family", self.runtime_family),
            ("namespace", self.namespace),
            ("execution_id", self.execution_id),
            ("execution_revision", self.execution_revision),
        ):
            if not value:
                raise ValueError(f"{name} must be non-empty")

    def canonical(self) -> dict[str, str]:
        return {
            "execution_id": self.execution_id,
            "execution_revision": self.execution_revision,
            "namespace": self.namespace,
            "runtime_family": self.runtime_family,
        }

    def digest(self) -> str:
        encoded = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":")).encode()
        return f"sha256:{sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class AdapterBinding:
    identity: RuntimeIdentity
    recovery_binding: Any
    adapter_manifest_digest: str

    def __post_init__(self) -> None:
        if not self.adapter_manifest_digest.startswith("sha256:"):
            raise ValueError("adapter manifest digest must be sha256-addressed")


class AdapterContractError(RuntimeError):
    def __init__(self, code: AdapterFailureCode, message: str) -> None:
        self.code = code
        super().__init__(message)


class AdapterResumeBlocked(AdapterContractError):
    def __init__(self, decision: RecoveryDecision) -> None:
        self.decision = decision
        super().__init__(
            AdapterFailureCode.CONTINUITY_BLOCKED,
            f"runtime continuation blocked by HOWEDO: {decision.action.value} {decision.reason_codes}",
        )


@runtime_checkable
class RuntimeAdapterV1(Protocol):
    """Public contract for third-party HOWEDO runtime adapters."""

    def manifest(self) -> AdapterManifest: ...

    def runtime_revision(self) -> ResourceRevision: ...

    async def resolve_identity(self, runtime: Any, target: Any) -> RuntimeIdentity: ...

    async def capture(
        self,
        runtime: Any,
        target: Any,
        *,
        resources: Sequence[ResourceRevision],
        fences: Sequence[Any] = (),
    ) -> AdapterBinding: ...

    async def validate_resume(
        self,
        runtime: Any,
        binding: AdapterBinding,
        *,
        current_heads: Mapping[str, ResourceRevision],
        current_fences: Mapping[str, int] | None = None,
        validity: Mapping[str, Validity] | None = None,
        semantic_comparator: SemanticComparator | None = None,
    ) -> RecoveryDecision: ...

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
    ) -> Any: ...


def require_recover(decision: RecoveryDecision) -> None:
    if decision.action is not ContinuityAction.RECOVER:
        raise AdapterResumeBlocked(decision)

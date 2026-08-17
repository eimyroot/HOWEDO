from __future__ import annotations

from collections.abc import Awaitable
from typing import TypeVar

from howedo.adapter_contract import (
    ADAPTER_CONTRACT_VERSION,
    AdapterCapability,
    AdapterFailureCode,
    AdapterManifest,
    AdapterResumeBlocked,
    RuntimeAdapterV1,
    RuntimeIdentity,
    require_recover,
)
from howedo.adapter_conformance import (
    AdapterConformanceSuite,
    AdapterFixture,
    ConformanceResult,
)

T = TypeVar("T")


async def maybe_await(value: T | Awaitable[T]) -> T:
    if hasattr(value, "__await__"):
        return await value  # type: ignore[misc]
    return value


__all__ = [
    "ADAPTER_CONTRACT_VERSION",
    "AdapterCapability",
    "AdapterConformanceSuite",
    "AdapterFailureCode",
    "AdapterFixture",
    "AdapterManifest",
    "AdapterResumeBlocked",
    "ConformanceResult",
    "RuntimeAdapterV1",
    "RuntimeIdentity",
    "maybe_await",
    "require_recover",
]

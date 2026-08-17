from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import Any

PROTOCOL_VERSION = "howedo.protocol.v1"


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_digest(payload: Mapping[str, Any]) -> str:
    return f"sha256:{sha256(canonical_json(payload).encode()).hexdigest()}"


@dataclass(frozen=True, slots=True)
class WitnessRecord:
    witness_digest: str
    witness_kind: str
    payload: Mapping[str, Any]
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if not self.witness_kind:
            raise ValueError("witness kind must be non-empty")
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError("unsupported witness protocol version")
        payload = dict(self.payload)
        if canonical_digest(payload) != self.witness_digest:
            raise ValueError("witness digest does not match canonical payload")
        object.__setattr__(self, "payload", MappingProxyType(payload))


@dataclass(frozen=True, slots=True)
class ContinuityEvent:
    event_id: str
    event_type: str
    payload: Mapping[str, Any]
    resource_id: str | None = None
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event id must be non-empty")
        if not self.event_type:
            raise ValueError("event type must be non-empty")
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError("unsupported event protocol version")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True, slots=True)
class StoredEvent:
    sequence: int
    event: ContinuityEvent

    def __post_init__(self) -> None:
        if self.sequence <= 0:
            raise ValueError("stored event sequence must be positive")

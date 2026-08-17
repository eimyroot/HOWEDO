from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256


class ContinuityAction(StrEnum):
    CONTINUE = "CONTINUE"
    PAUSE = "PAUSE"
    REVALIDATE = "REVALIDATE"
    ABORT = "ABORT"
    RECOVER = "RECOVER"


class Validity(StrEnum):
    VALID = "VALID"
    STALE = "STALE"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"
    REVALIDATING = "REVALIDATING"
    SUPERSEDED = "SUPERSEDED"


class DriftClassification(StrEnum):
    UNCHANGED = "UNCHANGED"
    COMPATIBLE = "COMPATIBLE"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"
    BREAKING = "BREAKING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ResourceRevision:
    resource_id: str
    revision: str
    digest: str

    def canonical(self) -> dict[str, str]:
        return {
            "digest": self.digest,
            "resource_id": self.resource_id,
            "revision": self.revision,
        }


@dataclass(frozen=True, slots=True)
class ContinuitySnapshot:
    snapshot_id: str
    resources: tuple[ResourceRevision, ...]

    @classmethod
    def build(cls, resources: tuple[ResourceRevision, ...]) -> ContinuitySnapshot:
        ordered = tuple(sorted(resources, key=lambda item: item.resource_id))
        payload = [item.canonical() for item in ordered]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return cls(snapshot_id=f"sha256:{sha256(encoded).hexdigest()}", resources=ordered)

    def by_resource(self) -> Mapping[str, ResourceRevision]:
        return {item.resource_id: item for item in self.resources}


@dataclass(frozen=True, slots=True)
class ContinuityWitness:
    snapshot_id: str
    action: ContinuityAction
    reason_codes: tuple[str, ...]
    witness_digest: str

    @classmethod
    def build(
        cls,
        *,
        snapshot_id: str,
        action: ContinuityAction,
        reason_codes: tuple[str, ...],
    ) -> ContinuityWitness:
        ordered_reasons = tuple(sorted(reason_codes))
        payload = {
            "action": action.value,
            "reason_codes": ordered_reasons,
            "snapshot_id": snapshot_id,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return cls(
            snapshot_id=snapshot_id,
            action=action,
            reason_codes=ordered_reasons,
            witness_digest=f"sha256:{sha256(encoded).hexdigest()}",
        )


@dataclass(frozen=True, slots=True)
class ContinuityDecision:
    action: ContinuityAction
    reason_codes: tuple[str, ...]
    witness: ContinuityWitness

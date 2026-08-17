from __future__ import annotations

from typing import Protocol

from howedo.domain import ResourceRevision
from howedo.protocol import ContinuityEvent, StoredEvent, WitnessRecord


class StorageAdapter(Protocol):
    """Persistence-only contract. Implementations must not redefine kernel semantics."""

    def schema_version(self) -> str: ...

    def register_revision(self, revision: ResourceRevision) -> None: ...

    def initialize_head(self, revision: ResourceRevision) -> None: ...

    def head(self, resource_id: str) -> ResourceRevision | None: ...

    def activate_if_head(
        self,
        *,
        expected: ResourceRevision,
        replacement: ResourceRevision,
    ) -> None: ...

    def put_witness(self, witness: WitnessRecord) -> None: ...

    def get_witness(self, witness_digest: str) -> WitnessRecord | None: ...

    def append_event(self, event: ContinuityEvent) -> StoredEvent: ...

    def events_after(self, sequence: int = 0, *, limit: int = 100) -> tuple[StoredEvent, ...]: ...

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256

import psycopg
import pytest

from howedo import ContinuityEvent, ResourceRevision, WitnessRecord, canonical_digest
from howedo.kernel import HeadConflict, RevisionConflict
from howedo.storage.postgres import (
    EventConflict,
    PostgresStorageAdapter,
    UnsupportedStorageSchema,
    WitnessConflict,
)

DSN = os.environ.get("HOWEDO_TEST_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(DSN is None, reason="PostgreSQL conformance DSN is not configured")


def revision(resource_id: str, version: str) -> ResourceRevision:
    digest = f"sha256:{sha256(version.encode()).hexdigest()}"
    return ResourceRevision(resource_id=resource_id, revision=version, digest=digest)


@pytest.fixture
def adapter() -> PostgresStorageAdapter:
    assert DSN is not None
    storage = PostgresStorageAdapter(DSN)
    storage.migrate()
    with psycopg.connect(DSN) as conn:
        conn.execute(
            "TRUNCATE howedo_events, howedo_witnesses, howedo_heads, "
            "howedo_revisions RESTART IDENTITY CASCADE"
        )
    return storage


def test_schema_version_is_protocol_v1(adapter: PostgresStorageAdapter) -> None:
    assert adapter.schema_version() == "howedo.protocol.v1"


def test_revision_identity_is_immutable(adapter: PostgresStorageAdapter) -> None:
    first = revision("repo://acme/app", "1")
    adapter.register_revision(first)
    adapter.register_revision(first)

    forged = ResourceRevision(first.resource_id, first.revision, "sha256:" + "f" * 64)
    with pytest.raises(RevisionConflict):
        adapter.register_revision(forged)


def test_head_initialization_is_one_time_and_idempotent(adapter: PostgresStorageAdapter) -> None:
    first = revision("repo://acme/app", "1")
    second = revision("repo://acme/app", "2")

    adapter.initialize_head(first)
    adapter.initialize_head(first)

    with pytest.raises(HeadConflict):
        adapter.initialize_head(second)

    assert adapter.head(first.resource_id) == first


def test_expected_head_activation_rejects_stale_writer(adapter: PostgresStorageAdapter) -> None:
    first = revision("repo://acme/app", "1")
    second = revision("repo://acme/app", "2")
    third = revision("repo://acme/app", "3")
    adapter.initialize_head(first)

    adapter.activate_if_head(expected=first, replacement=second)

    with pytest.raises(HeadConflict):
        adapter.activate_if_head(expected=first, replacement=third)

    assert adapter.head(first.resource_id) == second


def test_expected_head_activation_is_atomic_under_competing_writers(
    adapter: PostgresStorageAdapter,
) -> None:
    first = revision("repo://acme/race", "1")
    second = revision("repo://acme/race", "2a")
    third = revision("repo://acme/race", "2b")
    adapter.initialize_head(first)

    def attempt(candidate: ResourceRevision) -> str:
        try:
            adapter.activate_if_head(expected=first, replacement=candidate)
            return "success"
        except HeadConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, (second, third)))

    assert sorted(outcomes) == ["conflict", "success"]
    assert adapter.head(first.resource_id) in {second, third}


def test_witness_round_trip_is_content_addressed(adapter: PostgresStorageAdapter) -> None:
    payload = {"action": "CONTINUE", "reason_codes": [], "snapshot_id": "sha256:" + "a" * 64}
    record = WitnessRecord(
        witness_digest=canonical_digest(payload),
        witness_kind="continuity",
        payload=payload,
    )

    adapter.put_witness(record)
    adapter.put_witness(record)

    assert adapter.get_witness(record.witness_digest) == record

    conflicting_kind = WitnessRecord(
        witness_digest=record.witness_digest,
        witness_kind="recovery",
        payload=payload,
    )
    with pytest.raises(WitnessConflict):
        adapter.put_witness(conflicting_kind)


def test_events_are_append_only_ordered_and_idempotent(adapter: PostgresStorageAdapter) -> None:
    first = ContinuityEvent(
        event_id="evt-1",
        event_type="resource.changed",
        resource_id="repo://acme/app",
        payload={"revision": "2"},
    )
    second = ContinuityEvent(
        event_id="evt-2",
        event_type="decision.made",
        payload={"action": "REVALIDATE"},
    )

    stored_first = adapter.append_event(first)
    assert adapter.append_event(first) == stored_first
    stored_second = adapter.append_event(second)

    assert stored_first.sequence < stored_second.sequence
    assert adapter.events_after(stored_first.sequence) == (stored_second,)

    conflicting = ContinuityEvent(
        event_id="evt-1",
        event_type="resource.changed",
        resource_id="repo://acme/app",
        payload={"revision": "forged"},
    )
    with pytest.raises(EventConflict):
        adapter.append_event(conflicting)


def test_future_unknown_migration_is_rejected(adapter: PostgresStorageAdapter) -> None:
    assert DSN is not None
    with psycopg.connect(DSN) as conn:
        conn.execute(
            "INSERT INTO howedo_schema_migrations (migration_id, protocol_version) "
            "VALUES ('9999_future', 'howedo.protocol.v2')"
        )
    try:
        with pytest.raises(UnsupportedStorageSchema):
            adapter.schema_version()
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute(
                "DELETE FROM howedo_schema_migrations WHERE migration_id = '9999_future'"
            )

from __future__ import annotations

from importlib.resources import files
from typing import Any

import psycopg

from howedo.domain import ResourceRevision
from howedo.kernel import HeadConflict, RevisionConflict
from howedo.protocol import PROTOCOL_VERSION, ContinuityEvent, StoredEvent, WitnessRecord

MIGRATION_ID = "0001_protocol_v1"
SUPPORTED_MIGRATIONS = frozenset({MIGRATION_ID})


class StorageNotInitialized(RuntimeError):
    """Raised when a persistent adapter is used before migrations are applied."""


class UnsupportedStorageSchema(RuntimeError):
    """Raised when storage contains migrations unknown to this adapter."""


class WitnessConflict(ValueError):
    """Raised when a witness digest is reused with different canonical content."""


class EventConflict(ValueError):
    """Raised when an event id is reused with different event content."""


class PostgresStorageAdapter:
    """Reference PostgreSQL implementation of HOWEDO's persistence contract."""

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("PostgreSQL DSN must be non-empty")
        self._dsn = dsn

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(self._dsn)

    def migrate(self) -> None:
        sql = (
            files("howedo.storage.migrations")
            .joinpath("0001_protocol_v1.sql")
            .read_text(encoding="utf-8")
        )
        with self._connect() as conn:
            for statement in sql.split(";"):
                statement = statement.strip()
                if statement:
                    conn.execute(statement)
        if self.schema_version() != PROTOCOL_VERSION:
            raise UnsupportedStorageSchema("migration did not establish protocol v1")

    def schema_version(self) -> str:
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT to_regclass('public.howedo_schema_migrations')"
            ).fetchone()
            if exists is None or exists[0] is None:
                return "uninitialized"
            rows = conn.execute(
                "SELECT migration_id, protocol_version "
                "FROM howedo_schema_migrations ORDER BY migration_id"
            ).fetchall()
        if not rows:
            return "uninitialized"
        unknown = [migration_id for migration_id, _ in rows if migration_id not in SUPPORTED_MIGRATIONS]
        if unknown:
            raise UnsupportedStorageSchema(f"unsupported migrations: {unknown}")
        protocol_versions = {protocol_version for _, protocol_version in rows}
        if protocol_versions != {PROTOCOL_VERSION}:
            raise UnsupportedStorageSchema(
                f"unsupported protocol versions in storage: {sorted(protocol_versions)}"
            )
        return PROTOCOL_VERSION

    def _assert_initialized(self, conn: psycopg.Connection[Any]) -> None:
        rows = conn.execute(
            "SELECT migration_id, protocol_version FROM howedo_schema_migrations ORDER BY migration_id"
        ).fetchall()
        if not rows:
            raise StorageNotInitialized("HOWEDO storage migrations have not been applied")
        unknown = [migration_id for migration_id, _ in rows if migration_id not in SUPPORTED_MIGRATIONS]
        if unknown:
            raise UnsupportedStorageSchema(f"unsupported migrations: {unknown}")
        if {protocol for _, protocol in rows} != {PROTOCOL_VERSION}:
            raise UnsupportedStorageSchema("storage protocol version is not howedo.protocol.v1")

    @staticmethod
    def _register_revision(
        conn: psycopg.Connection[Any], revision: ResourceRevision
    ) -> None:
        conn.execute(
            "INSERT INTO howedo_revisions (resource_id, revision, digest) "
            "VALUES (%s, %s, %s) ON CONFLICT (resource_id, revision) DO NOTHING",
            (revision.resource_id, revision.revision, revision.digest),
        )
        row = conn.execute(
            "SELECT digest FROM howedo_revisions WHERE resource_id = %s AND revision = %s",
            (revision.resource_id, revision.revision),
        ).fetchone()
        if row is None or row[0] != revision.digest:
            raise RevisionConflict(
                f"immutable revision conflict for {revision.resource_id}@{revision.revision}"
            )

    def register_revision(self, revision: ResourceRevision) -> None:
        with self._connect() as conn:
            self._assert_initialized(conn)
            self._register_revision(conn, revision)

    def initialize_head(self, revision: ResourceRevision) -> None:
        with self._connect() as conn:
            self._assert_initialized(conn)
            self._register_revision(conn, revision)
            inserted = conn.execute(
                "INSERT INTO howedo_heads (resource_id, revision, digest) "
                "VALUES (%s, %s, %s) ON CONFLICT (resource_id) DO NOTHING "
                "RETURNING resource_id",
                (revision.resource_id, revision.revision, revision.digest),
            ).fetchone()
            if inserted is not None:
                return
            current = conn.execute(
                "SELECT revision, digest FROM howedo_heads WHERE resource_id = %s",
                (revision.resource_id,),
            ).fetchone()
            if current != (revision.revision, revision.digest):
                raise HeadConflict(f"authoritative head already initialized for {revision.resource_id}")

    def head(self, resource_id: str) -> ResourceRevision | None:
        with self._connect() as conn:
            self._assert_initialized(conn)
            row = conn.execute(
                "SELECT revision, digest FROM howedo_heads WHERE resource_id = %s",
                (resource_id,),
            ).fetchone()
        if row is None:
            return None
        return ResourceRevision(resource_id=resource_id, revision=row[0], digest=row[1])

    def activate_if_head(
        self,
        *,
        expected: ResourceRevision,
        replacement: ResourceRevision,
    ) -> None:
        if expected.resource_id != replacement.resource_id:
            raise ValueError("replacement must target the same resource")
        with self._connect() as conn:
            self._assert_initialized(conn)
            self._register_revision(conn, replacement)
            updated = conn.execute(
                "UPDATE howedo_heads SET revision = %s, digest = %s "
                "WHERE resource_id = %s AND revision = %s AND digest = %s "
                "RETURNING resource_id",
                (
                    replacement.revision,
                    replacement.digest,
                    expected.resource_id,
                    expected.revision,
                    expected.digest,
                ),
            ).fetchone()
            if updated is None:
                raise HeadConflict(f"stale expected head for {expected.resource_id}")

    def put_witness(self, witness: WitnessRecord) -> None:
        with self._connect() as conn:
            self._assert_initialized(conn)
            conn.execute(
                "INSERT INTO howedo_witnesses "
                "(witness_digest, witness_kind, protocol_version, payload) "
                "VALUES (%s, %s, %s, %s::jsonb) "
                "ON CONFLICT (witness_digest) DO NOTHING",
                (
                    witness.witness_digest,
                    witness.witness_kind,
                    witness.protocol_version,
                    _json_text(witness.payload),
                ),
            )
            row = conn.execute(
                "SELECT witness_kind, protocol_version, payload "
                "FROM howedo_witnesses WHERE witness_digest = %s",
                (witness.witness_digest,),
            ).fetchone()
            expected = (
                witness.witness_kind,
                witness.protocol_version,
                dict(witness.payload),
            )
            if row is None or (row[0], row[1], row[2]) != expected:
                raise WitnessConflict(f"witness digest conflict: {witness.witness_digest}")

    def get_witness(self, witness_digest: str) -> WitnessRecord | None:
        with self._connect() as conn:
            self._assert_initialized(conn)
            row = conn.execute(
                "SELECT witness_kind, protocol_version, payload "
                "FROM howedo_witnesses WHERE witness_digest = %s",
                (witness_digest,),
            ).fetchone()
        if row is None:
            return None
        return WitnessRecord(
            witness_digest=witness_digest,
            witness_kind=row[0],
            protocol_version=row[1],
            payload=row[2],
        )

    def append_event(self, event: ContinuityEvent) -> StoredEvent:
        with self._connect() as conn:
            self._assert_initialized(conn)
            inserted = conn.execute(
                "INSERT INTO howedo_events "
                "(event_id, event_type, resource_id, protocol_version, payload) "
                "VALUES (%s, %s, %s, %s, %s::jsonb) "
                "ON CONFLICT (event_id) DO NOTHING RETURNING sequence",
                (
                    event.event_id,
                    event.event_type,
                    event.resource_id,
                    event.protocol_version,
                    _json_text(event.payload),
                ),
            ).fetchone()
            if inserted is not None:
                return StoredEvent(sequence=inserted[0], event=event)
            row = conn.execute(
                "SELECT sequence, event_type, resource_id, protocol_version, payload "
                "FROM howedo_events WHERE event_id = %s",
                (event.event_id,),
            ).fetchone()
            if row is None:
                raise EventConflict(f"event id conflict: {event.event_id}")
            stored = ContinuityEvent(
                event_id=event.event_id,
                event_type=row[1],
                resource_id=row[2],
                protocol_version=row[3],
                payload=row[4],
            )
            if stored != event:
                raise EventConflict(f"event id conflict: {event.event_id}")
            return StoredEvent(sequence=row[0], event=stored)

    def events_after(self, sequence: int = 0, *, limit: int = 100) -> tuple[StoredEvent, ...]:
        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        if limit <= 0 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connect() as conn:
            self._assert_initialized(conn)
            rows = conn.execute(
                "SELECT sequence, event_id, event_type, resource_id, protocol_version, payload "
                "FROM howedo_events WHERE sequence > %s ORDER BY sequence LIMIT %s",
                (sequence, limit),
            ).fetchall()
        return tuple(
            StoredEvent(
                sequence=row[0],
                event=ContinuityEvent(
                    event_id=row[1],
                    event_type=row[2],
                    resource_id=row[3],
                    protocol_version=row[4],
                    payload=row[5],
                ),
            )
            for row in rows
        )


def _json_text(payload: Any) -> str:
    import json

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

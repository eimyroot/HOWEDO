# ADR-0006: Storage protocol v1 and PostgreSQL reference persistence

Status: Accepted
Date: 2026-08-17

## Context

R0-R4 define HOWEDO continuity semantics in a deterministic in-memory kernel. A durable product now needs a persistence boundary without allowing any storage backend to redefine those semantics.

## Decision

HOWEDO introduces protocol version `howedo.protocol.v1` and a narrow `StorageAdapter` contract. The contract owns persistence operations only:

- immutable resource revisions
- authoritative heads
- atomic expected-head activation
- witness records
- append-only continuity events
- storage schema version reporting

The reference persistent implementation is PostgreSQL through Psycopg 3. PostgreSQL is not a kernel dependency: it is an optional adapter under `howedo.storage.postgres`.

## Atomic head activation

Persistent `activate_if_head()` must perform compare-and-set atomically in one transaction. The PostgreSQL adapter updates the authoritative head only when both expected revision and expected digest match. A zero-row update is a `HeadConflict`; the adapter never performs a read-then-write race outside the transaction boundary.

## Protocol and migration versioning

- wire/storage protocol: `howedo.protocol.v1`
- PostgreSQL schema migration: `0001_protocol_v1`
- protocol schemas are additive/frozen within v1; breaking changes require a new protocol major
- database migrations are monotonic and recorded in `howedo_schema_migrations`
- adapters must reject a storage schema version newer than the version they understand

## Witnesses and events

Witness payloads are persisted canonically as JSON and keyed by their existing deterministic digest. Events are append-only, caller-identified records with a database-assigned monotonic sequence for ordered consumption.

## Boundary

R5 does not add runtime orchestration, checkpoint persistence, vector memory, generic event streaming, distributed locks, CASER/V-One dependencies, or a policy engine.

PostgreSQL is a reference adapter, not a product dependency. Future storage implementations must pass the same conformance suite.

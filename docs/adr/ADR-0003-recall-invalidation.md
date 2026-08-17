# ADR-0003: RECALL propagates validity, not memory content

Status: Accepted
Date: 2026-08-17

## Context

HOWEDO must determine which derived state can no longer be trusted when authoritative reality changes. It must not become a generic memory store or infer truth by asking an LLM to judge its own stale context.

## Decision

RECALL is a deterministic dependency-invalidation engine over explicit directed lineage edges.

The first signals are:

- `CHANGED`: the authoritative source has a new valid head; downstream dependents become `STALE`.
- `INVALID`: the source is known invalid; the source and downstream dependents become `INVALID`.
- `UNKNOWN`: the source cannot currently be established; the source and downstream dependents become `UNKNOWN`.

Propagation is transitive and cycle-safe. Multiple causes merge conservatively: `INVALID` outranks `UNKNOWN`, which outranks `STALE`.

RECALL outputs validity metadata and reason codes. The existing Decision Engine consumes that metadata; RECALL does not execute external actions.

## Safety correction

When continuity inputs contain both `UNKNOWN` and `STALE`, `PAUSE` must outrank `REVALIDATE`. Unknown reality is not safe to treat as merely stale.

Decision precedence is therefore:

`ABORT > PAUSE > REVALIDATE > RECOVER > CONTINUE`.

## Consequences

- HOWEDO retains deterministic and reproducible semantics.
- External memory/vector systems remain adapters or resources, not kernel dependencies.
- Dependency lineage becomes a core product primitive and can later be persisted in PostgreSQL without changing public semantics.
- R2 does not yet add persistence, graph databases, event buses, or probabilistic inference; those would be premature.

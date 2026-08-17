# ADR-0004: CONCUR uses expected-head checks and monotonic fencing

Status: Accepted
Date: 2026-08-17

## Context

Long-running or paused agents can resume after another actor has already advanced the same resource. Exact state validity alone does not prevent an old worker from writing after a newer worker has taken ownership.

## Decision

CONCUR adds two independent preconditions before an external write is considered safe:

1. The current authoritative head must exactly match the writer's expected head.
2. The writer must hold the current monotonic fencing token for the resource.

Outcomes map to the existing HOWEDO continuity actions:

- exact head + current fence -> `CONTINUE`
- head mismatch -> `REVALIDATE`
- stale fence -> `ABORT`
- future/unverifiable fence -> `PAUSE`

Stale fencing outranks a head conflict because the worker has already lost authority to write, even if it can re-read state.

## Storage boundary

The kernel defines compare-and-set semantics but does not claim to be a distributed database. `StateRegistry.activate_if_head()` is a reference implementation. Persistent adapters must implement the same expected-head check and activation atomically inside their own transaction boundary.

PostgreSQL can later implement this with transactional compare-and-set/locking semantics. No distributed lock service is required by the HOWEDO kernel contract.

## Consequences

- zombie/stale workers can be rejected even when the resource head has not yet changed
- runtime vendors remain replaceable
- fencing semantics are testable independently of Temporal, LangGraph, CASER, V-One, or any queue system
- durable execution remains external infrastructure; HOWEDO owns continuation/write validity

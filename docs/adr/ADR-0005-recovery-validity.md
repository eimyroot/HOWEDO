# ADR-0005: Recovery validates continuation; it does not restore runtime state

Status: Accepted
Date: 2026-08-17

## Context

Durable runtimes can persist and restore workflow or agent checkpoints. Restoring bytes does not prove that the restored assumptions, dependencies, semantic environment, or write ownership are still valid against current reality.

HOWEDO must preserve its product boundary: external runtimes own checkpoint persistence and replay; HOWEDO owns continuation validity.

## Decision

R4 introduces a content-addressed `RecoveryCheckpoint` continuity manifest containing:

- the exact HOWEDO `ContinuitySnapshot`
- optional fencing tokens for resources the restored execution may write

`RecoveryEngine.validate()` composes the existing kernel layers:

1. `SEMLOCK` through `DecisionEngine` semantic comparison
2. `RECALL` through current validity metadata
3. `CONCUR` through expected-head and fencing checks

A successful validation returns `RECOVER`. This means the externally restored checkpoint is valid to resume; HOWEDO has not restored, replayed, or executed the runtime itself.

Fail-conservative outcomes are:

- exact valid snapshot + valid write fences -> `RECOVER`
- stale/invalid dependency -> `REVALIDATE` or `ABORT`
- unknown state or missing current fence -> `PAUSE`
- changed write head -> `REVALIDATE`, even when the semantic change is compatible
- stale fencing token -> `ABORT`

## Integrity

`RecoveryCheckpoint` and `RecoveryWitness` are deterministic and content-addressed. The checkpoint digest covers HOWEDO continuity metadata, not the external runtime checkpoint bytes. Runtime adapters may bind their own checkpoint identifier or artifact digest in a later adapter/protocol layer.

## Boundary

R4 does not introduce:

- checkpoint storage
- workflow replay
- process restoration
- scheduler semantics
- Temporal or LangGraph dependencies
- CASER or V-One runtime dependencies
- distributed locking

External runtimes restore execution. HOWEDO decides whether that restored execution is still valid to continue.

## Consequences

- persistence remains replaceable infrastructure
- recovery cannot silently bypass SEMLOCK, RECALL, or CONCUR
- read-only compatible drift may resume
- write-capable recovery retains stricter expected-head/fencing requirements
- every recovery decision can be reproduced from recorded continuity inputs

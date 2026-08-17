# HOWEDO Constitution

## Mission

HOWEDO determines whether a long-lived or autonomous agent can safely continue using the exact state, assumptions, dependencies, and execution context on which its work depends.

## Product boundary

HOWEDO owns continuity semantics. It does not own generic agent orchestration, durable execution, memory storage, IAM/RBAC, secrets management, sandboxing, prompt management, generic observability, or human approval workflows.

External runtimes and infrastructure are integrated through explicit adapters. The kernel must remain usable without LangGraph, Temporal, AWS AgentCore, CASER, V-One, or any other single vendor or product.

## Core subsystems

1. State Registry — resource identity, immutable revisions, authoritative heads.
2. SEMLOCK — execution-context snapshots and semantic compatibility.
3. RECALL — dependency lineage, freshness, invalidation, revalidation.
4. CONCUR — expected-head validation, conflict detection, fencing.
5. Recovery — validation of restored state against current reality.
6. Decision Engine — deterministic continuity decisions.
7. Continuity Witness — reproducible evidence describing why a decision was made.

## Public decision contract

- CONTINUE
- PAUSE
- REVALIDATE
- ABORT
- RECOVER

## Non-negotiable invariants

I1. Revisions are immutable.
I2. Every decision references an exact state snapshot.
I3. A changed authoritative dependency cannot silently remain valid.
I4. A stale writer cannot advance a newer authoritative head.
I5. Recovery never implies validity.
I6. Persistence is not continuity.
I7. UNKNOWN is never silently promoted to VALID.
I8. External adapters cannot mutate kernel semantics.
I9. LLM judgment cannot directly commit authoritative state.
I10. A continuity decision must be reproducible from recorded canonical inputs.

## Dependency policy

The core package uses Python standard-library primitives first. Vendor SDKs live behind optional adapter packages/modules. A vendor integration may be removed without changing the canonical domain model or decision semantics.

## Change policy

Any change to canonical resource identity, revision semantics, decision values, witness schema, or an invariant requires an ADR and compatibility review.

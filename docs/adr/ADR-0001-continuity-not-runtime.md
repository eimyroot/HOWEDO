# ADR-0001: HOWEDO owns continuity semantics, not durable execution

- Status: Accepted
- Date: 2026-08-17

## Context

Modern agent runtimes already provide durable execution primitives. LangGraph persists graph state as checkpoints and supports replay/resume. Temporal provides an open-source durable execution platform that resumes workflows after failures. PostgreSQL provides mature transaction isolation and locking primitives suitable for the first authoritative state store.

Reimplementing these layers would create cost, operational complexity, and vendor-shaped architecture without creating HOWEDO's core differentiation.

## Decision

HOWEDO will remain runtime-neutral.

The kernel owns:

- immutable resource revisions and authoritative heads;
- exact execution-context snapshots;
- semantic drift classification;
- dependency invalidation and revalidation;
- expected-head/fencing semantics;
- recovery validity checks;
- deterministic continuity decisions;
- continuity witnesses.

Durable execution, checkpoint storage, workflow scheduling, retries, and runtime-specific resume mechanics remain external responsibilities exposed through adapters.

## Consequences

### Positive

- LangGraph and Temporal can be reused without becoming architectural dependencies.
- HOWEDO can integrate with future runtimes without redesigning the kernel.
- Local development can remain inexpensive and self-hostable.
- Product differentiation stays focused on validity across changing reality.

### Negative

- Adapter conformance becomes a first-class testing obligation.
- Runtime-specific guarantees must never be assumed by the kernel.

## Rejected alternatives

1. Build a proprietary agent runtime — rejected as duplication and scope explosion.
2. Build directly on LangGraph internals — rejected because it creates framework lock-in.
3. Build directly on Temporal workflow semantics — rejected because HOWEDO must also support non-Temporal agents.

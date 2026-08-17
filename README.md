# HOWEDO

**Continuity infrastructure for long-lived and autonomous AI agents.**

HOWEDO determines whether an agent can safely continue after the reality it depends on has changed.

## Product boundary

HOWEDO is **not** an agent runtime, workflow engine, memory database, IAM system, sandbox, or observability platform.

It is a vendor-neutral continuity and integrity control plane that evaluates exact state revisions, dependency validity, semantic compatibility, concurrent writes, and recovery validity.

## Core decision contract

Every continuity check resolves to one of:

- `CONTINUE`
- `PAUSE`
- `REVALIDATE`
- `ABORT`
- `RECOVER`

## Core subsystems

- **State Registry** — immutable resource identities and revisions.
- **SEMLOCK** — semantic snapshot and compatibility checks.
- **RECALL** — dependency graph and propagated invalidation.
- **CONCUR** — expected-head checks, fencing, and conflict detection.
- **Recovery** — validates restored state against current reality.
- **Decision Engine** — deterministic continuity decisions.
- **Continuity Witness** — reproducible evidence of each decision.

## Integrations

Runtimes and platforms are adapters, never required dependencies. Planned adapters include LangGraph, Temporal, OpenAI, AWS AgentCore, custom Python agents, CASER, and V-One.

## Canonical invariant

> Persistence tells you what the agent knew. HOWEDO determines whether it is still valid to act on it.

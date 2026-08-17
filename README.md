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

## R0-R6 baseline

The current integration baseline contains:

- deterministic continuity kernel and witness contract;
- SEMLOCK semantic drift classification;
- RECALL dependency invalidation;
- CONCUR expected-head and fencing checks;
- recovery validity / safe-resume gating;
- stable `howedo.protocol.v1` schemas;
- optional PostgreSQL reference persistence adapter;
- optional LangGraph OSS runtime adapter.

## Installation profiles

The core package has no required runtime dependencies:

```bash
pip install howedo-continuity
```

Optional adapters are isolated extras:

```bash
pip install 'howedo-continuity[postgres]'
pip install 'howedo-continuity[langgraph]'
pip install 'howedo-continuity[postgres,langgraph]'
```

## Integrations

**Implemented reference adapters:**

- PostgreSQL — persistence/reference storage adapter.
- LangGraph OSS — exact checkpoint binding and HOWEDO-gated resume through the public LangGraph API.

**Future adapters:** Temporal, OpenAI, AWS AgentCore, custom Python runtimes, CASER, and V-One.

Adapters never own HOWEDO continuity semantics and are not required dependencies of the core package.

## Canonical invariant

> Persistence tells you what the agent knew. HOWEDO determines whether it is still valid to act on it.

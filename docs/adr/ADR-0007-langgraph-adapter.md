# ADR-0007: LangGraph adapter validates exact checkpoint resume

Status: Accepted
Date: 2026-08-17

## Context

LangGraph already owns checkpoint persistence, thread state, replay and interrupt/resume behavior. HOWEDO must integrate without replacing `BaseCheckpointSaver` or depending on a specific saver backend.

## Decision

R6 introduces the first real runtime adapter under `howedo.adapters.langgraph`.

The adapter:

- reads the public LangGraph `StateSnapshot` through `graph.get_state(config)`
- binds the exact `thread_id`, `checkpoint_id` and optional `checkpoint_ns`
- adds the installed LangGraph package version as tracked resource `runtime://langgraph`
- binds that runtime checkpoint to a HOWEDO `RecoveryCheckpoint`
- verifies the exact LangGraph checkpoint is still resolvable before resume
- executes R4 recovery validity against current HOWEDO heads/fences/validity
- invokes `Command(resume=...)` only when HOWEDO returns `RECOVER`
- supports static-breakpoint resume through `graph.invoke(None, config=...)` under the same gate

## Vendor neutrality

A generic `RuntimeAdapter` protocol is added. LangGraph-specific types stay inside the optional adapter module. Importing the HOWEDO kernel does not import LangGraph.

The `langgraph` dependency is an optional package extra, not a core dependency.

## Checkpoint binding integrity

`LangGraphRecoveryBinding` is content-addressed over:

- runtime kind
- thread ID
- checkpoint ID
- checkpoint namespace
- HOWEDO recovery checkpoint ID
- HOWEDO protocol version

A forged binding digest is rejected.

## Runtime drift

The adapter automatically tracks the installed LangGraph package version as `runtime://langgraph`. If the runtime version changes between capture and resume, normal SEMLOCK behavior applies: it does not silently become compatible. An explicit semantic comparator may classify a known upgrade as compatible.

## Boundary

R6 does not:

- implement or subclass a LangGraph checkpointer
- persist LangGraph checkpoint bytes
- read LangGraph internal checkpoint tables
- own replay scheduling
- own thread lifecycle
- add LangSmith or Agent Server dependency
- introduce an LLM dependency

LangGraph decides how to persist and restore execution. HOWEDO decides whether the exact restored checkpoint may safely continue.

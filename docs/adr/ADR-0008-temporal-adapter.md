# ADR-0008 — Temporal OSS runtime adapter

Status: Proposed for R7

## Context

HOWEDO must prove that its continuity semantics are independent of LangGraph. Temporal OSS is a materially different durable execution runtime: workflow state is replayed from Temporal history and external callers interact with executions through workflow handles, signals, updates, cancellation, and termination.

HOWEDO must not become a Temporal persistence layer or depend on Temporal internals. The integration must therefore use only public Temporal Python SDK contracts and preserve exact execution identity.

## Decision

R7 adds an optional `temporal` installation profile and `TemporalRuntimeAdapter`.

The adapter binds a HOWEDO `RecoveryCheckpoint` to an exact Temporal execution identity:

- namespace;
- workflow ID;
- run ID;
- first execution run ID when the SDK handle provides it;
- installed Temporal Python SDK revision as `runtime://temporal-python`.

The binding is content-addressed and includes the HOWEDO protocol version.

Before a continuation signal is delivered, the adapter:

1. reconstructs a Temporal handle targeted to the exact bound `run_id`;
2. calls public `describe()` and requires the exact run to still be `RUNNING`;
3. validates the HOWEDO recovery checkpoint against current resource heads, semantic validity, runtime revision, and optional CONCUR fences;
4. requires the HOWEDO decision to be `RECOVER`;
5. sends the signal through the exact-run handle.

If the workflow run has completed, failed, terminated, timed out, or continued as new, the old binding does not silently move to another run. A new HOWEDO binding is required for the successor execution.

## Boundary

HOWEDO does not:

- store Temporal workflow history;
- replace Temporal persistence;
- own workflow scheduling or task queues;
- inject code into Temporal workflow replay;
- depend on Temporal server database internals;
- redirect a bound continuation to the latest execution sharing the workflow ID.

`temporalio` remains an optional dependency. HOWEDO core retains zero required runtime dependencies.

## Concurrency note

HOWEDO validation and Temporal signal delivery are separate network operations. Exact `run_id` targeting prevents the signal from being redirected to a successor or unrelated run, but it does not make external HOWEDO resource validation and Temporal signal delivery one distributed transaction. Callers that require write concurrency protection must use HOWEDO CONCUR fences/expected-head semantics around the authoritative resources they mutate.

## Verification

R7 must pass:

- Python 3.12 and 3.13 package/import conformance;
- core-only zero-dependency gate;
- Temporal-only optional profile;
- combined PostgreSQL + LangGraph + Temporal profile;
- unit tests for exact-run binding, namespace drift, closed-run rejection, binding integrity, and changed-reality blocking;
- real Temporal test-server integration showing a valid signal succeeds, changed reality blocks the signal, and a closed bound run cannot be resumed.

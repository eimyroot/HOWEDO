# ADR-0009 — Runtime Adapter Contract v1

## Status

Proposed in R8.

## Context

HOWEDO now has verified runtime integrations for LangGraph OSS and Temporal OSS. The two runtimes expose different continuation models, but both require the same HOWEDO invariants: exact runtime identity, captured continuity state, validation against current reality, and continuation only after `RECOVER`.

Without a stable adapter contract, future integrations would drift into bespoke wrappers and HOWEDO would risk becoming coupled to whichever runtime was implemented most recently.

## Decision

Introduce `howedo.runtime-adapter.v1` as a vendor-neutral adapter contract and ship an executable conformance kit.

The contract standardizes only:

1. adapter capability manifest;
2. exact runtime identity;
3. capture binding;
4. resume validation;
5. continuation after validation;
6. normalized adapter failure categories.

Reference bridges for LangGraph and Temporal prove that the same contract can represent both checkpoint/thread and workflow/run execution models.

## Consequences

### Positive

- new runtime integrations can be developed independently;
- adapters can be tested against shared HOWEDO invariants;
- vendor-specific execution semantics remain outside the kernel;
- adapter capability discovery becomes deterministic;
- third-party adapters can be versioned independently from HOWEDO core.

### Negative

- adapter bridges introduce a compatibility layer over existing native adapters;
- distributed atomicity between a HOWEDO decision and a remote runtime continuation remains outside this protocol;
- runtimes that cannot expose exact execution identity may fail conformance rather than receiving a weaker compatibility mode.

## Non-goals

The contract does not define runtime storage, scheduling, replay, queues, workflow code, worker lifecycle, IAM, secrets, or deployment.

## Compatibility rule

A future breaking adapter-contract change requires a new contract identifier. `howedo.runtime-adapter.v1` is not silently redefined in place.

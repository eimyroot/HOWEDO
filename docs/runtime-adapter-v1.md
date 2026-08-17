# HOWEDO Runtime Adapter Contract v1

Contract identifier: `howedo.runtime-adapter.v1`

## Purpose

A runtime adapter connects an external execution runtime to HOWEDO without transferring ownership of runtime persistence, replay, scheduling, task delivery, or workflow semantics to HOWEDO.

The adapter answers only four questions:

1. What exact runtime execution/checkpoint is being bound?
2. What HOWEDO continuity snapshot was captured with it?
3. Does that exact binding remain safe to continue under current reality?
4. If and only if HOWEDO returns `RECOVER`, how is the runtime continuation delivered to that exact execution?

## Mandatory capabilities

A conforming v1 adapter declares and implements:

- `EXACT_RUNTIME_IDENTITY`
- `CAPTURE`
- `VALIDATE_RESUME`
- `CONTINUE`

Optional capabilities include:

- `READ_ONLY_VALIDATE`
- `FENCED_WRITES`

Capability declarations are part of a canonical `AdapterManifest`. The manifest is content-addressed with SHA-256.

## Exact identity

`RuntimeIdentity` is vendor-neutral and contains:

- `runtime_family`
- `namespace`
- `execution_id`
- `execution_revision`

Adapters MAY retain richer vendor-specific binding data, but they MUST expose a stable exact identity through these four fields.

Examples:

- LangGraph: execution ID can represent the thread, execution revision the exact checkpoint ID.
- Temporal: execution ID can represent the workflow ID, execution revision the exact run ID.

A continuation MUST NOT silently retarget to a latest/successor execution when the bound identity no longer exists or is no longer continuable.

## Capture

Capture MUST bind:

- exact runtime identity;
- HOWEDO `RecoveryCheckpoint` or equivalent HOWEDO recovery binding;
- adapter manifest digest.

The adapter MUST include its runtime implementation revision in the captured HOWEDO resources.

## Validate

`validate_resume` MUST run HOWEDO continuity/recovery validation against current authoritative reality before any continuation side effect.

A changed, stale, invalid, unknown, fenced, or otherwise incompatible reality MUST resolve through HOWEDO actions and reason codes. Runtime adapters MUST NOT invent a weaker local decision that overrides HOWEDO.

## Continue

A continuation side effect MUST occur only after validation returns `RECOVER`.

The continuation operation MUST target the exact bound runtime identity. If the runtime cannot guarantee exact targeting for an operation, the adapter MUST reject the operation or declare that capability unsupported.

HOWEDO validation and a remote runtime continuation call are normally separate operations. The adapter contract therefore does not claim distributed atomicity across HOWEDO and the runtime. Authoritative writes requiring atomic concurrency protection remain subject to HOWEDO CONCUR expected-head/fencing semantics and backend transaction guarantees.

## Failure model

Normalized adapter failure codes:

- `IDENTITY_UNRESOLVED`
- `IDENTITY_MISMATCH`
- `EXECUTION_NOT_CONTINUABLE`
- `CONTINUITY_BLOCKED`
- `UNSUPPORTED_CAPABILITY`
- `PROTOCOL_VIOLATION`

Vendor exceptions may be retained as causes, but SDK-facing behavior SHOULD expose one of these stable categories.

## Conformance

A v1 conformance run verifies at minimum:

1. contract version is exact;
2. required capabilities are declared;
3. manifest is deterministic/content-addressed;
4. runtime family in identity matches the manifest;
5. binding uses the resolved exact identity;
6. binding carries the exact manifest digest;
7. unchanged authoritative reality resolves to `RECOVER`;
8. changed authoritative reality never resolves to `RECOVER`.

Reference adapters SHOULD add runtime-specific tests proving exact continuation targeting and rejection of unavailable/closed/superseded executions.

## Boundary

The adapter contract does not standardize the runtime itself. It intentionally does not define:

- workflow scheduling;
- runtime storage;
- checkpoint bytes;
- replay engines;
- worker lifecycle;
- queue semantics;
- IAM or secrets;
- runtime-specific deployment.

Those remain external runtime responsibilities.

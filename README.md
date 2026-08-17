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

## R0-R10 baseline

The current development baseline contains:

- deterministic continuity kernel and witness contract;
- SEMLOCK semantic drift classification;
- RECALL dependency invalidation;
- CONCUR expected-head and fencing checks;
- recovery validity / safe-resume gating;
- stable `howedo.protocol.v1` schemas;
- optional PostgreSQL reference persistence adapter;
- optional LangGraph OSS runtime adapter;
- optional Temporal OSS Python runtime adapter;
- vendor-neutral `howedo.runtime-adapter.v1` contract;
- executable runtime-adapter conformance kit;
- third-party adapter SDK surface and reference bridges;
- content-addressed `howedo.adapter-conformance-artifact.v1` records;
- core-only conformance artifact verifier and CLI;
- CI-produced evidence artifacts for LangGraph and Temporal reference adapters;
- in-toto Statement v1 binding for exact conformance artifacts;
- core-only attestation builder and semantic verifier CLIs;
- Sigstore keyless reference signing through GitHub Actions OIDC.

## Installation profiles

The core package has no required runtime or cryptography dependencies:

```bash
pip install howedo-continuity
```

The adapter contract, conformance kit, artifact verifier, attestation statement builder/verifier, and SDK helpers are part of core and do not require a runtime vendor SDK or signing library.

Optional reference adapters are isolated extras:

```bash
pip install 'howedo-continuity[postgres]'
pip install 'howedo-continuity[langgraph]'
pip install 'howedo-continuity[temporal]'
pip install 'howedo-continuity[postgres,langgraph,temporal]'
```

## Runtime adapter contract

`howedo.runtime-adapter.v1` defines the narrow interoperability boundary for external runtimes:

```text
exact runtime identity
        ↓
capture HOWEDO recovery binding
        ↓
validate against current reality
        ↓
RECOVER only
        ↓
continue exact bound execution
```

A conforming adapter declares a content-addressed capability manifest and exposes exact identity, capture, validation, and continuation operations. The shared conformance kit verifies the vendor-neutral invariants; runtime-specific fixtures prove exact targeting and real continuation behavior.

See `docs/runtime-adapter-v1.md`, `docs/third-party-adapters.md`, and `examples/third_party_runtime_adapter.py`.

## Conformance artifacts

R9 turns a conformance run into a portable JSON record:

```text
runtime fixture
      ↓
RuntimeAdapterV1 conformance
      ↓
11 frozen checks
      ↓
ConformanceArtifact
      ├── exact adapter manifest
      ├── manifest digest
      ├── environment
      ├── evidence refs
      ├── derived status
      └── artifact digest
```

A saved artifact can be verified without installing LangGraph, Temporal, PostgreSQL, or another runtime SDK:

```bash
howedo-verify-conformance artifact.json
```

The R9 artifact is content-addressed. Its digest detects record changes and binds the included evidence.

See `docs/adapter-conformance-artifact-v1.md` and `docs/adr/ADR-0010-adapter-conformance-artifact-v1.md`.

## Signed conformance attestations

R10 authenticates a conformance claim without changing the R9 artifact:

```text
R9 artifact
    ↓
in-toto Statement/v1
    ↓
exact subject SHA-256 binding
    ↓
HOWEDO semantic verification
    ↓
Sigstore keyless signature bundle
    ↓
expected GitHub workflow identity verification
```

Build and semantically verify a statement with core-only commands:

```bash
howedo-build-attestation artifact.json artifact.intoto.json
howedo-verify-attestation artifact.json artifact.intoto.json
```

The reference CI path then signs the statement with Sigstore/Cosign using GitHub Actions OIDC. No long-lived signing key is stored by HOWEDO.

A complete R10 acceptance requires all three checks:

```text
R9 artifact integrity
AND R10 statement semantic binding
AND Sigstore signer / transparency verification
```

R10 does not grant execution authority and does not implement a custom PKI, custom transparency log, or custom cryptographic signature format.

See `docs/signed-conformance-attestation-v1.md` and `docs/adr/ADR-0011-signed-conformance-attestation.md`.

## Integrations

**Implemented reference adapters:**

- PostgreSQL — persistence/reference storage adapter.
- LangGraph OSS — exact checkpoint binding and HOWEDO-gated resume through the public LangGraph API.
- Temporal OSS — exact workflow-run binding and HOWEDO-gated signal delivery through the public Temporal Python SDK.

The Temporal adapter deliberately binds `namespace + workflow_id + run_id`. A continuation request is never redirected to an unrelated or successor run merely because it shares the same workflow ID. The bound run must still be `RUNNING`, and HOWEDO recovery validity must resolve to `RECOVER`, before the adapter sends the signal.

**Future adapters:** OpenAI, AWS AgentCore, custom Python runtimes, CASER, and V-One.

Adapters never own HOWEDO continuity semantics and are not required dependencies of the core package.

## Canonical invariant

> Persistence tells you what the agent knew. HOWEDO determines whether it is still valid to act on it.

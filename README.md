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

## R0-R13 baseline

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
- Sigstore keyless reference signing through GitHub Actions OIDC;
- content-addressed `howedo.attestation-trust-policy.v1` consumer policies;
- deterministic `ACCEPT` / `REJECT` attestation trust evaluation;
- Sigstore/Cosign reference crypto-verifier adapter;
- standard in-toto Simple Verification Result v0.2 trust receipts;
- content-addressed `howedo.consumer-trust-profile.v1` relying-party expectations;
- portable `howedo.certification-package.v1` evidence packages;
- independent consumer replay of the R9 → R11 chain, including cryptographically verified GitHub workflow-name claims and pinned consumer-profile digests;
- optional TUF trust-root distribution and rotation for consumer trust profiles;
- content-addressed `howedo.trust-distribution-receipt.v1` update evidence.

## Installation profiles

The core package has no required runtime or cryptography dependencies:

```bash
pip install howedo-continuity
```

The adapter contract, conformance kit, artifact verifier, attestation statement builder/verifier, trust policy engine, consumer certification verifier, trust-distribution contract, and SDK helpers are part of core and do not require a runtime vendor SDK or signing library merely to import HOWEDO.

Optional integrations are isolated extras:

```bash
pip install 'howedo-continuity[postgres]'
pip install 'howedo-continuity[langgraph]'
pip install 'howedo-continuity[temporal]'
pip install 'howedo-continuity[tuf]'
pip install 'howedo-continuity[postgres,langgraph,temporal,tuf]'
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

R9 turns a conformance run into a portable content-addressed JSON record. A saved artifact can be verified without installing LangGraph, Temporal, PostgreSQL, or another runtime SDK:

```bash
howedo-verify-conformance artifact.json
```

See `docs/adapter-conformance-artifact-v1.md` and `docs/adr/ADR-0010-adapter-conformance-artifact-v1.md`.

## Signed conformance attestations

R10 binds an exact R9 artifact to an in-toto Statement v1 and uses Sigstore/Cosign with GitHub Actions OIDC as the reference keyless signing path:

```text
R9 artifact
    ↓
in-toto Statement/v1
    ↓
HOWEDO semantic verification
    ↓
Sigstore keyless signature bundle
    ↓
expected workflow identity verification
```

Core-only commands build and verify the semantic binding:

```bash
howedo-build-attestation artifact.json artifact.intoto.json
howedo-verify-attestation artifact.json artifact.intoto.json
```

See `docs/signed-conformance-attestation-v1.md` and `docs/adr/ADR-0011-signed-conformance-attestation.md`.

## Attestation trust policy

R11 evaluates authenticated R10 evidence against a deterministic consumer policy and emits a standard in-toto Simple Verification Result v0.2:

```text
R9 integrity
AND R10 semantic binding
AND external crypto verification
AND HOWEDO trust policy
        ↓
ACCEPT / REJECT
        ↓
in-toto SVR v0.2
```

The reference verifier is:

```bash
howedo-verify-sigstore-trust ...
```

The production reference policy accepts only the canonical workflow on `refs/heads/main`; pull requests use a separate test-only policy.

See `docs/attestation-trust-policy-v1.md` and `docs/adr/ADR-0012-attestation-trust-policy.md`.

## Consumer certification replay

R12 lets a relying consumer replay the certification chain independently instead of trusting a producer-generated `ACCEPT` as an oracle:

```text
portable certification package
        ↓
consumer trust profile
        ↓
file-digest verification
        ↓
R9 + R10 replay
        ↓
Sigstore verification
        ↓
pinned R11 policy identity/digest
        ↓
local R11 policy + SVR replay
        ↓
R11 SVR signature verification
        ↓
ACCEPT / REJECT
```

`howedo.consumer-trust-profile.v1` pins relying-party expectations independently of the package. `howedo.certification-package.v1` is transport/index material over authenticated R9/R10/R11 evidence; it is not a new PKI or a producer-controlled trust root.

See `docs/consumer-certification-v1.md` and `docs/adr/ADR-0013-consumer-certification-replay.md`.

## Trust-root distribution and rotation

R13 removes the need to replace a pinned R12 consumer-profile digest manually forever while preserving an independently bootstrapped trust anchor.

```text
out-of-band trusted TUF root
        ↓
TUF metadata refresh
        ├── sequential root rotation
        ├── freshness / expiry checks
        ├── rollback protection
        └── target length + hash verification
        ↓
verified howedo.consumer-trust-profile.v1 target
        ↓
HOWEDO profile validation
        ↓
howedo.trust-distribution-receipt.v1
```

The TUF repository URL is not the trust root. The initial TUF root bytes must arrive through an independently trusted bootstrap channel. HOWEDO records their SHA-256 digest, the final trusted TUF root version, exact target hashes, and resulting consumer-profile digest in the update receipt.

Reference CLI:

```bash
howedo-fetch-consumer-trust-profile \
  --bootstrap-root root.json \
  --metadata-dir .howedo/tuf/metadata \
  --metadata-base-url https://example.invalid/metadata/ \
  --target-dir .howedo/tuf/targets \
  --target-base-url https://example.invalid/targets/ \
  --profile-output consumer-profile.json \
  --receipt-output trust-update-receipt.json
```

HOWEDO does not implement a TUF-like metadata format, repository server, PKI, or key ceremony. TUF remains an optional distribution/rotation substrate.

See `docs/adr/ADR-0014-tuf-trust-root-distribution.md`.

## Canonical change channel

Canonical `main` is protected by the active repository ruleset **`HOWEDO canonical main protection`** (ruleset id `20928865`). The ruleset has no bypass actors and requires the exact GitHub Actions checks used by the project before merge.

The protected channel requires a pull request, resolved review threads, strict required checks, merge commits, and blocks deletion plus non-fast-forward / force-push updates. `Canonical Channel / provenance` additionally verifies that a resulting `main` head is attributable to a merged PR targeting `main`.

Repository governance is therefore preventive as well as evidence-producing; it is separate from HOWEDO runtime semantics.

See `docs/governance/CANONICAL_CHANNEL_PROTECTION.md`.

## Integrations

**Implemented reference integrations:**

- PostgreSQL — persistence/reference storage adapter.
- LangGraph OSS — exact checkpoint binding and HOWEDO-gated resume through the public LangGraph API.
- Temporal OSS — exact workflow-run binding and HOWEDO-gated signal delivery through the public Temporal Python SDK.
- Sigstore/Cosign — external cryptographic verification for the R10–R12 reference trust flow.
- The Update Framework (TUF) — optional consumer trust-profile bootstrap, distribution, integrity, freshness, and root-rotation substrate.

The Temporal adapter deliberately binds `namespace + workflow_id + run_id`. A continuation request is never redirected to an unrelated or successor run merely because it shares the same workflow ID. The bound run must still be `RUNNING`, and HOWEDO recovery validity must resolve to `RECOVER`, before the adapter sends the signal.

**Future adapters:** OpenAI, AWS AgentCore, custom Python runtimes, CASER, and V-One.

Adapters never own HOWEDO continuity semantics and are not required dependencies of the core package.

## Canonical invariant

> Persistence tells you what the agent knew. HOWEDO determines whether it is still valid to act on it.

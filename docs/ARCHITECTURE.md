# HOWEDO Architecture

Status: **canonical scaffold for the pre-1.0 repository**

This document defines where new code belongs, which direction dependencies may flow, and which
boundaries must remain stable as HOWEDO grows.

## Architectural objective

HOWEDO is a continuity and integrity control plane. It is not an agent runtime, workflow engine,
memory database, IAM system, sandbox, or observability platform.

The primary architectural requirement is therefore separation of **continuity semantics** from
presentation, deployment, persistence, and vendor-runtime integration.

## Layer model

### 1. Presentation boundary

Paths:

```text
src/howedo/api/
```

Responsibilities:

- FastAPI HTTP surface;
- request/response transport models;
- operator cockpit;
- OpenAPI exposure;
- transport-level health/readiness.

Rules:

- may call application/service functions;
- must not implement continuity decision rules;
- cockpit code must not become a second source of truth;
- browser assets must remain self-contained unless an explicit supply-chain decision says otherwise.

### 2. Application/service boundary

Paths:

```text
src/howedo/api/service.py
src/howedo/api/models.py
```

Responsibilities:

- translate validated transport models into kernel types;
- invoke continuity/recovery services;
- translate kernel results back to stable API responses.

Rules:

- no vendor-runtime orchestration;
- no persistence ownership;
- no hidden policy defaults that change kernel semantics.

### 3. Continuity kernel

Representative paths:

```text
src/howedo/domain.py
src/howedo/kernel.py
src/howedo/semlock.py
src/howedo/recall.py
src/howedo/concur.py
src/howedo/recovery.py
src/howedo/protocol.py
```

Responsibilities:

- exact revision identity;
- semantic compatibility;
- dependency invalidation;
- fencing and concurrency safety;
- recovery validity;
- deterministic decisions and evidence.

Rules:

- core imports must remain vendor-neutral;
- continuity actions are determined here, not in adapters;
- deterministic evidence contracts are part of the compatibility surface.

### 4. Evidence, certification, and trust

Representative paths:

```text
src/howedo/adapter_conformance.py
src/howedo/adapter_certification.py
src/howedo/attestation.py
src/howedo/consumer_trust.py
src/howedo/certification_package.py
src/howedo/trust_distribution.py
src/howedo/trust_publication.py
src/howedo/release_bundle.py
```

Responsibilities:

- portable conformance evidence;
- in-toto binding;
- trust-policy evaluation;
- independent consumer replay;
- TUF-assisted trust distribution;
- release-bundle integrity.

Rules:

- cryptographic verification is distinct from semantic verification;
- producer evidence is not automatically consumer authority;
- production private trust-root keys remain outside the repository and CI.

### 5. Adapters and storage

Paths:

```text
src/howedo/adapters/
src/howedo/storage/
```

Responsibilities:

- translate external runtime identity into HOWEDO contracts;
- bind exact runtime/checkpoint identity;
- provide optional persistence implementations.

Rules:

- adapters never own HOWEDO continuity semantics;
- runtime continuation is permitted only after the required HOWEDO decision;
- optional vendor SDKs must remain isolated behind extras.

## Dependency direction

Preferred dependency flow:

```text
cockpit / HTTP
      ↓
API service mapping
      ↓
continuity kernel
      ↓
protocol / evidence contracts

runtime adapter ───────────────→ continuity kernel
storage adapter ───────────────→ storage/kernel contracts
trust verifier ────────────────→ evidence/trust contracts
```

Forbidden direction examples:

```text
kernel → FastAPI
kernel → LangGraph
kernel → Temporal
kernel → PostgreSQL driver
kernel → cockpit HTML/JavaScript
```

The core package must remain importable without installing optional runtime, API, database, TUF, or
release-tool dependencies.

## Repository scaffold

```text
HOWEDO/
├── .github/
│   ├── CODEOWNERS
│   ├── pull_request_template.md
│   └── workflows/
├── docs/
│   ├── adr/
│   ├── governance/
│   ├── operations/
│   └── assets/
├── examples/
├── policies/
├── schemas/
├── scripts/
├── src/howedo/
│   ├── adapters/
│   ├── api/
│   └── storage/
└── tests/
    ├── api/
    ├── conformance/
    └── integration/
```

### Placement rule

Before adding a new top-level directory, answer all three questions:

1. Why can the content not live in an existing bounded context?
2. What is its ownership and dependency direction?
3. Which automated check proves that the new boundary remains valid?

If those answers are unclear, do not create the directory.

## Cockpit boundary

The cockpit is served at:

```text
GET /
GET /cockpit
```

It is deliberately implemented inside the existing FastAPI deployment to avoid a second build
toolchain, JavaScript package supply chain, deployment artifact, and version-skew boundary.

The cockpit may:

- read health/readiness;
- call documented HOWEDO API endpoints;
- visualize deterministic API output;
- link to OpenAPI documentation.

The cockpit must not:

- bypass API validation;
- mutate kernel state directly;
- invent a second decision model;
- conceal failed or unavailable checks;
- load third-party browser code without an explicit reviewed decision.

## Security and operational boundaries

- Default local cockpit bind: `127.0.0.1`.
- Docker runtime remains non-root.
- The compose profile binds the host port to loopback by default.
- Production deployment authority is an immutable OCI image digest, not a mutable tag.
- A green test or workflow only proves the scope exercised by that check.

## Quality gates

Repository changes should satisfy:

```bash
ruff check .
pytest
python scripts/check_repo_hygiene.py
```

The hygiene check verifies required scaffold paths and rejects tracked local/generated artifacts.
It is intentionally narrow: architecture correctness is still enforced by tests, reviews, ADRs, and
dependency discipline rather than by pretending a filename check is a security proof.

## Change policy

Use an ADR when a change:

- moves continuity semantics across a layer boundary;
- introduces a required runtime dependency;
- changes a public protocol or evidence contract;
- changes trust authority or cryptographic verification behavior;
- introduces a new execution/runtime adapter contract;
- changes the production release or trust-root boundary.

Presentation-only cockpit refinements do not require an ADR unless they change one of those
boundaries.

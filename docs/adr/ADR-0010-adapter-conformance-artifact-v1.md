# ADR-0010 — Adapter Conformance Artifact v1

Status: Accepted for R9 implementation

## Context

R8 established `howedo.runtime-adapter.v1` and an executable vendor-neutral conformance suite. The suite can prove that an adapter resolves exact execution identity, captures continuity state, blocks changed reality, and only continues after HOWEDO returns `RECOVER`.

The result was still ephemeral test output. A third party could not carry the result into an evidence system, independently detect record tampering, or compare an adapter claim with the exact tested manifest and check set.

## Decision

Introduce a separate immutable artifact format:

`howedo.adapter-conformance-artifact.v1`

The artifact binds:

- the exact adapter manifest and manifest digest;
- the frozen v1 conformance check sequence and per-check results;
- derived overall status;
- interpreter/platform environment metadata;
- caller-supplied evidence references;
- a SHA-256 digest over canonical JSON.

The format has its own schema namespace under `schemas/adapter-conformance-v1/`. It does not modify the frozen `schemas/runtime-adapter-v1/` set.

HOWEDO core also exposes a verifier that requires no optional runtime dependencies and a CLI for verifying saved records.

## Trust boundary

The artifact is content-addressed, not signed.

Its digest proves record integrity relative to the record presented to the verifier. It does not authenticate who created the record, establish third-party endorsement, or prevent an untrusted party from generating a different internally consistent record.

Signed attestations, issuer identity, trust roots, revocation, and transparency are explicitly deferred to a later protocol.

## Active-test boundary

The v1 conformance suite includes a real continuation check. Artifact generation may therefore cause a continuation side effect in the test runtime.

Certification fixtures must be isolated/disposable. R9 does not authorize running conformance against arbitrary production executions.

## Determinism

The artifact does not inject a wall-clock timestamp. Its digest is deterministic for the same manifest, results, environment metadata, and supplied evidence references.

Operational systems may wrap the artifact in independently timestamped or signed envelopes without changing the R9 core format.

## Consequences

Positive:

- `HOWEDO-compatible` can be backed by a portable machine-readable result rather than prose;
- tampering with a saved artifact is detectable;
- verification remains vendor-neutral and core-only;
- CI can publish concrete evidence for reference adapters;
- failed conformance can be preserved as valid negative evidence.

Trade-offs:

- the artifact is not issuer-authenticated;
- the check set becomes part of a versioned public contract;
- active continuation testing requires disposable fixtures;
- external timestamp/signature systems need a later envelope protocol.

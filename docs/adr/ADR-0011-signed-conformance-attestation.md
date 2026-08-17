# ADR-0011 — Signed conformance attestation

Status: Accepted

## Context

R9 introduced `howedo.adapter-conformance-artifact.v1`: a deterministic, content-addressed record of one runtime-adapter conformance run. The artifact can prove its own internal integrity and conformance consistency, but it cannot authenticate the entity that produced it.

HOWEDO needs an issuer-authenticated evidence layer without:

- inventing a custom signature format;
- storing long-lived signing keys in the repository or GitHub secrets;
- adding cryptography or runtime-vendor dependencies to the HOWEDO core package;
- weakening the R9 artifact digest or changing `howedo.runtime-adapter.v1`.

## Decision

R10 adds a signed attestation layer above R9.

### Semantic statement

HOWEDO builds an in-toto Statement v1:

- `_type`: `https://in-toto.io/Statement/v1`;
- exactly one subject named `howedo.adapter-conformance-artifact.v1`;
- subject `sha256` equals the exact R9 `artifact_digest` without the `sha256:` prefix;
- predicate type: `https://github.com/nulleimy/HOWEDO/attestations/adapter-conformance/v1`;
- predicate mirrors the adapter identity, manifest digest, conformance status/counts, artifact version, and evidence references from the exact R9 artifact.

The HOWEDO core verifies both the R9 artifact and the semantic binding between artifact and statement.

### Cryptographic authentication

HOWEDO does not implement signing primitives.

The reference CI path uses Sigstore/Cosign keyless blob signing:

1. GitHub Actions grants `id-token: write` only to the dedicated signing job.
2. Cosign obtains short-lived signing material from the GitHub OIDC identity through Sigstore.
3. The in-toto Statement JSON is signed as a blob and a Sigstore verification bundle is emitted.
4. CI verifies the bundle against the exact expected workflow identity, OIDC issuer, repository, workflow SHA, ref, and trigger.
5. CI separately runs the HOWEDO semantic verifier against the exact R9 artifact and statement.

No long-lived private signing key is stored by HOWEDO.

## Why not custom DSSE in R10

The in-toto Attestation Framework recommends DSSE for its envelope layer, but the current Sigstore bundle format is optimized around one Sigstore signature and is not itself the in-toto multi-signature envelope contract. R10 therefore does not implement a partial or custom DSSE layer merely to claim envelope compliance.

R10 uses:

- standard in-toto Statement v1 for semantics;
- standard Sigstore bundle verification for issuer authentication;
- explicit composition of those two verification results.

A future protocol may add an ITE-5/DSSE multi-signer envelope if HOWEDO develops a real multi-issuer requirement.

## Verification rule

A R10 signed conformance claim is accepted only when all three independent checks pass:

```text
R9 artifact integrity
        AND
R10 statement semantic binding
        AND
Sigstore signer / transparency verification
        =
SIGNED CONFORMANCE ATTESTATION ACCEPTED
```

A valid Sigstore signature over a statement bound to an invalid R9 artifact is rejected.

A valid R9 artifact with an unsigned or incorrectly signed statement is not a signed attestation.

A valid signature over a statement whose subject digest or predicate does not match the R9 artifact is rejected.

## Dependency boundary

The core package continues to have zero required runtime or cryptography dependencies.

`howedo.attestation` and the `howedo-build-attestation` / `howedo-verify-attestation` CLIs use the Python standard library plus existing HOWEDO core modules only.

Cosign is CI/tooling infrastructure, not a required HOWEDO Python dependency.

## Non-goals

R10 does not define:

- HOWEDO-owned certificate authorities;
- long-lived project signing keys;
- a custom PKI;
- a custom transparency log;
- generic software-supply-chain provenance;
- multi-party quorum signatures;
- revocation policy beyond the external trust system used for signature verification;
- authorization to execute an agent action.

The attestation authenticates a conformance evidence claim. It does not grant authority.

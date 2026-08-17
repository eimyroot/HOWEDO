# ADR-0013 — Consumer-Side Certification Replay

Status: Proposed for R12
Date: 2026-08-17

## Context

R9 produces content-addressed conformance evidence. R10 authenticates the conformance statement. R11 evaluates a consumer-facing trust policy and emits a signed in-toto SVR v0.2 result.

An SVR is intentionally a concise verification result, not a complete reproduction record. A relying consumer therefore still needs a trusted verifier expectation and a practical way to replay the underlying R9-R11 chain rather than trusting a producer-generated `ACCEPT` blindly.

## Decision

R12 adds two small consumer-side contracts:

1. `howedo.consumer-trust-profile.v1` — a content-addressed set of relying-party expectations that pins trusted SVR verifier IDs, exact R11 policy identity/digest, and allowed cryptographic signer claims.
2. `howedo.certification-package.v1` — a content-addressed transport manifest over the exact R9 artifact, R10 statement and Sigstore bundle, R11 policy, R11 SVR, and SVR Sigstore bundle.

The R12 verifier independently:

- verifies every package file digest;
- verifies R9 artifact integrity and R10 semantic binding;
- verifies the R10 signature through external Cosign;
- evaluates the R11 policy locally;
- deterministically replays the supplied R11 SVR;
- verifies the R11 SVR signature through external Cosign;
- applies the separately supplied consumer trust profile;
- fails closed on any mismatch.

## Trust-root boundary

The repository copy of a consumer trust profile is reference distribution material, not an automatically trusted root. A relying party must obtain or pin the expected profile through an independent channel. The reference CLI requires an externally supplied expected profile digest and rejects a self-consistent but differently addressed profile.

HOWEDO does not implement TUF, key rotation, threshold root signing, or revocation in R12. Those are distribution/root-management concerns and should be delegated to established systems such as TUF when required.

## Standards boundary

R12 does not invent a new attestation predicate. R10 remains in-toto Statement v1 and R11 remains in-toto SVR v0.2. The certification package is only a transport/index manifest over separately authenticated evidence.

The in-toto Bundle format groups authenticated envelopes, but the existing R10/R11 reference path uses detached Sigstore bundles. R12 therefore does not mislabel its package as an in-toto Bundle.

## Consequence

A consumer can independently answer: "Does this certification chain satisfy the trust profile I pinned?" without installing LangGraph or Temporal and without trusting the producer's `ACCEPT` as an oracle.

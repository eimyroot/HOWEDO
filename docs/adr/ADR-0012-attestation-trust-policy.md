# ADR-0012 — Attestation Trust Policy and Verification Result

- Status: Proposed for R11 merge gate
- Date: 2026-08-17

## Context

R9 creates content-addressed adapter conformance artifacts. R10 binds those artifacts into in-toto Statement/v1 records and authenticates the statement issuer through external Sigstore/Cosign keyless verification.

R10 answers whether the signed statement is authentic under a selected cryptographic identity check. It does not answer whether a consumer should trust that authenticated statement under its own acceptance rules.

A consumer-side trust policy is therefore required.

## Decision

HOWEDO will add `howedo.attestation-trust-policy.v1` as a small, deterministic, vendor-neutral policy contract.

The policy engine evaluates:

- validity of the R9 artifact;
- R10 artifact-to-statement semantic binding;
- success of an external cryptographic verifier;
- allowed verifier identity;
- allowed issuer;
- allowed signer identity pattern;
- repository;
- workflow;
- execution ref;
- workflow trigger;
- predicate type;
- artifact version;
- required `CONFORMANT` status;
- transparency verification;
- equality between the signing execution SHA and the R9 checkout SHA evidence.

The external cryptographic system is normalized into `SignerVerificationContext`. HOWEDO core does not implement or simulate the cryptographic verification.

## Reference verifier

R11 provides a Sigstore/Cosign reference adapter that invokes `cosign verify-blob` without a shell and pins exact GitHub OIDC claims.

Cosign remains external tooling and is not a Python runtime dependency.

## Policy wildcard semantics

V1 uses only a segment wildcard `*`, matching one non-empty slash-delimited segment. Arbitrary policy-provided regular expressions are not supported.

## Verification result format

HOWEDO will not create a proprietary trust-receipt wire format.

R11 emits the current in-toto Simple Verification Result predicate:

```text
https://in-toto.io/attestation/svr/v0.2
```

inside an in-toto Statement/v1.

The result binds the evaluated R9 artifact, identifies the HOWEDO verifier, references the exact policy URI and digest, and emits deterministic acceptance/rejection properties and reason codes.

The reference CI path also signs each generated SVR result through the existing Sigstore keyless workflow.

## Production trust policy

The production reference policy trusts only the canonical workflow on `refs/heads/main` for `push` or `workflow_dispatch` events.

A separate PR-only policy exists exclusively to test R11 during pull-request CI.

This separation prevents a pull request from being treated as production-trusted merely because it can run or modify the workflow under test.

## Main verification path

The Conformance Matrix will run on pushes to `main` in addition to pull requests and manual dispatch. After merge, the canonical main commit therefore generates a fresh production-policy result automatically.

## Trust root

Repository presence is not sufficient to establish trust in a policy. Consumers must independently pin or obtain the expected policy identity/digest.

The policy file is content-addressed to make that external pinning precise.

## Consequences

### Positive

- no custom PKI or signature format;
- no Sigstore Python dependency in core;
- deterministic consumer-side trust semantics;
- machine-readable rejection reasons;
- standard in-toto SVR output;
- production/main trust separated from PR test evidence;
- future cryptographic verifier adapters can reuse the same core policy engine.

### Costs

- Sigstore remains an external dependency for the reference end-to-end verifier;
- a production consumer must manage a trusted policy digest through an independent channel;
- R11 does not grant execution authority and does not replace V-One or another authorization layer.

## Rejected alternatives

### Treat a valid R10 Sigstore signature as sufficient

Rejected. Cryptographic authenticity is not equivalent to consumer policy acceptance.

### Use Sigstore policy-controller directly as HOWEDO policy semantics

Rejected. The controller is Kubernetes admission infrastructure and supports Kubernetes-oriented CUE/Rego policies. HOWEDO requires a small runtime-neutral trust contract.

### Create a proprietary verification receipt

Rejected. In-toto already defines Simple Verification Result for policy verification outcomes.

### Trust PR workflow identities in production policy

Rejected. Pull requests can alter the code or workflow being evaluated. PR acceptance remains test-only evidence.

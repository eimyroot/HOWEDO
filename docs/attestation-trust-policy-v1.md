# HOWEDO Attestation Trust Policy v1

## Purpose

R9 proves that an adapter conformance record is internally consistent. R10 authenticates the issuer of the in-toto conformance statement through an external signature system. R11 answers the consumer-side question:

> Is this cryptographically verified conformance attestation acceptable under my explicit trust policy?

R11 is a policy evaluation layer. It is not a PKI, certificate authority, transparency log, OIDC provider, workflow engine, or execution authorization system.

## Contract

The frozen policy version is:

```text
howedo.attestation-trust-policy.v1
```

A policy is content-addressed. `policy_digest` is SHA-256 over the canonical policy object excluding the digest field itself. Consumers SHOULD pin the expected policy digest outside the repository or artifact being evaluated when the policy is being used as a trust root.

The shipped reference policies are examples, not an implicit universal root of trust.

## Evaluation inputs

R11 consumes four inputs:

1. an R9 `howedo.adapter-conformance-artifact.v1` record;
2. the R10 in-toto Statement/v1 bound to that exact artifact;
3. a content-addressed R11 trust policy;
4. a normalized signer verification context produced after external cryptographic verification.

The normalized signer context contains:

```text
verifier_id
cryptographically_verified
issuer
identity
repository
workflow
execution_sha
execution_ref
trigger
transparency_log_verified
evidence_refs
```

The context is an explicit trust boundary. HOWEDO core does not pretend that a Boolean field proves cryptography. The reference Sigstore adapter only marks the context as cryptographically verified after `cosign verify-blob` succeeds with the expected identity, issuer, repository, workflow SHA, workflow ref, and trigger.

## Reference Sigstore verifier

`howedo.sigstore_trust` invokes Cosign as an external process. It does not import Sigstore cryptography into HOWEDO core.

The reference command pins:

```text
--certificate-identity
--certificate-oidc-issuer
--certificate-github-workflow-repository
--certificate-github-workflow-sha
--certificate-github-workflow-ref
--certificate-github-workflow-trigger
```

The adapter never adds `--insecure-ignore-tlog` or `--insecure-ignore-sct`.

This keeps the cryptographic verification replaceable. A future verifier can normalize another PKI or signing system into the same `SignerVerificationContext` without changing HOWEDO trust semantics.

## Policy fields

A v1 policy declares allow-lists for:

- verifier implementation identity;
- certificate/OIDC issuer;
- signer identity patterns;
- repository identity;
- workflow path;
- execution ref patterns;
- workflow trigger;
- accepted in-toto predicate types;
- accepted HOWEDO artifact versions.

It also declares whether to require:

- `CONFORMANT` R9 status;
- verified transparency-log inclusion;
- exact equality between the signing workflow execution SHA and the R9 `git-checkout://sha/...` evidence reference.

## Pattern semantics

R11 does not accept arbitrary regular expressions from policy files.

The only v1 wildcard is `*`. It matches exactly one non-empty slash-delimited segment.

Example:

```text
refs/pull/*/merge
```

matches:

```text
refs/pull/14/merge
```

but does not match:

```text
refs/pull/14/extra/merge
```

This behavior is frozen for v1.

## Deterministic decision

The policy engine returns exactly one of:

```text
ACCEPT
REJECT
```

`REJECT` includes stable reason codes, including:

```text
ARTIFACT_INVALID
STATEMENT_INVALID
CRYPTOGRAPHIC_VERIFICATION_FAILED
VERIFIER_NOT_ALLOWED
ISSUER_NOT_ALLOWED
IDENTITY_NOT_ALLOWED
REPOSITORY_NOT_ALLOWED
WORKFLOW_NOT_ALLOWED
REF_NOT_ALLOWED
TRIGGER_NOT_ALLOWED
PREDICATE_TYPE_NOT_ALLOWED
ARTIFACT_VERSION_NOT_ALLOWED
CONFORMANCE_STATUS_NOT_ALLOWED
TRANSPARENCY_REQUIRED
ARTIFACT_CHECKOUT_SHA_MISSING
EXECUTION_SHA_MISMATCH
```

Unknown or failed verification is never promoted to acceptance.

## Verification result format

R11 deliberately does not invent a proprietary receipt wire format.

The result is emitted as an in-toto Simple Verification Result v0.2 Statement:

```text
_type         = https://in-toto.io/Statement/v1
predicateType = https://in-toto.io/attestation/svr/v0.2
```

The SVR subject is the exact R9 conformance artifact digest. The verifier section identifies the HOWEDO trust evaluator and includes the exact policy URI and policy SHA-256 digest.

Properties include:

```text
HOWEDO_ATTESTATION_TRUST_ACCEPTED
```

or:

```text
HOWEDO_ATTESTATION_TRUST_REJECTED
```

plus the policy digest, normalized signer-context digest, and stable rejection reasons when present.

`timeCreated` is explicit evidence metadata and is not part of the deterministic decision inputs.

## Signed SVR receipts

The reference GitHub Actions path signs generated SVR receipts keylessly with Sigstore/Cosign and immediately verifies the receipt signatures against the same exact workflow identity and GitHub OIDC claims.

This produces two distinct authenticated layers:

```text
R10: signed claim that adapter conformance succeeded
R11: signed verification result that the R10 claim satisfies a named trust policy
```

Neither layer grants permission to execute an external effect.

## Production versus PR policy

HOWEDO ships two intentionally separate policies.

### Production reference policy

```text
policies/reference/github-actions-conformance-trust-v1.json
```

It accepts only the canonical workflow running on:

```text
refs/heads/main
```

with trigger:

```text
push
workflow_dispatch
```

### PR test policy

```text
policies/test/github-actions-pr-conformance-trust-v1.json
```

It exists only to exercise the R11 implementation during pull-request CI and accepts:

```text
refs/pull/*/merge
pull_request
```

A PR-generated acceptance is therefore test evidence, not the production trust-root result.

The Conformance Matrix also runs on pushes to `main`, so after merge the production policy is evaluated against canonical main automatically.

## CLI

Reference end-to-end verification:

```text
howedo-verify-sigstore-trust \
  --artifact <r9.json> \
  --statement <r10.intoto.json> \
  --bundle <r10.sigstore.json> \
  --policy <policy.json> \
  --issuer <issuer> \
  --identity <identity> \
  --repository <repository> \
  --workflow <workflow-path> \
  --execution-sha <sha> \
  --execution-ref <ref> \
  --trigger <event> \
  --time-created <RFC3339> \
  --output <result.svr.json>
```

Exit code `0` means the cryptographic verification succeeded and the deterministic policy decision was `ACCEPT`. Any verification or policy failure returns non-zero.

## Trust-root rule

A policy stored next to the code it evaluates is convenient distribution, not by itself a root of trust.

A consumer that relies on a policy for security MUST obtain or pin the expected policy identity/digest through an independent trusted channel appropriate to that consumer.

## Boundary

R11 owns:

```text
normalized verified-signer context
content-addressed trust policy
deterministic ACCEPT / REJECT semantics
stable rejection reasons
SVR verification result generation
```

R11 does not own:

```text
PKI
OIDC
certificate issuance
signature algorithms
transparency-log infrastructure
repository permissions
workflow execution authority
runtime continuation semantics
```

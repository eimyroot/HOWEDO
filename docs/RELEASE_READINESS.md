# HOWEDO Release Readiness

Status: **pre-1.0 / release-candidate engineering**

This document separates implemented repository controls from production trust ceremonies and external assurance. A checked implementation item is not equivalent to an independently audited production guarantee.

## Implemented repository baseline

- Deterministic continuity kernel with `CONTINUE`, `PAUSE`, `REVALIDATE`, `ABORT`, and `RECOVER` decisions.
- Continuity Witness evidence contract.
- Runtime adapter contract and reference LangGraph/Temporal adapters.
- Conformance artifacts, in-toto attestation binding, trust-policy verification, consumer replay, TUF distribution contracts, trust-root publication contracts, and release-bundle verification.
- R16.1 FastAPI service boundary with health/readiness endpoints and continuity-check API.
- R16.2 hardened OCI runtime definition and GHCR build/publish pipeline using commit-bound tags, immutable image digests, provenance attestation, SBOM generation, non-root runtime, dropped capabilities, read-only verification, and health/API smoke checks.
- Apache-2.0 repository license and explicit security policy.

## Mandatory gates before first public PyPI production release

The following are operational decisions or external actions and MUST NOT be represented as completed until evidence exists:

1. Confirm the public package name `howedo-continuity` is final and uncontested.
2. Enable PyPI Trusted Publishing only for the intended production environment and canonical workflow.
3. Produce a release candidate from a protected canonical commit and preserve the exact release-bundle evidence.
4. Verify wheel/sdist clean installation and the complete release verification matrix in GitHub Actions.
5. Verify that package metadata resolves to `https://github.com/eimyroot/HOWEDO` and includes the Apache-2.0 license.
6. Keep any publish-enablement switch fail-closed until the release owner explicitly authorizes publication.

## Mandatory gates before production TUF trust-root activation

The repository contains contracts and runbooks; this does not mean a production trust root currently exists.

Before production activation:

1. Perform the documented offline root ceremony outside CI.
2. Establish production TUF metadata and target endpoints over HTTPS.
3. Record and independently preserve the bootstrap root bytes and SHA-256 digest.
4. Verify threshold/key-separation policy and sequential root-history validation.
5. Test expiry, rollback, freeze, key compromise, and rotation recovery scenarios.
6. Publish only public trust material; production private root keys must remain outside HOWEDO, GitHub, and CI.

## Mandatory external-assurance gates

Before describing HOWEDO as independently verified production trust/security infrastructure:

1. Complete a line-level review of the Decision Engine, SEMLOCK, RECALL/CONCUR interactions, recovery fencing, attestation verification, TUF rotation, and release workflows.
2. Obtain at least one independent security review from a person who did not author the implementation under review.
3. Track findings to closure with reproducible regression tests.
4. Publish a reference deployment/case study demonstrating a real stale-state or dependency-drift incident that HOWEDO detects and handles safely.

## Deployment authority

For OCI deployment, mutable tags such as `main` are convenience aliases only. The deployment authority is:

```text
ghcr.io/eimyroot/howedo@sha256:<digest>
```

The digest must be produced by the canonical build and recorded as release/deployment evidence.

## Current interpretation

HOWEDO can be treated as a serious pre-1.0 continuity/security engineering project with a substantial implemented verification surface. Production trust claims remain conditional on the operational trust-root ceremony, release activation, and independent review gates above.

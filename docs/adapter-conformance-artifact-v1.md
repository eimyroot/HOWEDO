# HOWEDO Adapter Conformance Artifact v1

Artifact identifier: `howedo.adapter-conformance-artifact.v1`

## Purpose

A HOWEDO runtime adapter can already execute the vendor-neutral `howedo.runtime-adapter.v1` conformance suite. R9 makes the result portable and machine-verifiable by binding the adapter manifest, the complete frozen check set, execution-environment metadata, evidence references, and the overall result into one canonical JSON record.

The artifact answers:

> What exact adapter contract was tested, what checks ran, in what environment, and has this record changed since it was produced?

## What the artifact proves

A valid artifact proves internal record integrity and consistency:

- the artifact uses the exact v1 format;
- the complete frozen v1 conformance check sequence is present;
- status is derived from those checks rather than supplied independently;
- the adapter manifest digest matches the embedded manifest;
- the artifact digest matches the canonical record;
- evidence references are part of the content-addressed record.

The verifier is part of HOWEDO core and does not import LangGraph, Temporal, PostgreSQL, or another runtime vendor SDK.

## What it deliberately does not prove

A SHA-256 digest does not authenticate the issuer. Anyone able to create a record can compute a digest for it.

Therefore R9 MUST NOT be described as third-party trust certification, vendor endorsement, signed provenance, or proof that a named organization issued the artifact. Issuer authentication, signatures, trust roots, revocation, and transparency logs require a separate protocol layer.

The correct R9 statement is:

> This record is a self-consistent, content-addressed result of the HOWEDO runtime-adapter-v1 conformance model.

## Frozen check set

`howedo.adapter-conformance-artifact.v1` contains exactly these checks, in this order:

1. `runtime-adapter-v1-structural`
2. `contract-version`
3. `required-capabilities`
4. `manifest-content-addressed`
5. `identity-runtime-family`
6. `identity-content-addressed`
7. `binding-manifest-digest`
8. `binding-exact-identity`
9. `unchanged-reality-recovers`
10. `changed-reality-does-not-recover`
11. `continue-after-recover`

Changing this semantic check set requires a new artifact format identifier.

## Status

Status is derived, never independently trusted:

- every check passes -> `CONFORMANT`
- one or more checks fail -> `NON_CONFORMANT`

A non-conformant artifact is still valid evidence if its digest and internal structure verify. Validity of the artifact and success of the adapter are separate concepts.

## Canonical record

The record contains:

- `artifact_version`
- `status`
- embedded adapter `manifest`
- `manifest_digest`
- ordered `checks`
- `environment`
- sorted unique `evidence_refs`
- `artifact_digest`

`artifact_digest` is SHA-256 over canonical JSON of every field except the digest field itself, using sorted object keys and compact separators.

No implicit current timestamp is inserted into the core artifact. This keeps the artifact reproducible for identical supplied evidence and environment. External evidence systems MAY envelope the artifact with timestamps, signatures, build IDs, or transparency-log metadata.

## Active conformance warning

The runtime-adapter-v1 suite includes `continue-after-recover`. Certification is therefore an active test and may perform a real continuation side effect in the supplied runtime fixture.

Third-party adapters MUST run certification against an isolated/disposable test execution, never an arbitrary production execution.

## Generation

```python
artifact = await AdapterConformanceArtifactBuilder().build(
    adapter,
    fixture,
    evidence_refs=("ci://run/123",),
)
record = artifact.record()
```

The runtime-specific fixture remains responsible for creating an exact test execution and verifying that continuation really occurred.

## Verification

Library:

```python
verification = verify_conformance_record(record)
assert verification.valid
```

CLI:

```bash
howedo-verify-conformance artifact.json
```

Exit code is `0` when record integrity and internal consistency verify and `1` otherwise.

## Schema

The frozen wire schema is:

`schemas/adapter-conformance-v1/conformance-artifact.schema.json`

The artifact format is deliberately separate from `schemas/runtime-adapter-v1/`. R9 does not mutate the already-frozen runtime adapter contract schema set.

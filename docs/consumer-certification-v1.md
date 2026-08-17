# Consumer Certification Replay v1

R12 turns the R9-R11 evidence chain into a portable, independently replayable consumer artifact.

## Core question

> Does this exact certification chain satisfy the trust expectations I pinned?

## Contracts

### `howedo.consumer-trust-profile.v1`

The consumer trust profile pins:

- trusted R11 SVR verifier IDs;
- exact trusted R11 policy ID + content digest;
- allowed external crypto verifier IDs;
- issuer, signer identity, repository, workflow path, workflow display name, ref, and trigger expectations;
- transparency-log requirement.

The workflow display name is passed to Cosign as a certificate claim expectation. It is not accepted from package metadata as a substitute for cryptographic verification.

The profile is content-addressed. It is a relying-party expectation file, not a PKI and not a replacement for TUF or another root-distribution system.

### `howedo.certification-package.v1`

A package directory contains exactly:

```text
manifest.json
artifact.json
policy.json
statement.intoto.json
statement.sigstore.json
svr.json
svr.sigstore.json
```

`manifest.json` pins the SHA-256 of every file, the R9 artifact digest, the R11 policy digest, and the exact signer context required to reproduce the R11 signer-context digest.

The manifest is a transport/index object. Security still comes from the R9/R10/R11 semantic bindings, the consumer profile, and the externally verified Sigstore signatures.

R12 v1 requires the R10 statement and R11 SVR to be signed by the same exact workflow execution identity recorded in the manifest. A future contract can generalize this only if a real multi-signer requirement appears.

## Build

```bash
howedo-build-certification-package \
  --artifact artifact.json \
  --statement statement.intoto.json \
  --statement-bundle statement.sigstore.json \
  --policy policy.json \
  --svr svr.json \
  --svr-bundle svr.sigstore.json \
  --issuer https://token.actions.githubusercontent.com \
  --identity <exact-workflow-identity> \
  --repository nulleimy/HOWEDO \
  --workflow .github/workflows/consolidation.yml \
  --execution-sha <sha> \
  --execution-ref <ref> \
  --trigger <event> \
  --evidence-ref <original-r11-evidence-ref> \
  --output-dir package/
```

## Verify

```bash
howedo-verify-certification-package package/ \
  --profile /trusted/path/consumer-trust-profile.json \
  --expected-profile-digest sha256:<externally-pinned-digest>
```

The CLI requires the expected profile digest to be pinned outside the supplied profile file. The verifier fails closed unless all of the following succeed:

```text
package digests
AND R9 integrity
AND R10 semantic binding
AND R10 external signature verification
AND cryptographically verified workflow display name
AND consumer signer expectations
AND independent R11 policy replay
AND deterministic R11 SVR replay
AND R11 SVR external signature verification
AND trusted verifier + trusted policy pin
```

No LangGraph, Temporal, PostgreSQL, Sigstore Python library, or other runtime vendor SDK becomes a required HOWEDO core dependency. Cosign remains external reference tooling.

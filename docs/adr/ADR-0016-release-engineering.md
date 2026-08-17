# ADR-0016 — Verifiable Python Release and Secretless Publication

## Status

Accepted for R15 software implementation.

## Context

HOWEDO already has content-addressed conformance, signed attestations, consumer verification,
TUF client trust-root distribution, and protected canonical development. R15 needs a release
path that preserves those trust properties when Python artifacts leave the repository.

Long-lived package-registry tokens would create a new secret-management liability. Publishing
directly from arbitrary branches or rebuilding artifacts in a separate publish job would also
weaken provenance.

## Decision

1. Build wheel and sdist exactly once from the GitHub Release tag.
2. Require the release tag to be `v<project.version>`.
3. Require the tagged commit to equal the current protected `main` head.
4. Clean-install the wheel and generate a reproducible CycloneDX SBOM from that environment.
5. Emit `howedo.release-bundle.v1` binding wheel, sdist, SBOM, commit, tree, version, and tag.
6. Generate GitHub artifact provenance and SBOM attestations in the build job.
7. Pass the already-built distributions to the publish job through GitHub artifact storage;
   never rebuild during publication.
8. Publish to PyPI only with GitHub OIDC Trusted Publishing and the `pypi` environment.
9. Keep public-registry activation separate from R15 software completion.
10. Defer OCI image publication until R16 has a real deployable service.

## Consequences

- R15 can be canonical before any public package is uploaded.
- First PyPI publication still requires intentional external configuration and a final name
  collision/license check.
- No PyPI API token is required or stored.
- Consumers get wheel/sdist, checksums, a CycloneDX SBOM, a HOWEDO release manifest, and GitHub
  provenance/SBOM attestations from one build.

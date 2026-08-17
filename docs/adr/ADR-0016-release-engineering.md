# ADR-0016 — Verifiable Python Release and Secretless Publication

## Status

Accepted for R15 software implementation.

## Context

HOWEDO already has content-addressed conformance, signed attestations, consumer verification,
TUF client trust-root distribution, and protected canonical development. R15 needs a release
path that preserves those trust properties when Python artifacts leave the repository.

Long-lived package-registry tokens would create a new secret-management liability. Publishing
directly from arbitrary branches, rebuilding artifacts during publication, or attaching assets
after a release has already become immutable would weaken the release trust boundary.

## Decision

1. A `v*` tag push starts the release-candidate workflow.
2. Require the release tag to be `v<project.version>`.
3. Require the tagged commit to equal the current protected `main` head at candidate build time.
4. Build wheel and sdist exactly once from that tag.
5. Clean-install the wheel and generate a reproducible CycloneDX SBOM from that environment.
6. Emit `howedo.release-bundle.v1` binding wheel, sdist, SBOM, commit, tree, version, and tag.
7. Generate GitHub artifact provenance and SBOM attestations in the build job.
8. Transfer the already-built bytes through GitHub artifact storage and recheck SHA-256 digests.
9. Create a GitHub Release as a draft and attach wheel, sdist, SBOM, release manifest, and
   checksums before any publication.
10. A human reviews the draft and publishes it only after GitHub release immutability is enabled.
11. The separate PyPI workflow runs only on `release: published`, only when
    `HOWEDO_PYPI_PUBLISH_ENABLED=true`, and only through the protected `pypi` environment.
12. Before PyPI upload, require `gh release verify` and `gh release verify-asset` to succeed for
    the immutable release and the exact wheel/sdist bytes.
13. Publish to PyPI only with GitHub OIDC Trusted Publishing; never use a long-lived PyPI token.
14. Keep public-registry activation separate from R15 software completion.
15. Defer OCI image publication until R16 has a real deployable service.

## Consequences

- R15 can be canonical before any public package is uploaded.
- GitHub Release assets are staged before the immutable publication boundary instead of mutated
  afterward.
- First public release still requires intentional external configuration: release immutability,
  PyPI Trusted Publisher, `pypi` environment approval, activation variable, final package-name
  collision check, and an explicit license/distribution decision.
- No PyPI API token is required or stored.
- Consumers get wheel/sdist, checksums, a CycloneDX SBOM, a HOWEDO release manifest, and GitHub
  provenance/SBOM attestations from one build.

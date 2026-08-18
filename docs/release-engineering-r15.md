# R15 — Distribution and Release Engineering

## Purpose

R15 turns the canonical HOWEDO Python codebase into a verifiable release artifact without
changing continuity-kernel semantics.

## Release contract

A release candidate is eligible only when all of the following are true:

1. the pushed tag is exactly `v<project.version>`;
2. the tagged commit equals the exact current protected `main` commit at candidate build time;
3. wheel and sdist build successfully;
4. `twine check` accepts both distributions;
5. the wheel installs into a clean virtual environment without dependencies;
6. the installed distribution reports the expected package version;
7. a reproducible CycloneDX 1.6 JSON SBOM is generated from the clean installed environment;
8. `howedo.release-bundle.v1` content-addresses the wheel, sdist, and SBOM;
9. the release bundle re-verifies the exact file bytes;
10. GitHub artifact attestations bind provenance to the Python distributions and bind the
    CycloneDX SBOM to the wheel;
11. the verified assets are attached to a **draft** GitHub Release before publication.

The draft step deliberately precedes the immutable-release boundary. Release assets are not
uploaded or replaced after publication.

## PyPI publishing boundary

PyPI publication uses Trusted Publishing through GitHub Actions OIDC. No long-lived PyPI API
token belongs in GitHub secrets, CASER, source control, or a developer workstation.

The trusted publisher should be constrained to:

- owner: `nulleimy`
- repository: `HOWEDO`
- workflow: `pypi-publish.yml`
- environment: `pypi`

The `pypi` GitHub environment should require explicit release approval.

The publish job is additionally fail-closed behind the repository variable
`HOWEDO_PYPI_PUBLISH_ENABLED=true`. If the variable is absent or any other value, publishing the
GitHub Release does not upload anything to PyPI.

Before PyPI receives bytes, the publisher requires GitHub's immutable-release attestation to
verify successfully with `gh release verify`, downloads only the wheel and sdist from the
published GitHub Release, and verifies each local file with `gh release verify-asset`.

Public release activation is separate from R15 software completion. It remains pending until:

- GitHub release immutability is enabled for future HOWEDO releases;
- the PyPI project/pending publisher is configured for `pypi-publish.yml` + `pypi`;
- the package-name collision is rechecked immediately before first publication;
- the repository license/distribution terms are explicitly decided;
- `HOWEDO_PYPI_PUBLISH_ENABLED=true` is intentionally configured;
- a valid version tag is intentionally pushed from canonical `main`;
- the generated draft release is reviewed and intentionally published.

A pending PyPI Trusted Publisher does not reserve the project name.

## OCI/GHCR boundary

R15 does not manufacture a meaningless container image for a library-only codebase. OCI/GHCR
image publication is activated in R16 together with the deployable HOWEDO service/API. The R15
supply-chain pattern (digest binding, SBOM, provenance, secretless GitHub credentials) is the
required release pattern for that future image.

## Upgrade compatibility

- protocol and evidence schema versions remain independently versioned from the Python package;
- package-version changes do not silently change frozen wire contracts;
- breaking wire-format changes require a new schema/contract version and migration documentation;
- database migration compatibility remains part of the release acceptance gate before a stable
  production release.

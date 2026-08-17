# R15 — Distribution and Release Engineering

## Purpose

R15 turns the canonical HOWEDO Python codebase into a verifiable release artifact without
changing continuity-kernel semantics.

## Release contract

A release is eligible only when all of the following are true:

1. the GitHub Release tag is exactly `v<project.version>`;
2. the tag resolves to the exact current protected `main` commit;
3. wheel and sdist build successfully;
4. `twine check` accepts both distributions;
5. the wheel installs into a clean virtual environment without dependencies;
6. the installed distribution reports the expected package version;
7. a reproducible CycloneDX JSON SBOM is generated from the clean installed environment;
8. `howedo.release-bundle.v1` content-addresses the wheel, sdist, and SBOM;
9. the release bundle re-verifies the exact file bytes before publication;
10. GitHub artifact attestations bind provenance to the Python distributions and bind the
    CycloneDX SBOM to the wheel.

## PyPI publishing boundary

PyPI publication uses Trusted Publishing through GitHub Actions OIDC. No long-lived PyPI API
token belongs in GitHub secrets, CASER, source control, or a developer workstation.

The trusted publisher should be constrained to:

- owner: `nulleimy`
- repository: `HOWEDO`
- workflow: `release.yml`
- environment: `pypi`

The `pypi` GitHub environment should require explicit release approval.

The publish job is additionally fail-closed behind the repository variable
`HOWEDO_PYPI_PUBLISH_ENABLED=true`. If the variable is absent or any other value, a GitHub Release
may build, verify, attest, and archive evidence, but the PyPI job is skipped.

Public PyPI activation is separate from R15 software completion. It remains pending until:

- the PyPI project/pending publisher is configured;
- the package-name collision is rechecked immediately before first publication;
- the repository license/distribution terms are explicitly decided;
- `HOWEDO_PYPI_PUBLISH_ENABLED=true` is intentionally configured;
- the first release is intentionally published.

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

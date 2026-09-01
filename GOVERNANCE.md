# Governance

HOWEDO uses an evidence-first, protected-main development model.

## Canonical branch

`main` is the canonical integration branch. Changes are expected to arrive through pull requests and satisfy the repository ruleset and required status checks before merge.

## Decision authority

The maintainer owns product direction, release decisions, repository policy, and acceptance of changes. Architecture changes that alter continuity semantics, trust boundaries, protocol identity, evidence formats, or adapter contracts should be documented with an ADR under `docs/adr/`.

## Change principles

- Fail closed when continuity or trust cannot be established.
- Preserve historical signed evidence rather than rewriting cryptographic identity.
- Keep presentation and adapters outside the continuity kernel's semantic authority.
- Prefer deterministic, reproducible verification over narrative claims.
- Do not weaken required checks to make a change mergeable; fix the implementation or the declared contract.

## Releases

A Git tag, GitHub Release, package publication, container publication, trust-root ceremony, and production deployment are distinct events. A successful engineering release candidate does not automatically assert completion of external assurance gates.

See `docs/RELEASE_READINESS.md` for the authoritative boundary.

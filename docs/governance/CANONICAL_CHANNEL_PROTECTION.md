# Canonical Channel Protection

Status: GOVERNANCE CONTRACT

This document defines how the canonical `main` branch is allowed to change. It is repository governance, not a HOWEDO runtime feature.

## Required invariant

> A new canonical `main` head must be attributable to a reviewed pull request and must pass the production verification gates before it is treated as trusted canonical state.

## Required GitHub enforcement

Preferred configuration is a repository ruleset targeting `main`:

1. require a pull request before merge;
2. require the repository workflows `CI`, `Conformance Matrix`, `R12 Consumer Certification`, and `Canonical Channel` to pass before merge;
3. require branches to be up to date before merge when compatible with the selected merge policy;
4. block force pushes;
5. block branch deletion;
6. block direct pushes to `main` except a separately documented break-glass identity/path;
7. require conversation resolution before merge where available;
8. preserve verified/signed commit requirements where supported by the repository/account tier.

If only classic branch protection is available, require the equivalent status checks exposed by these workflows and apply the same force-push/deletion/direct-push restrictions.

## Canonical Channel workflow

`.github/workflows/canonical-channel.yml` provides an executable provenance check.

On pull requests targeting `main`, it establishes a stable status check that can be required by GitHub protection.

On pushes to `main`, it fails closed when:

- the push event is marked as forced; or
- the resulting `GITHUB_SHA` cannot be associated through the GitHub API with at least one merged pull request whose base branch is `main`.

This workflow is **detection only while `main` is unprotected**. A failing post-push workflow cannot retroactively prevent a direct push. It becomes an enforcement gate only after GitHub ruleset/branch protection requires the check and blocks bypass/direct push paths.

## Production trust gates

The canonical trust chain currently requires:

- `CI`;
- `Conformance Matrix`;
- `R12 Consumer Certification`;
- `Canonical Channel`.

The R12 consumer replay is independent of the producer-generated R11 `ACCEPT`; the relying-party profile digest remains an independently pinned root expectation.

## Break-glass

No break-glass bypass is authorized by this document.

If one is later required, it must be separately documented with:

- the exact actor/role allowed to bypass;
- the emergency condition;
- a time-bounded authorization;
- mandatory post-event evidence and reconciliation;
- explicit CASER journal/receipt entry.

A generic administrator bypass is not considered a governed break-glass path.

## Source-of-Truth interaction

GitHub `main` is the canonical code branch only after the required gates pass. CASER current state is selected through its content-addressed immutable snapshot pointer and must record the exact canonical Git commit/tree and verification runs.

A failed `Canonical Channel` run is a Source-of-Truth incident and must prevent CASER-SOURCER from promoting the affected head as trusted canonical state until reconciled.

## Current gap

Issue #15 tracks activation of the GitHub-side ruleset/branch protection. Until GitHub reports `main` as effectively protected, this repository retains an explicit governance risk even when all product tests are green.

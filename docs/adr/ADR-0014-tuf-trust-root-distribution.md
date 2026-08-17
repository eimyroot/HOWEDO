# ADR-0014: TUF trust-root distribution for consumer profiles

Status: Accepted for R13

## Context

R12 independently replays certification evidence against a content-addressed
`howedo.consumer-trust-profile.v1`. The remaining bootstrap problem is how a
consumer learns a current trusted profile without replacing a pinned digest by
hand forever.

A profile downloaded from the same repository that publishes the evidence is
not a trust root. HOWEDO must preserve an independently bootstrapped trust
anchor while allowing profile rotation, freshness checks, and rollback/freeze
resistance.

## Decision

R13 uses The Update Framework (TUF) as the trust-distribution substrate.

- The initial trusted TUF root is supplied out of band as immutable bootstrap bytes.
- The HOWEDO consumer trust profile is a TUF target.
- Root rotation, metadata freshness, target integrity, and rollback/freeze
  protections are delegated to the TUF client workflow.
- HOWEDO validates the downloaded target as an exact
  `howedo.consumer-trust-profile.v1` and emits a content-addressed update receipt.
- TUF is an optional dependency. Importing HOWEDO core or the trust-distribution
  module must not require TUF to be installed.
- HOWEDO does not invent a TUF-like metadata format, repository server, PKI, or
  key ceremony.

## Security boundary

A TUF repository URL is not itself trusted. The trust anchor is the out-of-band
bootstrap root. The R13 receipt records the bootstrap-root digest, final trusted
root version, verified target hashes, and resulting HOWEDO profile digest.

The receipt is evidence of the update result; it does not replace TUF metadata
or become a new signing authority.

## Conformance

R13 must demonstrate with public python-tuf APIs that:

1. a bootstrap root v1 can securely advance to a dual-threshold root v2;
2. the production R12 consumer profile is fetched as a verified TUF target;
3. target tampering fails;
4. a root v2 that lacks the old-root threshold is rejected;
5. core-only HOWEDO remains dependency-free.

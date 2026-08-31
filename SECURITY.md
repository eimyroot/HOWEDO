# Security Policy

HOWEDO is security-sensitive continuity and integrity infrastructure. Treat suspected bypasses of fail-closed behavior, trust-policy verification, attestation verification, TUF root rotation, release provenance, or recovery fencing as security issues.

## Supported versions

HOWEDO is currently pre-1.0. Until a stable release exists, security fixes are applied to the canonical `main` branch and the latest tagged release candidate, if one exists.

## Reporting a vulnerability

Do not publish exploitable details in a public issue. Use GitHub private vulnerability reporting for this repository when available. If private reporting is unavailable, open a public issue containing only a request for a private security contact and no exploit details.

A useful report contains:

- affected commit/tag and component;
- attacker prerequisites and trust boundary;
- reproducible steps or minimal proof of concept;
- expected fail-closed behavior versus observed behavior;
- impact on continuity decisions, evidence, trust roots, release provenance, or recovery;
- suggested mitigation, if known.

## Security invariants

Changes are security-relevant when they can affect any of these invariants:

1. Unknown or unverifiable state must not silently become trusted state.
2. Continuity decisions must remain deterministic for equivalent validated inputs.
3. Recovery must not resume execution against an unvalidated or stale binding.
4. Trust-root rotation must not degrade into trust-on-first-use.
5. Attestation and certification verification must bind to exact content and expected workflow identity.
6. Deployment authority is an immutable artifact digest, not a mutable tag.
7. Release and container pipelines must minimize permissions and produce replayable evidence.

## Disclosure

Please allow time to validate, patch, test, and release a fix before public disclosure. HOWEDO does not promise a fixed response SLA while the project remains pre-1.0.

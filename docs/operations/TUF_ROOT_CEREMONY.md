# HOWEDO production TUF root ceremony

This runbook is the operational step required to activate R14 in production. The repository contains only public contracts and verification code.

## Reference custody model

- root: 3 independent keys, threshold 2, offline;
- targets: dedicated key, offline;
- snapshot: dedicated key, offline under the conservative HOWEDO reference profile;
- timestamp: dedicated online key;
- no key reuse between top-level roles;
- no production private key in GitHub, GitHub Actions, CASER, application images, or writable TUF client caches.

TUF itself requires root private keys to be kept very secure/offline and recommends secure offline storage for roles other than timestamp/mirrors. Exact storage technology is deployment-specific.

## Initial ceremony

1. Prepare isolated signing devices or equivalent offline key custody.
2. Generate three independent root keys and dedicated targets/snapshot/timestamp keys.
3. Build root v1 with `consistent_snapshot=true`, the agreed expiry, and 2-of-3 root threshold.
4. Sign root v1 with at least two root keys.
5. Export **public** `1.root.json` only.
6. Verify it with `howedo-build-trust-root-publication` and the pinned reference policy.
7. Distribute `1.root.json` and the publication manifest through the selected out-of-band bootstrap channel.
8. Publish repository metadata/targets separately; never publish private-key material.

## Root rotation

For vN → vN+1, retain every prior root metadata file. The new root must be signed by a threshold trusted by vN and a threshold trusted by vN+1. Run the R14 verifier over the complete root history before publication.

## Compromise handling

If fewer than the root threshold are compromised, revoke/replace affected keys through a normal threshold-authorized root rotation. If the root threshold itself is compromised, treat the bootstrap trust anchor as compromised and require a new out-of-band trust bootstrap; do not represent ordinary online rotation as sufficient recovery.

## Evidence

A production ceremony receipt should record public key IDs, role thresholds, root metadata digests, operators/approvers, storage-class assertions, publication manifest digest, and independent verification results. Sensitive private material is never evidence content.

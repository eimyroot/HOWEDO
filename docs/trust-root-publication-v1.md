# Production trust-root publication v1

R14 defines how HOWEDO publishes the public trust material that bootstraps R13 TUF-based consumer trust-profile distribution.

## Boundary

R14 verifies public metadata and publication policy. It does **not** generate, escrow, upload, or attest physical custody of production private keys. Root/targets/snapshot private-key custody is an offline operational ceremony outside the repository; timestamp may be online according to the deployment design.

## Publication acceptance

A publication is accepted only when:

1. the supplied TUF root history starts at v1 and contains every version through N;
2. root v1 meets its own signature threshold;
3. every root N+1 verifies against both the previous root threshold and its new root threshold;
4. the current root meets the independently supplied HOWEDO publication policy;
5. the current root uses the required TUF spec major and consistent snapshots;
6. root key count/threshold meet the reference minimum;
7. top-level roles do not reuse key IDs under the reference production policy;
8. the current root has at least the configured validity window remaining at `verified_at`;
9. metadata and target endpoints are absolute HTTPS URLs under the reference policy; and
10. the content-addressed publication manifest exactly matches the verified root history and policy digest.

The reference production policy is `policies/reference/tuf-production-publication-v1.json`.

## CLI

```bash
howedo-build-trust-root-publication \
  --root 1.root.json \
  --root 2.root.json \
  --policy policies/reference/tuf-production-publication-v1.json \
  --publication-id howedo-production-trust-root-v2 \
  --metadata-base-url https://trust.example/metadata/ \
  --target-base-url https://trust.example/targets/ \
  --target-path howedo/github-actions-consumer-trust-v1.json \
  --consumer-profile-id howedo.github-actions-consumer-trust.v1 \
  --output publication.json

howedo-verify-trust-root-publication \
  --root 1.root.json \
  --root 2.root.json \
  --policy policies/reference/tuf-production-publication-v1.json \
  --manifest publication.json
```

The initial root bytes still require an out-of-band trusted bootstrap channel. A valid R14 manifest is publication evidence, not a substitute for that bootstrap trust decision.

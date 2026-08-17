from __future__ import annotations

import copy
from datetime import UTC, datetime

import pytest

from howedo.trust_publication import (
    TrustRootPublicationPolicy,
    build_trust_root_publication_manifest,
    verify_trust_root_publication,
)

signer_module = pytest.importorskip("securesystemslib.signer")
tuf_metadata = pytest.importorskip("tuf.api.metadata")
CryptoSigner = signer_module.CryptoSigner
Metadata = tuf_metadata.Metadata
Root = tuf_metadata.Root

VERIFIED_AT = datetime(2026, 8, 17, 8, 0, tzinfo=UTC)
EXPIRES = datetime(2028, 8, 17, 8, 0, tzinfo=UTC)


def _initial_root(*, threshold: int = 2, consistent_snapshot: bool = True):
    root_signers = [CryptoSigner.generate_ecdsa() for _ in range(3)]
    role_signers = {
        role: CryptoSigner.generate_ecdsa()
        for role in ("snapshot", "targets", "timestamp")
    }
    metadata = Metadata(Root(expires=EXPIRES))
    metadata.signed.version = 1
    metadata.signed.consistent_snapshot = consistent_snapshot
    for signer in root_signers:
        metadata.signed.add_key(signer.public_key, "root")
    metadata.signed.roles["root"].threshold = threshold
    for role, signer in role_signers.items():
        metadata.signed.add_key(signer.public_key, role)
    for signer in root_signers:
        metadata.sign(signer, append=True)
    return metadata, root_signers


def _rotated_root(previous: Metadata, old_root_signers):
    metadata = copy.deepcopy(previous)
    metadata.signed.version = 2
    metadata.signatures.clear()
    replacement = CryptoSigner.generate_ecdsa()
    metadata.signed.revoke_key(old_root_signers[2].public_key.keyid, "root")
    metadata.signed.add_key(replacement.public_key, "root")
    for signer in [old_root_signers[0], old_root_signers[1], replacement]:
        metadata.sign(signer, append=True)
    return metadata


def _policy() -> TrustRootPublicationPolicy:
    return TrustRootPublicationPolicy(policy_id="howedo.production-tuf-publication.v1")


def _build(history: tuple[bytes, ...]):
    return build_trust_root_publication_manifest(
        root_history=history,
        policy=_policy(),
        publication_id="howedo-production-trust-root-v1",
        metadata_base_url="https://trust.howedo.example/metadata/",
        target_base_url="https://trust.howedo.example/targets/",
        target_path="howedo/github-actions-consumer-trust-v1.json",
        consumer_profile_id="howedo.github-actions-consumer-trust.v1",
        verified_at=VERIFIED_AT,
    )


def test_publication_verifies_signed_root_history_and_rotation() -> None:
    root1, signers = _initial_root()
    root2 = _rotated_root(root1, signers)
    history = (root1.to_bytes(), root2.to_bytes())
    manifest = _build(history)
    assert manifest.root_version == 2
    assert tuple(item.version for item in manifest.root_history) == (1, 2)
    assert manifest.bootstrap_root_digest != manifest.current_root_digest
    verified = verify_trust_root_publication(
        root_history=history,
        manifest_record=manifest.record(),
        policy=_policy(),
    )
    assert verified == manifest


def test_root_rotation_missing_previous_threshold_is_rejected() -> None:
    root1, signers = _initial_root()
    root2 = copy.deepcopy(root1)
    root2.signed.version = 2
    root2.signatures.clear()
    replacement = CryptoSigner.generate_ecdsa()
    root2.signed.revoke_key(signers[2].public_key.keyid, "root")
    root2.signed.add_key(replacement.public_key, "root")
    root2.sign(signers[0], append=True)
    root2.sign(replacement, append=True)
    with pytest.raises(ValueError, match="signature threshold verification failed"):
        _build((root1.to_bytes(), root2.to_bytes()))


def test_root_history_must_retain_contiguous_versions() -> None:
    root1, signers = _initial_root()
    root2 = _rotated_root(root1, signers)
    root2.signed.version = 3
    with pytest.raises(ValueError, match="contiguous versions"):
        _build((root1.to_bytes(), root2.to_bytes()))


def test_policy_rejects_weak_root_threshold() -> None:
    root1, _ = _initial_root(threshold=1)
    with pytest.raises(ValueError, match="minimum threshold"):
        _build((root1.to_bytes(),))


def test_policy_rejects_role_key_reuse() -> None:
    root1, signers = _initial_root()
    root1.signed.add_key(signers[0].public_key, "timestamp")
    root1.signatures.clear()
    for signer in signers:
        root1.sign(signer, append=True)
    with pytest.raises(ValueError, match="key reuse"):
        _build((root1.to_bytes(),))


def test_policy_rejects_inconsistent_snapshot_mode() -> None:
    root1, _ = _initial_root(consistent_snapshot=False)
    with pytest.raises(ValueError, match="consistent snapshots"):
        _build((root1.to_bytes(),))


def test_policy_rejects_non_https_endpoints() -> None:
    root1, _ = _initial_root()
    with pytest.raises(ValueError, match="metadata_base_url"):
        build_trust_root_publication_manifest(
            root_history=(root1.to_bytes(),),
            policy=_policy(),
            publication_id="x",
            metadata_base_url="http://trust.example/metadata/",
            target_base_url="https://trust.example/targets/",
            target_path="howedo/github-actions-consumer-trust-v1.json",
            consumer_profile_id="howedo.github-actions-consumer-trust.v1",
            verified_at=VERIFIED_AT,
        )


def test_policy_rejects_short_root_validity_window() -> None:
    root1, signers = _initial_root()
    root1.signed.expires = datetime(2026, 9, 1, tzinfo=UTC)
    root1.signatures.clear()
    for signer in signers:
        root1.sign(signer, append=True)
    with pytest.raises(ValueError, match="minimum validity window"):
        _build((root1.to_bytes(),))


def test_manifest_tamper_is_rejected() -> None:
    root1, _ = _initial_root()
    history = (root1.to_bytes(),)
    manifest = _build(history)
    record = manifest.record()
    record["metadata_base_url"] = "https://attacker.example/metadata/"
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_trust_root_publication(
            root_history=history,
            manifest_record=record,
            policy=_policy(),
        )

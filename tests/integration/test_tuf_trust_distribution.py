from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytest.importorskip("tuf")
pytest.importorskip("securesystemslib")

from securesystemslib.signer import CryptoSigner
from tuf.api.exceptions import DownloadHTTPError, LengthOrHashMismatchError, UnsignedMetadataError
from tuf.api.metadata import Metadata, MetaFile, Root, Snapshot, TargetFile, Targets, Timestamp
from tuf.api.serialization.json import JSONSerializer
from tuf.ngclient.fetcher import FetcherInterface

from howedo.trust_distribution import (
    DEFAULT_CONSUMER_TRUST_TARGET,
    TrustProfileUpdateReceipt,
    fetch_consumer_trust_profile,
)

PROFILE_PATH = Path("policies/reference/github-actions-consumer-trust-v1.json")
EXPECTED_PROFILE_DIGEST = "sha256:312018c9e05bfdb9ffddf0f71ad80c3002ab185c90cc605e3295a2a0dd34d5a5"
EXPECTED_PROFILE_ID = (
    "https://github.com/nulleimy/HOWEDO/policies/reference/"
    "github-actions-consumer-trust-v1"
)


class MemoryFetcher(FetcherInterface):
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    def _fetch(self, url: str) -> Iterator[bytes]:
        path = urlparse(url).path
        data = self.objects.get(path)
        if data is None:
            raise DownloadHTTPError(f"missing test object: {path}", 404)
        yield data


def _signed(metadata: Metadata, signer: CryptoSigner) -> bytes:
    metadata.sign(signer)
    return metadata.to_bytes(JSONSerializer())


def _repository(
    profile_bytes: bytes, *, dual_signed_root: bool = True
) -> tuple[bytes, dict[str, bytes]]:
    expires = datetime.now(UTC) + timedelta(days=30)
    signers = {
        role: CryptoSigner.generate_ed25519()
        for role in (Root.type, Targets.type, Snapshot.type, Timestamp.type)
    }

    root_v1 = Metadata(Root(expires=expires, consistent_snapshot=False))
    for role, signer in signers.items():
        root_v1.signed.add_key(signer.public_key, role)
    root_v1_bytes = _signed(root_v1, signers[Root.type])

    root_v2 = Metadata.from_bytes(root_v1_bytes)
    root_v2.signed.version = 2
    new_root = CryptoSigner.generate_ed25519()
    old_root_id = signers[Root.type].public_key.keyid
    root_v2.signed.add_key(new_root.public_key, Root.type)
    root_v2.signed.revoke_key(old_root_id, Root.type)
    if dual_signed_root:
        root_v2.sign(signers[Root.type])
        root_v2.sign(new_root, append=True)
    else:
        root_v2.sign(new_root)
    root_v2_bytes = root_v2.to_bytes(JSONSerializer())

    targets = Metadata(Targets(expires=expires))
    targets.signed.targets[DEFAULT_CONSUMER_TRUST_TARGET] = TargetFile.from_data(
        DEFAULT_CONSUMER_TRUST_TARGET,
        profile_bytes,
        ["sha256"],
    )
    targets_bytes = _signed(targets, signers[Targets.type])

    snapshot = Metadata(Snapshot(expires=expires))
    snapshot.signed.meta["targets.json"] = MetaFile(targets.signed.version)
    snapshot_bytes = _signed(snapshot, signers[Snapshot.type])

    timestamp = Metadata(Timestamp(expires=expires))
    timestamp.signed.snapshot_meta = MetaFile(snapshot.signed.version)
    timestamp_bytes = _signed(timestamp, signers[Timestamp.type])

    objects = {
        "/metadata/2.root.json": root_v2_bytes,
        "/metadata/timestamp.json": timestamp_bytes,
        "/metadata/snapshot.json": snapshot_bytes,
        "/metadata/targets.json": targets_bytes,
        f"/targets/{DEFAULT_CONSUMER_TRUST_TARGET}": profile_bytes,
    }
    return root_v1_bytes, objects


def test_tuf_bootstrap_rotates_root_and_fetches_consumer_profile(tmp_path: Path) -> None:
    profile_bytes = PROFILE_PATH.read_bytes()
    bootstrap, objects = _repository(profile_bytes)
    update = fetch_consumer_trust_profile(
        bootstrap_root=bootstrap,
        metadata_dir=tmp_path / "metadata",
        metadata_base_url="https://repo.example/metadata/",
        target_dir=tmp_path / "targets",
        target_base_url="https://repo.example/targets/",
        fetcher=MemoryFetcher(objects),
        expected_profile_id=EXPECTED_PROFILE_ID,
    )

    assert update.profile.digest() == EXPECTED_PROFILE_DIGEST
    assert update.receipt.trusted_root_version == 2
    assert update.receipt.bootstrap_root_digest == f"sha256:{hashlib.sha256(bootstrap).hexdigest()}"
    assert update.receipt.profile_digest == EXPECTED_PROFILE_DIGEST
    assert update.receipt.target_path == DEFAULT_CONSUMER_TRUST_TARGET
    assert dict(update.receipt.target_hashes)["sha256"] == hashlib.sha256(profile_bytes).hexdigest()

    round_trip = TrustProfileUpdateReceipt.from_record(update.receipt.record())
    assert round_trip == update.receipt


def test_tuf_rejects_target_tampering(tmp_path: Path) -> None:
    profile_bytes = PROFILE_PATH.read_bytes()
    bootstrap, objects = _repository(profile_bytes)
    objects[f"/targets/{DEFAULT_CONSUMER_TRUST_TARGET}"] = profile_bytes + b"\n "

    with pytest.raises(LengthOrHashMismatchError):
        fetch_consumer_trust_profile(
            bootstrap_root=bootstrap,
            metadata_dir=tmp_path / "metadata",
            metadata_base_url="https://repo.example/metadata/",
            target_dir=tmp_path / "targets",
            target_base_url="https://repo.example/targets/",
            fetcher=MemoryFetcher(objects),
        )


def test_tuf_rejects_root_rotation_without_old_root_threshold(tmp_path: Path) -> None:
    bootstrap, objects = _repository(PROFILE_PATH.read_bytes(), dual_signed_root=False)

    with pytest.raises(UnsignedMetadataError):
        fetch_consumer_trust_profile(
            bootstrap_root=bootstrap,
            metadata_dir=tmp_path / "metadata",
            metadata_base_url="https://repo.example/metadata/",
            target_dir=tmp_path / "targets",
            target_base_url="https://repo.example/targets/",
            fetcher=MemoryFetcher(objects),
        )


def test_distribution_module_imports_without_tuf_dependency() -> None:
    import howedo.trust_distribution as distribution

    assert distribution.DEFAULT_CONSUMER_TRUST_TARGET == DEFAULT_CONSUMER_TRUST_TARGET

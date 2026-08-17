from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from howedo.consumer_trust import (
    CONSUMER_TRUST_PROFILE_VERSION,
    ConsumerTrustProfile,
    load_consumer_trust_profile,
)
from howedo.protocol import canonical_digest

TRUST_DISTRIBUTION_RECEIPT_VERSION = "howedo.trust-distribution-receipt.v1"
DEFAULT_CONSUMER_TRUST_TARGET = "howedo/github-actions-consumer-trust-v1.json"

_RECEIPT_KEYS = {
    "bootstrap_root_digest",
    "profile_digest",
    "profile_id",
    "receipt_digest",
    "receipt_version",
    "target_hashes",
    "target_length",
    "target_path",
    "trusted_root_version",
}


@dataclass(frozen=True, slots=True)
class TrustProfileUpdateReceipt:
    bootstrap_root_digest: str
    trusted_root_version: int
    target_path: str
    target_length: int
    target_hashes: tuple[tuple[str, str], ...]
    profile_id: str
    profile_digest: str
    receipt_version: str = TRUST_DISTRIBUTION_RECEIPT_VERSION

    def __post_init__(self) -> None:
        if self.receipt_version != TRUST_DISTRIBUTION_RECEIPT_VERSION:
            raise ValueError("unsupported trust distribution receipt version")
        if not _is_sha256_digest(self.bootstrap_root_digest):
            raise ValueError("bootstrap_root_digest must be sha256:<64 lowercase hex>")
        if self.trusted_root_version < 1:
            raise ValueError("trusted_root_version must be positive")
        if not self.target_path or self.target_path.startswith("/"):
            raise ValueError("target_path must be a non-empty relative path")
        if ".." in Path(self.target_path).parts:
            raise ValueError("target_path must not contain parent traversal")
        if self.target_length < 0:
            raise ValueError("target_length must be non-negative")
        if not self.target_hashes:
            raise ValueError("target_hashes must be non-empty")
        if tuple(sorted(set(self.target_hashes))) != self.target_hashes:
            raise ValueError("target_hashes must be sorted and unique")
        for algorithm, digest in self.target_hashes:
            if not algorithm or not re.fullmatch(r"[0-9a-f]+", digest):
                raise ValueError("target hashes must contain lowercase hexadecimal digests")
        if not self.profile_id:
            raise ValueError("profile_id must be non-empty")
        if not _is_sha256_digest(self.profile_digest):
            raise ValueError("profile_digest must be sha256:<64 lowercase hex>")

    def canonical(self) -> dict[str, Any]:
        return {
            "bootstrap_root_digest": self.bootstrap_root_digest,
            "profile_digest": self.profile_digest,
            "profile_id": self.profile_id,
            "receipt_version": self.receipt_version,
            "target_hashes": [
                {"algorithm": algorithm, "digest": digest}
                for algorithm, digest in self.target_hashes
            ],
            "target_length": self.target_length,
            "target_path": self.target_path,
            "trusted_root_version": self.trusted_root_version,
        }

    def digest(self) -> str:
        return canonical_digest(self.canonical())

    def record(self) -> dict[str, Any]:
        record = self.canonical()
        record["receipt_digest"] = self.digest()
        return record

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> TrustProfileUpdateReceipt:
        if set(record) != _RECEIPT_KEYS:
            raise ValueError("trust distribution receipt shape mismatch")
        raw_hashes = record.get("target_hashes")
        if not isinstance(raw_hashes, list):
            raise TypeError("target_hashes must be a list")
        hashes: list[tuple[str, str]] = []
        for item in raw_hashes:
            if not isinstance(item, dict) or set(item) != {"algorithm", "digest"}:
                raise ValueError("target hash entry shape mismatch")
            algorithm = item.get("algorithm")
            digest = item.get("digest")
            if not isinstance(algorithm, str) or not isinstance(digest, str):
                raise TypeError("target hash fields must be strings")
            hashes.append((algorithm, digest))
        receipt = cls(
            bootstrap_root_digest=_required_string(record, "bootstrap_root_digest"),
            trusted_root_version=_required_int(record, "trusted_root_version"),
            target_path=_required_string(record, "target_path"),
            target_length=_required_int(record, "target_length"),
            target_hashes=tuple(hashes),
            profile_id=_required_string(record, "profile_id"),
            profile_digest=_required_string(record, "profile_digest"),
            receipt_version=_required_string(record, "receipt_version"),
        )
        if record.get("receipt_digest") != receipt.digest():
            raise ValueError("trust distribution receipt digest mismatch")
        return receipt


@dataclass(frozen=True, slots=True)
class TrustProfileUpdate:
    profile: ConsumerTrustProfile
    receipt: TrustProfileUpdateReceipt
    profile_path: Path


def fetch_consumer_trust_profile(
    *,
    bootstrap_root: bytes,
    metadata_dir: str | Path,
    metadata_base_url: str,
    target_dir: str | Path,
    target_base_url: str,
    target_path: str = DEFAULT_CONSUMER_TRUST_TARGET,
    fetcher: Any | None = None,
    expected_profile_id: str | None = None,
    expected_profile_version: str = CONSUMER_TRUST_PROFILE_VERSION,
) -> TrustProfileUpdate:
    if not bootstrap_root:
        raise ValueError("bootstrap_root must be non-empty out-of-band trusted bytes")
    if not metadata_base_url or not target_base_url:
        raise ValueError("TUF metadata and target base URLs must be non-empty")
    if not target_path or target_path.startswith("/") or ".." in Path(target_path).parts:
        raise ValueError("target_path must be safe and relative")

    try:
        from tuf.api.metadata import Metadata
        from tuf.ngclient import Updater
    except ImportError as exc:
        raise RuntimeError(
            "TUF support is optional; install howedo-continuity[tuf]"
        ) from exc

    metadata_path = Path(metadata_dir)
    target_directory = Path(target_dir)
    metadata_path.mkdir(parents=True, exist_ok=True)
    target_directory.mkdir(parents=True, exist_ok=True)

    updater = Updater(
        str(metadata_path),
        metadata_base_url,
        str(target_directory),
        target_base_url,
        fetcher,
        bootstrap=bootstrap_root,
    )
    updater.refresh()

    target_info = updater.get_targetinfo(target_path)
    if target_info is None:
        raise FileNotFoundError(f"TUF target not found: {target_path}")
    profile_file = Path(updater.download_target(target_info))

    raw = json.loads(profile_file.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("consumer trust profile target must contain a JSON object")
    profile = load_consumer_trust_profile(raw)
    if profile.profile_version != expected_profile_version:
        raise ValueError("consumer trust profile version mismatch")
    if expected_profile_id is not None and profile.profile_id != expected_profile_id:
        raise ValueError("consumer trust profile id mismatch")

    trusted_root = Metadata.from_file(str(metadata_path / "root.json"))
    receipt = TrustProfileUpdateReceipt(
        bootstrap_root_digest=f"sha256:{sha256(bootstrap_root).hexdigest()}",
        trusted_root_version=trusted_root.signed.version,
        target_path=target_info.path,
        target_length=target_info.length,
        target_hashes=tuple(sorted(target_info.hashes.items())),
        profile_id=profile.profile_id,
        profile_digest=profile.digest(),
    )
    return TrustProfileUpdate(profile=profile, receipt=receipt, profile_path=profile_file)


def load_trust_profile_update_receipt(record: dict[str, Any]) -> TrustProfileUpdateReceipt:
    return TrustProfileUpdateReceipt.from_record(record)


def _is_sha256_digest(value: str) -> bool:
    return re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None


def _required_string(record: dict[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{key} must be a non-empty string")
    return value


def _required_int(record: dict[str, Any], key: str) -> int:
    value = record.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{key} must be an integer")
    return value

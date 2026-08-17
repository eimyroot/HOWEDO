from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from howedo.protocol import canonical_digest

TRUST_ROOT_PUBLICATION_POLICY_VERSION = "howedo.trust-root-publication-policy.v1"
TRUST_ROOT_PUBLICATION_MANIFEST_VERSION = "howedo.trust-root-publication-manifest.v1"
_REQUIRED_TOP_LEVEL_ROLES = ("root", "snapshot", "targets", "timestamp")


@dataclass(frozen=True, slots=True)
class TrustRootPublicationPolicy:
    policy_id: str
    minimum_root_keys: int = 3
    minimum_root_threshold: int = 2
    minimum_root_validity_days: int = 180
    require_consistent_snapshot: bool = True
    require_disjoint_role_keys: bool = True
    require_https_endpoints: bool = True
    required_spec_major: int = 1
    policy_version: str = TRUST_ROOT_PUBLICATION_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.policy_version != TRUST_ROOT_PUBLICATION_POLICY_VERSION:
            raise ValueError("unsupported trust-root publication policy version")
        if not self.policy_id:
            raise ValueError("policy_id must be non-empty")
        if self.minimum_root_keys < 1:
            raise ValueError("minimum_root_keys must be positive")
        if self.minimum_root_threshold < 1:
            raise ValueError("minimum_root_threshold must be positive")
        if self.minimum_root_threshold > self.minimum_root_keys:
            raise ValueError("minimum_root_threshold cannot exceed minimum_root_keys")
        if self.minimum_root_validity_days < 1:
            raise ValueError("minimum_root_validity_days must be positive")
        if self.required_spec_major < 1:
            raise ValueError("required_spec_major must be positive")

    def canonical(self) -> dict[str, Any]:
        return {
            "minimum_root_keys": self.minimum_root_keys,
            "minimum_root_threshold": self.minimum_root_threshold,
            "minimum_root_validity_days": self.minimum_root_validity_days,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "require_consistent_snapshot": self.require_consistent_snapshot,
            "require_disjoint_role_keys": self.require_disjoint_role_keys,
            "require_https_endpoints": self.require_https_endpoints,
            "required_spec_major": self.required_spec_major,
        }

    def digest(self) -> str:
        return canonical_digest(self.canonical())


@dataclass(frozen=True, slots=True)
class PublishedRole:
    name: str
    keyids: tuple[str, ...]
    threshold: int

    def __post_init__(self) -> None:
        if self.name not in _REQUIRED_TOP_LEVEL_ROLES:
            raise ValueError(f"unsupported top-level role: {self.name}")
        if not self.keyids:
            raise ValueError(f"{self.name} keyids must be non-empty")
        if tuple(sorted(set(self.keyids))) != self.keyids:
            raise ValueError(f"{self.name} keyids must be sorted and unique")
        if self.threshold < 1 or self.threshold > len(self.keyids):
            raise ValueError(f"{self.name} threshold must be within the role key set")

    def canonical(self) -> dict[str, Any]:
        return {"keyids": list(self.keyids), "name": self.name, "threshold": self.threshold}


@dataclass(frozen=True, slots=True)
class PublishedRootVersion:
    version: int
    digest: str

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("published root version must be positive")
        if not _is_sha256_digest(self.digest):
            raise ValueError("published root digest must be sha256:<64 lowercase hex>")

    def canonical(self) -> dict[str, Any]:
        return {"digest": self.digest, "version": self.version}


@dataclass(frozen=True, slots=True)
class TrustRootPublicationManifest:
    publication_id: str
    policy_digest: str
    root_history: tuple[PublishedRootVersion, ...]
    root_expires: str
    verified_at: str
    spec_version: str
    consistent_snapshot: bool
    roles: tuple[PublishedRole, ...]
    metadata_base_url: str
    target_base_url: str
    target_path: str
    consumer_profile_id: str
    manifest_version: str = TRUST_ROOT_PUBLICATION_MANIFEST_VERSION

    def __post_init__(self) -> None:
        if self.manifest_version != TRUST_ROOT_PUBLICATION_MANIFEST_VERSION:
            raise ValueError("unsupported trust-root publication manifest version")
        if not self.publication_id:
            raise ValueError("publication_id must be non-empty")
        if not _is_sha256_digest(self.policy_digest):
            raise ValueError("policy_digest must be sha256:<64 lowercase hex>")
        if not self.root_history:
            raise ValueError("root_history must be non-empty")
        expected_versions = tuple(range(1, len(self.root_history) + 1))
        if tuple(item.version for item in self.root_history) != expected_versions:
            raise ValueError("root_history must retain every released root version from 1..N")
        _parse_utc(self.root_expires)
        _parse_utc(self.verified_at)
        role_names = tuple(role.name for role in self.roles)
        if role_names != _REQUIRED_TOP_LEVEL_ROLES:
            raise ValueError("roles must contain root,snapshot,targets,timestamp in canonical order")
        if not self.target_path or self.target_path.startswith("/"):
            raise ValueError("target_path must be a non-empty relative path")
        if ".." in Path(self.target_path).parts:
            raise ValueError("target_path must not contain parent traversal")
        if not self.consumer_profile_id:
            raise ValueError("consumer_profile_id must be non-empty")

    @property
    def root_version(self) -> int:
        return self.root_history[-1].version

    @property
    def bootstrap_root_digest(self) -> str:
        return self.root_history[0].digest

    @property
    def current_root_digest(self) -> str:
        return self.root_history[-1].digest

    def canonical(self) -> dict[str, Any]:
        return {
            "consistent_snapshot": self.consistent_snapshot,
            "consumer_profile_id": self.consumer_profile_id,
            "manifest_version": self.manifest_version,
            "metadata_base_url": self.metadata_base_url,
            "policy_digest": self.policy_digest,
            "publication_id": self.publication_id,
            "roles": [role.canonical() for role in self.roles],
            "root_expires": self.root_expires,
            "root_history": [item.canonical() for item in self.root_history],
            "spec_version": self.spec_version,
            "target_base_url": self.target_base_url,
            "target_path": self.target_path,
            "verified_at": self.verified_at,
        }

    def digest(self) -> str:
        return canonical_digest(self.canonical())

    def record(self) -> dict[str, Any]:
        record = self.canonical()
        record["manifest_digest"] = self.digest()
        return record


def load_publication_policy(record: dict[str, Any]) -> TrustRootPublicationPolicy:
    expected = {
        "minimum_root_keys",
        "minimum_root_threshold",
        "minimum_root_validity_days",
        "policy_id",
        "policy_version",
        "require_consistent_snapshot",
        "require_disjoint_role_keys",
        "require_https_endpoints",
        "required_spec_major",
    }
    if set(record) != expected:
        raise ValueError("trust-root publication policy shape mismatch")
    return TrustRootPublicationPolicy(
        policy_id=_required_string(record, "policy_id"),
        minimum_root_keys=_required_int(record, "minimum_root_keys"),
        minimum_root_threshold=_required_int(record, "minimum_root_threshold"),
        minimum_root_validity_days=_required_int(record, "minimum_root_validity_days"),
        require_consistent_snapshot=_required_bool(record, "require_consistent_snapshot"),
        require_disjoint_role_keys=_required_bool(record, "require_disjoint_role_keys"),
        require_https_endpoints=_required_bool(record, "require_https_endpoints"),
        required_spec_major=_required_int(record, "required_spec_major"),
        policy_version=_required_string(record, "policy_version"),
    )


def build_trust_root_publication_manifest(
    *,
    root_history: tuple[bytes, ...],
    policy: TrustRootPublicationPolicy,
    publication_id: str,
    metadata_base_url: str,
    target_base_url: str,
    target_path: str,
    consumer_profile_id: str,
    verified_at: datetime,
) -> TrustRootPublicationManifest:
    verified_at = _normalize_utc(verified_at)
    verified_history, current = _verify_root_history(root_history)
    current_root = current.signed
    spec_version = current_root.spec_version
    spec_major = _parse_spec_major(spec_version)
    if spec_major != policy.required_spec_major:
        raise ValueError("TUF root spec major does not match publication policy")
    if policy.require_consistent_snapshot and not current_root.consistent_snapshot:
        raise ValueError("production publication policy requires consistent snapshots")
    if policy.require_https_endpoints:
        _require_https(metadata_base_url, "metadata_base_url")
        _require_https(target_base_url, "target_base_url")

    roles = _extract_roles(current_root)
    root_role = roles[0]
    if len(root_role.keyids) < policy.minimum_root_keys:
        raise ValueError("root role does not meet minimum key count")
    if root_role.threshold < policy.minimum_root_threshold:
        raise ValueError("root role does not meet minimum threshold")
    if policy.require_disjoint_role_keys:
        _require_disjoint_role_keys(roles)
    minimum_expiry = verified_at + timedelta(days=policy.minimum_root_validity_days)
    if current_root.expires < minimum_expiry:
        raise ValueError("current TUF root does not meet minimum validity window")

    return TrustRootPublicationManifest(
        publication_id=publication_id,
        policy_digest=policy.digest(),
        root_history=verified_history,
        root_expires=current_root.expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        verified_at=verified_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        spec_version=spec_version,
        consistent_snapshot=current_root.consistent_snapshot,
        roles=roles,
        metadata_base_url=metadata_base_url,
        target_base_url=target_base_url,
        target_path=target_path,
        consumer_profile_id=consumer_profile_id,
    )


def verify_trust_root_publication(
    *,
    root_history: tuple[bytes, ...],
    manifest_record: dict[str, Any],
    policy: TrustRootPublicationPolicy,
) -> TrustRootPublicationManifest:
    manifest = load_trust_root_publication_manifest(manifest_record)
    if manifest.policy_digest != policy.digest():
        raise ValueError("publication manifest policy digest mismatch")
    rebuilt = build_trust_root_publication_manifest(
        root_history=root_history,
        policy=policy,
        publication_id=manifest.publication_id,
        metadata_base_url=manifest.metadata_base_url,
        target_base_url=manifest.target_base_url,
        target_path=manifest.target_path,
        consumer_profile_id=manifest.consumer_profile_id,
        verified_at=_parse_utc(manifest.verified_at),
    )
    if rebuilt != manifest:
        raise ValueError("publication manifest does not match root history and policy")
    return manifest


def load_trust_root_publication_manifest(record: dict[str, Any]) -> TrustRootPublicationManifest:
    expected = {
        "consistent_snapshot",
        "consumer_profile_id",
        "manifest_digest",
        "manifest_version",
        "metadata_base_url",
        "policy_digest",
        "publication_id",
        "roles",
        "root_expires",
        "root_history",
        "spec_version",
        "target_base_url",
        "target_path",
        "verified_at",
    }
    if set(record) != expected:
        raise ValueError("trust-root publication manifest shape mismatch")
    raw_roles = record.get("roles")
    if not isinstance(raw_roles, list):
        raise TypeError("roles must be a list")
    roles: list[PublishedRole] = []
    for raw in raw_roles:
        if not isinstance(raw, dict) or set(raw) != {"keyids", "name", "threshold"}:
            raise ValueError("published role shape mismatch")
        keyids = raw.get("keyids")
        if not isinstance(keyids, list) or not all(isinstance(item, str) for item in keyids):
            raise TypeError("published role keyids must be a string list")
        roles.append(PublishedRole(name=_required_string(raw, "name"), keyids=tuple(keyids), threshold=_required_int(raw, "threshold")))
    raw_history = record.get("root_history")
    if not isinstance(raw_history, list):
        raise TypeError("root_history must be a list")
    history: list[PublishedRootVersion] = []
    for raw in raw_history:
        if not isinstance(raw, dict) or set(raw) != {"digest", "version"}:
            raise ValueError("published root history entry shape mismatch")
        history.append(PublishedRootVersion(version=_required_int(raw, "version"), digest=_required_string(raw, "digest")))
    manifest = TrustRootPublicationManifest(
        publication_id=_required_string(record, "publication_id"),
        policy_digest=_required_string(record, "policy_digest"),
        root_history=tuple(history),
        root_expires=_required_string(record, "root_expires"),
        verified_at=_required_string(record, "verified_at"),
        spec_version=_required_string(record, "spec_version"),
        consistent_snapshot=_required_bool(record, "consistent_snapshot"),
        roles=tuple(roles),
        metadata_base_url=_required_string(record, "metadata_base_url"),
        target_base_url=_required_string(record, "target_base_url"),
        target_path=_required_string(record, "target_path"),
        consumer_profile_id=_required_string(record, "consumer_profile_id"),
        manifest_version=_required_string(record, "manifest_version"),
    )
    if record.get("manifest_digest") != manifest.digest():
        raise ValueError("trust-root publication manifest digest mismatch")
    return manifest


def _verify_root_history(root_history: tuple[bytes, ...]) -> tuple[tuple[PublishedRootVersion, ...], Any]:
    if not root_history:
        raise ValueError("root_history must contain at least bootstrap root v1")
    try:
        from tuf.api.metadata import Metadata, Root
    except ImportError as exc:
        raise RuntimeError("TUF support is optional; install howedo-continuity[tuf]") from exc

    previous = None
    published: list[PublishedRootVersion] = []
    current = None
    for expected_version, root_bytes in enumerate(root_history, start=1):
        if not root_bytes:
            raise ValueError("root history contains an empty metadata file")
        metadata = Metadata.from_bytes(root_bytes)
        if not isinstance(metadata.signed, Root):
            raise ValueError("root history may contain only TUF root metadata")
        if metadata.signed.version != expected_version:
            raise ValueError("root history must retain contiguous versions from 1..N")
        previous_root = previous.signed if previous is not None else None
        result = metadata.signed.get_root_verification_result(previous_root, metadata.signed_bytes, metadata.signatures)
        if not result:
            raise ValueError(f"TUF root v{expected_version} signature threshold verification failed")
        published.append(PublishedRootVersion(version=expected_version, digest=f"sha256:{sha256(root_bytes).hexdigest()}"))
        previous = metadata
        current = metadata
    assert current is not None
    return tuple(published), current


def _extract_roles(root: Any) -> tuple[PublishedRole, ...]:
    result: list[PublishedRole] = []
    for role_name in _REQUIRED_TOP_LEVEL_ROLES:
        role = root.roles.get(role_name)
        if role is None:
            raise ValueError(f"missing TUF top-level role: {role_name}")
        result.append(PublishedRole(name=role_name, keyids=tuple(sorted(role.keyids)), threshold=role.threshold))
    return tuple(result)


def _require_disjoint_role_keys(roles: tuple[PublishedRole, ...]) -> None:
    owner: dict[str, str] = {}
    for role in roles:
        for keyid in role.keyids:
            previous = owner.get(keyid)
            if previous is not None:
                raise ValueError(f"TUF role key reuse is forbidden by policy: {previous}/{role.name}")
            owner[keyid] = role.name


def _parse_spec_major(spec_version: str) -> int:
    match = re.fullmatch(r"(\d+)\.\d+(?:\.\d+)?", spec_version)
    if match is None:
        raise ValueError("invalid TUF spec_version")
    return int(match.group(1))


def _require_https(value: str, field: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{field} must be an absolute HTTPS URL")


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


def _required_bool(record: dict[str, Any], key: str) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise TypeError(f"{key} must be a boolean")
    return value


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be ISO-8601 UTC") from exc
    return _normalize_utc(parsed)


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("timestamp must be timezone-aware UTC")
    return value.astimezone(timezone.utc).replace(microsecond=0)

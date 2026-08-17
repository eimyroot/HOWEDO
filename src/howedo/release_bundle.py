from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from howedo.protocol import canonical_digest

RELEASE_BUNDLE_VERSION = "howedo.release-bundle.v1"
RELEASE_PACKAGE_NAME = "howedo-continuity"

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
_VERSION_RE = re.compile(r"^[0-9]+(?:\.[0-9]+){2}(?:[A-Za-z0-9.+-]*)?$")
_REQUIRED_FILE_ROLES = {"wheel", "sdist", "sbom"}


@dataclass(frozen=True, slots=True)
class ReleaseFile:
    path: str
    digest: str
    size: int

    def __post_init__(self) -> None:
        candidate = Path(self.path)
        if not self.path or candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("release file path must be safe and relative")
        if not _SHA256_RE.fullmatch(self.digest):
            raise ValueError("release file digest must be sha256:<64 lowercase hex>")
        if self.size < 0:
            raise ValueError("release file size must be non-negative")

    def canonical(self) -> dict[str, Any]:
        return {"digest": self.digest, "path": self.path, "size": self.size}


@dataclass(frozen=True, slots=True)
class ReleaseBundleManifest:
    package_name: str
    package_version: str
    tag: str
    git_commit: str
    git_tree: str
    files: Mapping[str, ReleaseFile]
    bundle_version: str = RELEASE_BUNDLE_VERSION

    def __post_init__(self) -> None:
        if self.bundle_version != RELEASE_BUNDLE_VERSION:
            raise ValueError("unsupported release bundle version")
        if self.package_name != RELEASE_PACKAGE_NAME:
            raise ValueError("unexpected release package name")
        if not _VERSION_RE.fullmatch(self.package_version):
            raise ValueError("invalid package version")
        if self.tag != f"v{self.package_version}":
            raise ValueError("release tag must equal v<package_version>")
        if not _HEX40_RE.fullmatch(self.git_commit):
            raise ValueError("git_commit must be 40 lowercase hex characters")
        if not _HEX40_RE.fullmatch(self.git_tree):
            raise ValueError("git_tree must be 40 lowercase hex characters")
        if set(self.files) != _REQUIRED_FILE_ROLES:
            raise ValueError("release bundle must contain wheel, sdist, and sbom roles")

        wheel = self.files["wheel"].path
        sdist = self.files["sdist"].path
        sbom = self.files["sbom"].path
        if not wheel.endswith(".whl"):
            raise ValueError("wheel role must reference a .whl file")
        if not sdist.endswith(".tar.gz"):
            raise ValueError("sdist role must reference a .tar.gz file")
        if not sbom.endswith(".cdx.json"):
            raise ValueError("sbom role must reference a .cdx.json file")

    def canonical(self) -> dict[str, Any]:
        return {
            "bundle_version": self.bundle_version,
            "files": {key: self.files[key].canonical() for key in sorted(self.files)},
            "git_commit": self.git_commit,
            "git_tree": self.git_tree,
            "package_name": self.package_name,
            "package_version": self.package_version,
            "tag": self.tag,
        }

    def digest(self) -> str:
        return canonical_digest(self.canonical())

    def record(self) -> dict[str, Any]:
        record = self.canonical()
        record["bundle_digest"] = self.digest()
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "ReleaseBundleManifest":
        expected = {
            "bundle_digest",
            "bundle_version",
            "files",
            "git_commit",
            "git_tree",
            "package_name",
            "package_version",
            "tag",
        }
        if set(record) != expected:
            raise ValueError("release bundle manifest shape mismatch")
        raw_files = record.get("files")
        if not isinstance(raw_files, Mapping):
            raise TypeError("files must be an object")
        files: dict[str, ReleaseFile] = {}
        for role, value in raw_files.items():
            if not isinstance(role, str) or not isinstance(value, Mapping):
                raise TypeError("release file entries must be objects")
            if set(value) != {"digest", "path", "size"}:
                raise ValueError("release file entry shape mismatch")
            size = value.get("size")
            if not isinstance(size, int) or isinstance(size, bool):
                raise TypeError("release file size must be an integer")
            files[role] = ReleaseFile(
                path=_required_string(value, "path"),
                digest=_required_string(value, "digest"),
                size=size,
            )
        manifest = cls(
            package_name=_required_string(record, "package_name"),
            package_version=_required_string(record, "package_version"),
            tag=_required_string(record, "tag"),
            git_commit=_required_string(record, "git_commit"),
            git_tree=_required_string(record, "git_tree"),
            files=files,
            bundle_version=_required_string(record, "bundle_version"),
        )
        if record.get("bundle_digest") != manifest.digest():
            raise ValueError("release bundle digest mismatch")
        return manifest


def build_release_bundle(
    *,
    root: Path,
    package_version: str,
    tag: str,
    git_commit: str,
    git_tree: str,
    wheel: str,
    sdist: str,
    sbom: str,
) -> ReleaseBundleManifest:
    files = {
        "wheel": _release_file(root, wheel),
        "sdist": _release_file(root, sdist),
        "sbom": _release_file(root, sbom),
    }
    return ReleaseBundleManifest(
        package_name=RELEASE_PACKAGE_NAME,
        package_version=package_version,
        tag=tag,
        git_commit=git_commit,
        git_tree=git_tree,
        files=files,
    )


def verify_release_bundle(
    record: Mapping[str, Any],
    *,
    root: Path,
    expected_tag: str | None = None,
    expected_commit: str | None = None,
    expected_tree: str | None = None,
) -> ReleaseBundleManifest:
    manifest = ReleaseBundleManifest.from_record(record)
    if expected_tag is not None and manifest.tag != expected_tag:
        raise ValueError("release tag does not match expected tag")
    if expected_commit is not None and manifest.git_commit != expected_commit:
        raise ValueError("release commit does not match expected commit")
    if expected_tree is not None and manifest.git_tree != expected_tree:
        raise ValueError("release tree does not match expected tree")
    for release_file in manifest.files.values():
        actual = _release_file(root, release_file.path)
        if actual != release_file:
            raise ValueError(f"release file integrity mismatch: {release_file.path}")
    return manifest


def _release_file(root: Path, relative_path: str) -> ReleaseFile:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("release file path must be safe and relative")
    full_path = root / candidate
    if not full_path.is_file() or full_path.is_symlink():
        raise ValueError(f"release file missing or unsafe: {relative_path}")
    payload = full_path.read_bytes()
    return ReleaseFile(
        path=candidate.as_posix(),
        digest=f"sha256:{sha256(payload).hexdigest()}",
        size=len(payload),
    )


def _required_string(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{key} must be a non-empty string")
    return value

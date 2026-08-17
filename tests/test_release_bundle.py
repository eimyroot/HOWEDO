from __future__ import annotations

from pathlib import Path

import pytest

from howedo.release_bundle import build_release_bundle, verify_release_bundle


def _files(root: Path) -> None:
    (root / "python").mkdir()
    (root / "evidence").mkdir()
    (root / "python/howedo_continuity-0.0.1-py3-none-any.whl").write_bytes(b"wheel")
    (root / "python/howedo_continuity-0.0.1.tar.gz").write_bytes(b"sdist")
    (root / "evidence/howedo-continuity-0.0.1.cdx.json").write_bytes(
        b'{"bomFormat":"CycloneDX"}'
    )


def _manifest(root: Path):
    return build_release_bundle(
        root=root,
        package_version="0.0.1",
        tag="v0.0.1",
        git_commit="a" * 40,
        git_tree="b" * 40,
        wheel="python/howedo_continuity-0.0.1-py3-none-any.whl",
        sdist="python/howedo_continuity-0.0.1.tar.gz",
        sbom="evidence/howedo-continuity-0.0.1.cdx.json",
    )


def test_release_bundle_round_trip(tmp_path: Path) -> None:
    _files(tmp_path)
    manifest = _manifest(tmp_path)
    verified = verify_release_bundle(
        manifest.record(),
        root=tmp_path,
        expected_tag="v0.0.1",
        expected_commit="a" * 40,
        expected_tree="b" * 40,
    )
    assert verified.digest() == manifest.digest()


def test_release_bundle_rejects_tampered_artifact(tmp_path: Path) -> None:
    _files(tmp_path)
    manifest = _manifest(tmp_path)
    (tmp_path / "python/howedo_continuity-0.0.1-py3-none-any.whl").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="integrity mismatch"):
        verify_release_bundle(manifest.record(), root=tmp_path)


def test_release_bundle_rejects_tag_version_mismatch(tmp_path: Path) -> None:
    _files(tmp_path)
    with pytest.raises(ValueError, match="release tag"):
        build_release_bundle(
            root=tmp_path,
            package_version="0.0.1",
            tag="v0.0.2",
            git_commit="a" * 40,
            git_tree="b" * 40,
            wheel="python/howedo_continuity-0.0.1-py3-none-any.whl",
            sdist="python/howedo_continuity-0.0.1.tar.gz",
            sbom="evidence/howedo-continuity-0.0.1.cdx.json",
        )


def test_release_bundle_rejects_symlink(tmp_path: Path) -> None:
    _files(tmp_path)
    target = tmp_path / "real.whl"
    target.write_bytes(b"wheel")
    link = tmp_path / "python/linked.whl"
    link.unlink(missing_ok=True)
    link.symlink_to(target)
    with pytest.raises(ValueError, match="missing or unsafe"):
        build_release_bundle(
            root=tmp_path,
            package_version="0.0.1",
            tag="v0.0.1",
            git_commit="a" * 40,
            git_tree="b" * 40,
            wheel="python/linked.whl",
            sdist="python/howedo_continuity-0.0.1.tar.gz",
            sbom="evidence/howedo-continuity-0.0.1.cdx.json",
        )


def test_release_bundle_rejects_manifest_digest_tamper(tmp_path: Path) -> None:
    _files(tmp_path)
    record = _manifest(tmp_path).record()
    record["bundle_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="bundle digest"):
        verify_release_bundle(record, root=tmp_path)


def test_release_bundle_v1_schema_set_is_frozen() -> None:
    expected = {"release-bundle.schema.json"}
    actual = {p.name for p in Path("schemas/release-bundle-v1").glob("*.json")}
    assert actual == expected

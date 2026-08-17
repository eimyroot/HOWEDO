from pathlib import Path


def test_release_candidate_stages_assets_before_publication() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    assert 'tags:\n      - "v*"' in workflow
    assert "gh release create" in workflow
    assert "--draft" in workflow
    assert "--verify-tag" in workflow
    assert "release:\n    types: [published]" not in workflow
    assert "password:" not in workflow
    assert "api-token" not in workflow


def test_pypi_publish_is_secretless_and_fail_closed() -> None:
    workflow = Path(".github/workflows/pypi-publish.yml").read_text(encoding="utf-8")
    assert "types: [published]" in workflow
    assert "HOWEDO_PYPI_PUBLISH_ENABLED == 'true'" in workflow
    assert "environment: pypi" in workflow
    assert "id-token: write" in workflow
    assert "gh release verify" in workflow
    assert "gh release verify-asset" in workflow
    assert "password:" not in workflow
    assert "api-token" not in workflow

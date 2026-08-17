from __future__ import annotations

import subprocess

from howedo.sigstore_trust import SigstoreGithubClaims, verify_sigstore_github_bundle


def claims() -> SigstoreGithubClaims:
    return SigstoreGithubClaims(
        identity=(
            "https://github.com/nulleimy/HOWEDO/.github/workflows/"
            "consolidation.yml@refs/pull/14/merge"
        ),
        issuer="https://token.actions.githubusercontent.com",
        repository="nulleimy/HOWEDO",
        workflow_sha="a" * 40,
        workflow_ref="refs/pull/14/merge",
        workflow_trigger="pull_request",
    )


def test_cosign_reference_verifier_pins_all_github_claims(monkeypatch) -> None:
    captured: list[str] = []

    def fake_run(command, **kwargs):
        captured.extend(command)
        assert kwargs["check"] is False
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        return subprocess.CompletedProcess(command, 0, stdout="Verified OK", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = verify_sigstore_github_bundle(
        "statement.json",
        "bundle.json",
        claims(),
        cosign_executable="cosign-test",
    )

    assert result.verified
    assert captured == [
        "cosign-test",
        "verify-blob",
        "statement.json",
        "--bundle",
        "bundle.json",
        "--certificate-identity",
        claims().identity,
        "--certificate-oidc-issuer",
        claims().issuer,
        "--certificate-github-workflow-repository",
        claims().repository,
        "--certificate-github-workflow-sha",
        claims().workflow_sha,
        "--certificate-github-workflow-ref",
        claims().workflow_ref,
        "--certificate-github-workflow-trigger",
        claims().workflow_trigger,
    ]
    assert "--insecure-ignore-tlog" not in captured
    assert "--insecure-ignore-sct" not in captured


def test_cosign_failure_is_normalized(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="verification failed")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = verify_sigstore_github_bundle("statement.json", "bundle.json", claims())

    assert not result.verified
    assert result.detail == "verification failed"

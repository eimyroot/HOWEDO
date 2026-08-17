from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SigstoreGithubClaims:
    identity: str
    issuer: str
    repository: str
    workflow_sha: str
    workflow_ref: str
    workflow_trigger: str

    def __post_init__(self) -> None:
        if any(
            not value
            for value in (
                self.identity,
                self.issuer,
                self.repository,
                self.workflow_sha,
                self.workflow_ref,
                self.workflow_trigger,
            )
        ):
            raise ValueError("Sigstore GitHub claim expectations must be non-empty")


@dataclass(frozen=True, slots=True)
class SigstoreVerificationResult:
    verified: bool
    verifier_id: str = "sigstore-cosign"
    detail: str = ""


def verify_sigstore_github_bundle(
    statement_path: str | Path,
    bundle_path: str | Path,
    claims: SigstoreGithubClaims,
    *,
    cosign_executable: str = "cosign",
) -> SigstoreVerificationResult:
    """Verify one blob and exact GitHub OIDC claims through the Cosign CLI.

    Cosign is intentionally an external reference verifier. HOWEDO core does not
    import Sigstore libraries or implement certificate/transparency verification.
    """

    command = [
        cosign_executable,
        "verify-blob",
        str(statement_path),
        "--bundle",
        str(bundle_path),
        "--certificate-identity",
        claims.identity,
        "--certificate-oidc-issuer",
        claims.issuer,
        "--certificate-github-workflow-repository",
        claims.repository,
        "--certificate-github-workflow-sha",
        claims.workflow_sha,
        "--certificate-github-workflow-ref",
        claims.workflow_ref,
        "--certificate-github-workflow-trigger",
        claims.workflow_trigger,
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return SigstoreVerificationResult(verified=False, detail=str(exc))

    detail = (completed.stderr or completed.stdout).strip()
    return SigstoreVerificationResult(verified=completed.returncode == 0, detail=detail)

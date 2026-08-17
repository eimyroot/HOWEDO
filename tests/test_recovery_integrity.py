import pytest

from howedo import (
    ContinuityAction,
    RecoveryCheckpoint,
    RecoveryWitness,
    ResourceRevision,
    StateRegistry,
)


def revision(resource: str, version: str) -> ResourceRevision:
    return ResourceRevision(resource_id=resource, revision=version, digest=f"sha256:{version}")


def test_forged_checkpoint_id_is_rejected() -> None:
    registry = StateRegistry()
    registry.register(revision("repo://acme/app", "1"))
    snapshot = registry.snapshot(["repo://acme/app"])

    with pytest.raises(ValueError):
        RecoveryCheckpoint(checkpoint_id="sha256:forged", snapshot=snapshot)


def test_forged_recovery_witness_digest_is_rejected() -> None:
    registry = StateRegistry()
    registry.register(revision("repo://acme/app", "1"))
    snapshot = registry.snapshot(["repo://acme/app"])
    checkpoint = RecoveryCheckpoint.build(snapshot=snapshot)

    with pytest.raises(ValueError):
        RecoveryWitness(
            checkpoint_id=checkpoint.checkpoint_id,
            snapshot_id=snapshot.snapshot_id,
            action=ContinuityAction.RECOVER,
            reason_codes=("RECOVERY_VALIDATED",),
            witness_digest="sha256:forged",
        )

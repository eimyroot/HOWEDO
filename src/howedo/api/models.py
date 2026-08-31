from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from howedo.domain import ContinuityAction, Validity

Digest = Annotated[str, Field(min_length=1, max_length=256)]
ResourceId = Annotated[str, Field(min_length=1, max_length=512)]
Revision = Annotated[str, Field(min_length=1, max_length=256)]
CheckpointId = Annotated[str, Field(min_length=1, max_length=256)]
PositiveFence = Annotated[int, Field(gt=0)]


class ResourceRevisionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    resource_id: ResourceId
    revision: Revision
    digest: Digest


class ContinuityCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot: list[ResourceRevisionModel] = Field(min_length=1, max_length=1024)
    current_heads: list[ResourceRevisionModel] = Field(max_length=1024)
    validity: dict[str, Validity] = Field(default_factory=dict)


class FenceTokenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    resource_id: ResourceId
    value: PositiveFence


class RecoveryCheckpointModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    checkpoint_id: CheckpointId
    snapshot: list[ResourceRevisionModel] = Field(min_length=1, max_length=1024)
    fences: list[FenceTokenModel] = Field(default_factory=list, max_length=1024)


class RecoveryCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    checkpoint: RecoveryCheckpointModel
    current_heads: list[ResourceRevisionModel] = Field(max_length=1024)
    current_fences: dict[str, PositiveFence] = Field(default_factory=dict)
    validity: dict[str, Validity] = Field(default_factory=dict)


class ContinuityWitnessModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str
    action: ContinuityAction
    reason_codes: list[str]
    witness_digest: str


class ContinuityCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: ContinuityAction
    reason_codes: list[str]
    witness: ContinuityWitnessModel


class RecoveryWitnessModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    checkpoint_id: str
    snapshot_id: str
    action: ContinuityAction
    reason_codes: list[str]
    witness_digest: str


class RecoveryCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: ContinuityAction
    reason_codes: list[str]
    witness: RecoveryWitnessModel


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    service: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str

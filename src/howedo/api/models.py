from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from howedo.domain import ContinuityAction, Validity

Digest = Annotated[str, Field(min_length=1, max_length=256)]
ResourceId = Annotated[str, Field(min_length=1, max_length=512)]
Revision = Annotated[str, Field(min_length=1, max_length=256)]


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
    recovery_requested: bool = False


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


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    service: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version as package_version
from typing import Any, Protocol

from langgraph.types import Command, StateSnapshot

from howedo.concur import FenceToken
from howedo.domain import ContinuityAction, ContinuitySnapshot, ResourceRevision, Validity
from howedo.protocol import PROTOCOL_VERSION
from howedo.recovery import RecoveryCheckpoint, RecoveryDecision, RecoveryEngine
from howedo.semlock import SemanticComparator

RUNTIME_RESOURCE_ID = "runtime://langgraph"


class LangGraphProtocolError(RuntimeError):
    """Raised when LangGraph checkpoint metadata cannot satisfy the adapter contract."""


class LangGraphCheckpointMismatch(RuntimeError):
    """Raised when the requested LangGraph checkpoint cannot be resolved exactly."""


class ResumeBlocked(RuntimeError):
    """Raised when HOWEDO does not return RECOVER for a requested resume."""

    def __init__(self, decision: RecoveryDecision) -> None:
        self.decision = decision
        super().__init__(
            f"LangGraph resume blocked by HOWEDO: {decision.action.value} "
            f"{decision.reason_codes}"
        )


class LangGraphLike(Protocol):
    def get_state(self, config: Mapping[str, Any]) -> StateSnapshot: ...

    def invoke(self, input: Any, config: Mapping[str, Any]) -> Any: ...


@dataclass(frozen=True, slots=True)
class LangGraphCheckpointRef:
    thread_id: str
    checkpoint_id: str
    checkpoint_ns: str = ""

    def __post_init__(self) -> None:
        if not self.thread_id:
            raise ValueError("thread_id must be non-empty")
        if not self.checkpoint_id:
            raise ValueError("checkpoint_id must be non-empty")

    def config(self) -> dict[str, dict[str, str]]:
        configurable = {
            "thread_id": self.thread_id,
            "checkpoint_id": self.checkpoint_id,
        }
        if self.checkpoint_ns:
            configurable["checkpoint_ns"] = self.checkpoint_ns
        return {"configurable": configurable}


@dataclass(frozen=True, slots=True)
class LangGraphRecoveryBinding:
    checkpoint: LangGraphCheckpointRef
    recovery_checkpoint: RecoveryCheckpoint
    binding_digest: str
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError("unsupported HOWEDO protocol version")
        expected = self.compute_digest(
            checkpoint=self.checkpoint,
            recovery_checkpoint=self.recovery_checkpoint,
            protocol_version=self.protocol_version,
        )
        if expected != self.binding_digest:
            raise ValueError("LangGraph recovery binding digest mismatch")

    @classmethod
    def build(
        cls,
        *,
        checkpoint: LangGraphCheckpointRef,
        recovery_checkpoint: RecoveryCheckpoint,
    ) -> LangGraphRecoveryBinding:
        return cls(
            checkpoint=checkpoint,
            recovery_checkpoint=recovery_checkpoint,
            binding_digest=cls.compute_digest(
                checkpoint=checkpoint,
                recovery_checkpoint=recovery_checkpoint,
                protocol_version=PROTOCOL_VERSION,
            ),
        )

    @staticmethod
    def compute_digest(
        *,
        checkpoint: LangGraphCheckpointRef,
        recovery_checkpoint: RecoveryCheckpoint,
        protocol_version: str,
    ) -> str:
        payload = {
            "checkpoint_id": checkpoint.checkpoint_id,
            "checkpoint_ns": checkpoint.checkpoint_ns,
            "howedo_checkpoint_id": recovery_checkpoint.checkpoint_id,
            "protocol_version": protocol_version,
            "runtime": "langgraph",
            "thread_id": checkpoint.thread_id,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return f"sha256:{sha256(encoded).hexdigest()}"


class LangGraphRuntimeAdapter:
    """Binds exact LangGraph checkpoints to HOWEDO recovery validity checks."""

    def runtime_revision(self) -> ResourceRevision:
        runtime_version = package_version("langgraph")
        digest = f"sha256:{sha256(runtime_version.encode()).hexdigest()}"
        return ResourceRevision(
            resource_id=RUNTIME_RESOURCE_ID,
            revision=runtime_version,
            digest=digest,
        )

    def capture(
        self,
        graph: LangGraphLike,
        config: Mapping[str, Any],
        *,
        resources: Sequence[ResourceRevision],
        fences: Sequence[FenceToken] = (),
    ) -> LangGraphRecoveryBinding:
        state = graph.get_state(config)
        checkpoint = self._checkpoint_ref(state)
        snapshot = ContinuitySnapshot.build(self._with_runtime_revision(resources))
        recovery_checkpoint = RecoveryCheckpoint.build(
            snapshot=snapshot,
            fences=tuple(fences),
        )
        return LangGraphRecoveryBinding.build(
            checkpoint=checkpoint,
            recovery_checkpoint=recovery_checkpoint,
        )

    def validate_resume(
        self,
        graph: LangGraphLike,
        binding: LangGraphRecoveryBinding,
        *,
        current_heads: Mapping[str, ResourceRevision],
        current_fences: Mapping[str, int] | None = None,
        validity: Mapping[str, Validity] | None = None,
        semantic_comparator: SemanticComparator | None = None,
    ) -> RecoveryDecision:
        state = graph.get_state(binding.checkpoint.config())
        resolved = self._checkpoint_ref(state)
        if resolved != binding.checkpoint:
            raise LangGraphCheckpointMismatch(
                "LangGraph did not resolve the exact checkpoint bound by HOWEDO"
            )

        heads = dict(current_heads)
        heads[RUNTIME_RESOURCE_ID] = self.runtime_revision()
        return RecoveryEngine().validate(
            binding.recovery_checkpoint,
            current_heads=heads,
            current_fences=current_fences,
            validity=validity,
            semantic_comparator=semantic_comparator,
        )

    def resume_interrupt(
        self,
        graph: LangGraphLike,
        binding: LangGraphRecoveryBinding,
        resume_value: Any,
        *,
        current_heads: Mapping[str, ResourceRevision],
        current_fences: Mapping[str, int] | None = None,
        validity: Mapping[str, Validity] | None = None,
        semantic_comparator: SemanticComparator | None = None,
    ) -> Any:
        decision = self.validate_resume(
            graph,
            binding,
            current_heads=current_heads,
            current_fences=current_fences,
            validity=validity,
            semantic_comparator=semantic_comparator,
        )
        if decision.action is not ContinuityAction.RECOVER:
            raise ResumeBlocked(decision)
        return graph.invoke(Command(resume=resume_value), config=binding.checkpoint.config())

    def resume_static(
        self,
        graph: LangGraphLike,
        binding: LangGraphRecoveryBinding,
        *,
        current_heads: Mapping[str, ResourceRevision],
        current_fences: Mapping[str, int] | None = None,
        validity: Mapping[str, Validity] | None = None,
        semantic_comparator: SemanticComparator | None = None,
    ) -> Any:
        decision = self.validate_resume(
            graph,
            binding,
            current_heads=current_heads,
            current_fences=current_fences,
            validity=validity,
            semantic_comparator=semantic_comparator,
        )
        if decision.action is not ContinuityAction.RECOVER:
            raise ResumeBlocked(decision)
        return graph.invoke(None, config=binding.checkpoint.config())

    def _with_runtime_revision(
        self, resources: Sequence[ResourceRevision]
    ) -> tuple[ResourceRevision, ...]:
        runtime = self.runtime_revision()
        by_resource = {item.resource_id: item for item in resources}
        existing = by_resource.get(RUNTIME_RESOURCE_ID)
        if existing is not None and existing != runtime:
            raise LangGraphProtocolError(
                "caller supplied a conflicting runtime://langgraph revision"
            )
        by_resource[RUNTIME_RESOURCE_ID] = runtime
        return tuple(by_resource.values())

    @staticmethod
    def _checkpoint_ref(state: StateSnapshot) -> LangGraphCheckpointRef:
        configurable = state.config.get("configurable", {})
        thread_id = configurable.get("thread_id")
        checkpoint_id = configurable.get("checkpoint_id")
        checkpoint_ns = configurable.get("checkpoint_ns", "")
        if not isinstance(thread_id, str) or not thread_id:
            raise LangGraphProtocolError("LangGraph StateSnapshot is missing thread_id")
        if not isinstance(checkpoint_id, str) or not checkpoint_id:
            raise LangGraphProtocolError("LangGraph StateSnapshot is missing checkpoint_id")
        if not isinstance(checkpoint_ns, str):
            raise LangGraphProtocolError("LangGraph checkpoint_ns must be a string")
        return LangGraphCheckpointRef(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            checkpoint_ns=checkpoint_ns,
        )

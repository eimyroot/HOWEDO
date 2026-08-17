from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, TypeVar

from howedo.concur import FenceToken
from howedo.domain import ResourceRevision, Validity
from howedo.recovery import RecoveryDecision
from howedo.semlock import SemanticComparator

RuntimeT_contra = TypeVar("RuntimeT_contra", contravariant=True)
BindingT = TypeVar("BindingT")


class RuntimeAdapter(Protocol[RuntimeT_contra, BindingT]):
    """Vendor-neutral checkpoint-to-continuity adapter contract."""

    def capture(
        self,
        runtime: RuntimeT_contra,
        config: Mapping[str, Any],
        *,
        resources: Sequence[ResourceRevision],
        fences: Sequence[FenceToken] = (),
    ) -> BindingT: ...

    def validate_resume(
        self,
        runtime: RuntimeT_contra,
        binding: BindingT,
        *,
        current_heads: Mapping[str, ResourceRevision],
        current_fences: Mapping[str, int] | None = None,
        validity: Mapping[str, Validity] | None = None,
        semantic_comparator: SemanticComparator | None = None,
    ) -> RecoveryDecision: ...

"""Provider-neutral adapter port for already-authorized Tool execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping, Protocol

if TYPE_CHECKING:
    from apps.assistant.src.modules.tools import ToolDefinition, ToolProposal


@dataclass(frozen=True)
class ToolAdapterResult:
    succeeded: bool
    reason_code: str
    output: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.succeeded, bool):
            raise ValueError("tool adapter result succeeded must be boolean")
        if not isinstance(self.reason_code, str) or not self.reason_code or len(self.reason_code) > 128:
            raise ValueError("tool adapter result reason_code is invalid")
        if not isinstance(self.output, Mapping) or len(self.output) > 64:
            raise ValueError("tool adapter output must be a bounded object")
        copied: dict[str, object] = {}
        for key, value in self.output.items():
            if not isinstance(key, str) or not key or len(key) > 128:
                raise ValueError("tool adapter output contains an invalid key")
            if value is not None and not isinstance(value, (str, bool, int, float)):
                raise ValueError("tool adapter output supports scalar JSON values only")
            copied[key] = value
        object.__setattr__(self, "output", MappingProxyType(copied))


class ToolAdapter(Protocol):
    """Execute one reviewed Tool after policy and executor guards succeed."""

    def execute(
        self,
        definition: ToolDefinition,
        proposal: ToolProposal,
    ) -> ToolAdapterResult:
        """Perform only the capability represented by the registered definition."""


class DecisionReplayProtector(Protocol):
    def consume(self, decision_id: str) -> bool:
        """Atomically return True once; repeated decision IDs must return False."""

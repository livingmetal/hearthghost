"""Persistence port for atomic due-reminder delivery claims."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ReminderClaimRepository(Protocol):
    def claim_due(
        self,
        *,
        now: datetime,
        claim_owner: str,
        claim_until: datetime,
    ) -> object | None: ...

    def claim_is_current(self, claim: object) -> bool: ...

    def mark_delivered(
        self,
        claim: object,
        *,
        delivered_at: datetime,
        reason: str,
    ) -> bool: ...

    def mark_retry(
        self,
        claim: object,
        *,
        next_attempt_at: datetime,
        reason: str,
    ) -> bool: ...

    def mark_exhausted(self, claim: object, *, reason: str) -> bool: ...

"""Deny-only reminder delivery adapter used until a reviewed Node transport exists."""

from __future__ import annotations

from apps.assistant.src.modules.notification_delivery import (
    NotificationAdapterRequest,
    NotificationAdapterResult,
)


class DenyingReminderDeliveryAdapter:
    def deliver(self, request: object) -> NotificationAdapterResult:
        if not isinstance(request, NotificationAdapterRequest):
            return NotificationAdapterResult(False, "delivery_request_invalid")
        return NotificationAdapterResult(False, "delivery_not_configured")

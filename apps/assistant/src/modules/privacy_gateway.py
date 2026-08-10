"""Fail-closed policy boundary for content sent to an external model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from apps.assistant.src.ports.llm import (
    LLMCompletion,
    LLMPort,
    LLMProviderError,
    LLMRequest,
    LLMTimeoutError,
    LLMUnavailableError,
    ProposedAction,
)


class DataModality(str, Enum):
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"


class PrivacyReason(str, Enum):
    ALLOWED = "allowed"
    MEDIA_DENIED = "cloud_media_denied"
    MALFORMED_REQUEST = "malformed_request"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_FAILURE = "provider_failure"


@dataclass(frozen=True)
class CloudPrivacyPolicy:
    text_allowed: bool = True
    audio_allowed: bool = False
    image_allowed: bool = False
    video_allowed: bool = False

    def allows(self, modality: DataModality) -> bool:
        return {
            DataModality.TEXT: self.text_allowed,
            DataModality.AUDIO: self.audio_allowed,
            DataModality.IMAGE: self.image_allowed,
            DataModality.VIDEO: self.video_allowed,
        }[modality]


DEFAULT_CLOUD_PRIVACY_POLICY = CloudPrivacyPolicy()
MAX_CLOUD_TEXT_RESPONSE_LENGTH = 8_000
MAX_CLOUD_TEXT_RESPONSE_BYTES = 8_000
MAX_PROPOSALS = 8
MAX_PROPOSAL_ARGUMENT_BYTES = 2_048


@dataclass(frozen=True)
class PrivacyGatewayResult:
    allowed: bool
    reason: PrivacyReason
    completion: LLMCompletion | None = None


class PrivacyGateway:
    def __init__(self, *, llm: LLMPort, policy: CloudPrivacyPolicy) -> None:
        self._llm = llm
        self._policy = policy

    def generate(
        self,
        modality: DataModality,
        request: LLMRequest,
        *,
        timeout_seconds: float,
    ) -> PrivacyGatewayResult:
        if not isinstance(modality, DataModality) or not self._policy.allows(modality):
            return PrivacyGatewayResult(False, PrivacyReason.MEDIA_DENIED)
        if modality is not DataModality.TEXT:
            return PrivacyGatewayResult(False, PrivacyReason.MEDIA_DENIED)
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or timeout_seconds <= 0
            or not request.request_id
            or not request.conversation_session_id
            or not request.instructions
            or not request.input_text
        ):
            return PrivacyGatewayResult(False, PrivacyReason.MALFORMED_REQUEST)
        try:
            completion = self._llm.generate(
                request,
                timeout_seconds=float(timeout_seconds),
            )
        except LLMTimeoutError:
            return PrivacyGatewayResult(False, PrivacyReason.PROVIDER_TIMEOUT)
        except LLMUnavailableError:
            return PrivacyGatewayResult(False, PrivacyReason.PROVIDER_UNAVAILABLE)
        except LLMProviderError:
            return PrivacyGatewayResult(False, PrivacyReason.PROVIDER_FAILURE)
        except Exception:
            return PrivacyGatewayResult(False, PrivacyReason.PROVIDER_FAILURE)
        if (
            not isinstance(completion, LLMCompletion)
            or not completion.text.strip()
            or len(completion.text) > MAX_CLOUD_TEXT_RESPONSE_LENGTH
            or len(completion.text.encode("utf-8")) > MAX_CLOUD_TEXT_RESPONSE_BYTES
            or len(completion.proposed_actions) > MAX_PROPOSALS
            or any(
                not isinstance(proposal, ProposedAction)
                or proposal.authorization_status != "pending_policy"
                for proposal in completion.proposed_actions
            )
            or sum(
                len(key.encode("utf-8")) + len(value.encode("utf-8"))
                for proposal in completion.proposed_actions
                for key, value in proposal.arguments.items()
            ) > MAX_PROPOSAL_ARGUMENT_BYTES
        ):
            return PrivacyGatewayResult(False, PrivacyReason.PROVIDER_FAILURE)
        return PrivacyGatewayResult(True, PrivacyReason.ALLOWED, completion)

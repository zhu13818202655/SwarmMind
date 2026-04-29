"""Types for the lightweight FlyReport LM chat client."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


LMRole = Literal["system", "user", "assistant"]


class LMOutputFormat(StrEnum):
    """Optional output format hint for a chat request."""

    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"
    RAW = "raw"


class LMMessage(BaseModel):
    """A minimal chat message."""

    role: LMRole
    content: str


class LMChatRequest(BaseModel):
    """Request for a lightweight LM chat completion."""

    system_prompt: str | None = None
    user_prompt: str | None = None
    messages: list[LMMessage] | None = None
    output_format: LMOutputFormat = LMOutputFormat.TEXT
    temperature: float | None = None
    max_tokens: int | None = None
    response_format: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LMChatResponse(BaseModel):
    """Response from a lightweight LM chat completion."""

    text: str
    output_format: LMOutputFormat = LMOutputFormat.TEXT
    parsed: Any | None = None
    raw: Any | None = None
    model_name: str | None = None
    usage: dict[str, Any] | None = None


class LMError(Exception):
    """Base error for lightweight LM calls."""


class LMConfigError(LMError):
    """Raised when LM configuration is invalid."""


class LMRequestError(LMError):
    """Raised when a chat request cannot be built or sent."""


class LMTimeoutError(LMError):
    """Raised when the LM provider request times out."""


class LMProviderError(LMError):
    """Raised when the LM provider returns an error or malformed response."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
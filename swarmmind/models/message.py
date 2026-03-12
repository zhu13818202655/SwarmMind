"""Message models for SwarmMind."""

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message role enum."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(BaseModel):
    """Message model."""

    id: str = Field(..., description="Unique message identifier")
    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    tool_calls: list[dict[str, Any]] | None = Field(default=None, description="Tool calls if any")
    tool_call_id: str | None = Field(default=None, description="Tool call ID for tool responses")

    @classmethod
    def user_message(cls, content: str) -> "Message":
        """Create a user message."""
        return cls(
            id=f"msg_{datetime.utcnow().timestamp()}",
            role=MessageRole.USER,
            content=content,
        )

    @classmethod
    def assistant_message(cls, content: str, tool_calls: list[dict[str, Any]] | None = None) -> "Message":
        """Create an assistant message."""
        return cls(
            id=f"msg_{datetime.utcnow().timestamp()}",
            role=MessageRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls,
        )

    @classmethod
    def tool_message(cls, content: str, tool_call_id: str) -> "Message":
        """Create a tool message."""
        return cls(
            id=f"msg_{datetime.utcnow().timestamp()}",
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id,
        )

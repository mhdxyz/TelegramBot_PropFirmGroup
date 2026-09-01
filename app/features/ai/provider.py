"""
The AI provider contract.

Everything above this layer (ChatService, handlers) depends only on
`AIProvider` and the plain dataclasses below — never on `openai` or
`google-generativeai` types directly. That's what lets a new provider be
added by writing one file, and lets tests substitute a fake provider with
zero mocking framework magic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class AIMessage:
    role: MessageRole
    content: str


@dataclass(frozen=True)
class AIResponse:
    text: str
    provider: str
    model: str
    finish_reason: str | None = None


class AIProvider(Protocol):
    """Structural contract every AI provider implementation must satisfy.

    A `Protocol` (rather than an ABC) is used deliberately: providers don't
    need to inherit from anything, which keeps them free of coupling to our
    package beyond this one interface.
    """

    name: str

    async def generate_reply(self, messages: list[AIMessage]) -> AIResponse:
        """Send a conversation to the provider and return its reply.

        Implementations must translate provider-specific exceptions into the
        AIProviderError subtypes defined in core.exceptions — callers should
        never need to know which SDK raised what.
        """
        ...

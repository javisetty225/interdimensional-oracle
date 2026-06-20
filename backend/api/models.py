"""Pydantic request/response models with input validation."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatMessage(BaseModel):
    """A single message in the conversation history."""
    role: str = Field(..., description="Either 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request body for the /chat/stream endpoint."""
    query: str = Field(..., min_length=1, max_length=500)
    history: list[ChatMessage] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=10)
    filter_type: Literal["character", "episode", "location"] | None = Field(
        default=None,
        description="Optional entity type filter",
    )

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, v: str) -> str:
        """Strip whitespace and reject blank queries."""
        if not v.strip():
            raise ValueError("Query must not be blank or whitespace only.")
        return v.strip()


class FeedbackRequest(BaseModel):
    """Request body for the /feedback endpoint."""
    message_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1, max_length=500)
    helpful: bool
    comment: str | None = None


class BrowseRequest(BaseModel):
    """Request body for the /browse endpoint."""
    filter_type: Literal["character", "episode", "location"] | None = None
    search: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=5, le=100)
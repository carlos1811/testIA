from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    user_id: UUID
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    history_limit: int = Field(default=12, ge=1, le=50)


class ChatMessageResponse(BaseModel):
    conversation_id: UUID
    reply: str
    profile_hint: str
    profile_completeness: float

from uuid import UUID
from pydantic import BaseModel


class MatchItem(BaseModel):
    match_id: UUID
    candidate_user_id: UUID
    candidate_username: str
    compatibility_score: float
    status: str
    shared_topics: list[str]


class MatchStatusUpdate(BaseModel):
    status: str  # accepted | rejected

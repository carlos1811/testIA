from pydantic import BaseModel


class MatchItem(BaseModel):
    candidate_user_id: str
    compatibility_score: float

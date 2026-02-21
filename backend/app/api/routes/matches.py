from fastapi import APIRouter
from ...schemas.match import MatchItem

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("", response_model=list[MatchItem])
def get_matches() -> list[MatchItem]:
    # TODO: Fetch personalized matches from matching service.
    return [
        MatchItem(candidate_user_id="example-user-1", compatibility_score=81.5),
        MatchItem(candidate_user_id="example-user-2", compatibility_score=76.2),
    ]

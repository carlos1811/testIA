from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...schemas.match import MatchItem, MatchStatusUpdate
from ...services.match_service import generate_matches, get_matches, update_match_status

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("/generate", response_model=list[MatchItem])
def post_generate_matches(user_id: UUID, db: Session = Depends(get_db)) -> list[MatchItem]:
    """Genera matches para el usuario basándose en su perfil psicológico."""
    results = generate_matches(db=db, user_id=user_id)
    if not results:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron matches. El perfil psicológico puede estar incompleto.",
        )
    return [
        MatchItem(
            match_id=r.match_id,
            candidate_user_id=r.candidate_user_id,
            candidate_username=r.candidate_username,
            compatibility_score=r.compatibility_score,
            status=r.status,
            shared_topics=r.shared_topics,
        )
        for r in results
    ]


@router.get("", response_model=list[MatchItem])
def list_matches(user_id: UUID, db: Session = Depends(get_db)) -> list[MatchItem]:
    """Lista los matches ya generados para el usuario."""
    results = get_matches(db=db, user_id=user_id)
    return [
        MatchItem(
            match_id=r.match_id,
            candidate_user_id=r.candidate_user_id,
            candidate_username=r.candidate_username,
            compatibility_score=r.compatibility_score,
            status=r.status,
            shared_topics=r.shared_topics,
        )
        for r in results
    ]


@router.put("/{match_id}", response_model=MatchItem)
def put_match_status(
    match_id: UUID,
    body: MatchStatusUpdate,
    user_id: UUID,
    db: Session = Depends(get_db),
) -> MatchItem:
    """Acepta o rechaza un match."""
    try:
        match = update_match_status(db=db, match_id=match_id, user_id=user_id, new_status=body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    candidate_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id
    return MatchItem(
        match_id=match.id,
        candidate_user_id=candidate_id,
        candidate_username="",
        compatibility_score=match.compatibility_score,
        status=match.status,
        shared_topics=[],
    )

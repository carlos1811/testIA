from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...schemas.chat import ChatMessageRequest, ChatMessageResponse
from ...services.chat_service import process_chat_message

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatMessageResponse)
def post_message(payload: ChatMessageRequest, db: Session = Depends(get_db)) -> ChatMessageResponse:
    try:
        result = process_chat_message(
            db=db,
            user_id=payload.user_id,
            message_text=payload.message,
            history_limit=payload.history_limit,
            conversation_id=payload.conversation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ChatMessageResponse(
        conversation_id=result.conversation_id,
        reply=result.reply,
        profile_hint=result.profile_hint,
        profile_completeness=result.profile_completeness,
    )

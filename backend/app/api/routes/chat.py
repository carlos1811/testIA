from fastapi import APIRouter

from app.schemas.chat import ChatMessageRequest, ChatMessageResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
def post_message(payload: ChatMessageRequest) -> ChatMessageResponse:
    # TODO: Connect this endpoint to LLM service and profile extraction pipeline.
    return ChatMessageResponse(
        reply=f"I understand you said: {payload.message}",
        profile_hint="Initial psychological signals captured.",
    )

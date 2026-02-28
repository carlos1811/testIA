import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib import error, request
from uuid import UUID

from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.conversation import Conversation
from ..models.message import Message
from ..models.psychological_profile import PsychologicalProfile
from ..models.user import User


@dataclass
class ChatResult:
    conversation_id: UUID
    reply: str
    profile_hint: str
    profile_completeness: float


def process_chat_message(
    db: Session,
    user_id: UUID,
    message_text: str,
    history_limit: int,
    conversation_id: UUID | None = None,
) -> ChatResult:
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")

    conversation = _resolve_conversation(db, user_id, conversation_id)
    _save_message(db, conversation.id, "user", message_text)

    history = _get_recent_messages(db, conversation.id, history_limit)
    assistant_reply = _generate_assistant_reply(history)
    _save_message(db, conversation.id, "assistant", assistant_reply)

    profile = _get_or_create_profile(db, user_id)
    profile_hint = _update_psychological_profile(profile, message_text)

    db.commit()

    return ChatResult(
        conversation_id=conversation.id,
        reply=assistant_reply,
        profile_hint=profile_hint,
        profile_completeness=profile.completeness_score,
    )


def _resolve_conversation(db: Session, user_id: UUID, conversation_id: UUID | None) -> Conversation:
    if conversation_id:
        conversation = db.get(Conversation, conversation_id)
        if conversation and conversation.user_id == user_id:
            return conversation

    conversation = Conversation(user_id=user_id)
    db.add(conversation)
    db.flush()
    return conversation


def _save_message(db: Session, conversation_id: UUID, role: str, content: str) -> None:
    db.add(Message(conversation_id=conversation_id, role=role, content=content))
    db.flush()


def _get_recent_messages(db: Session, conversation_id: UUID, history_limit: int) -> list[dict[str, str]]:
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(history_limit)
        .all()
    )
    messages.reverse()
    return [{"role": m.role, "content": m.content} for m in messages]


def _generate_assistant_reply(history: list[dict[str, str]]) -> str:
    if not settings.openai_api_key:
        return "Gracias por compartirlo. Quiero entenderte mejor: ¿qué situación reciente te hizo sentir así?"

    payload = {
        "model": settings.openai_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres una IA empática que conversa en español para onboarding psicológico "
                    "de una app de citas. Responde breve, cálida y con una pregunta abierta."
                ),
            },
            *history,
        ],
        "temperature": 0.7,
    }

    req = request.Request(
        url="https://api.openai.com/v1/chat/completions",
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload).encode("utf-8"),
    )

    try:
        with request.urlopen(req, timeout=settings.openai_timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except (error.URLError, error.HTTPError, KeyError, IndexError, json.JSONDecodeError):
        return "Te leo con atención. ¿Qué valoras más cuando conectas con alguien?"


def _get_or_create_profile(db: Session, user_id: UUID) -> PsychologicalProfile:
    profile = db.query(PsychologicalProfile).filter(PsychologicalProfile.user_id == user_id).first()
    if profile:
        return profile

    profile = PsychologicalProfile(user_id=user_id, perfil_json={}, completeness_score=0.0)
    db.add(profile)
    db.flush()
    return profile


def _update_psychological_profile(profile: PsychologicalProfile, user_message: str) -> str:
    insights = profile.perfil_json or {}
    lower = user_message.lower()

    keywords = {
        "emociones": ["siento", "emocion", "ansiedad", "feliz", "triste", "miedo"],
        "valores": ["valoro", "respeto", "confianza", "lealtad", "honestidad"],
        "vinculo": ["pareja", "relación", "amor", "conectar", "compromiso"],
        "autoconocimiento": ["aprendí", "terapia", "cambié", "crecer", "mejorar"],
    }

    detected = [topic for topic, terms in keywords.items() if any(term in lower for term in terms)]
    if not detected:
        detected = ["narrativa_general"]

    signal_log = insights.get("signal_log", [])
    signal_log.append({
        "message_excerpt": user_message[:220],
        "topics": detected,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    insights["signal_log"] = signal_log[-30:]

    topic_counts = insights.get("topic_counts", {})
    for topic in detected:
        topic_counts[topic] = int(topic_counts.get(topic, 0)) + 1
    insights["topic_counts"] = topic_counts

    sentence_count = len([p for p in re.split(r"[.!?]+", user_message) if p.strip()])
    avg_len = sum(len(s) for s in re.findall(r"\w+", user_message)) / max(len(re.findall(r"\w+", user_message)), 1)
    style = insights.get("writing_style", {})
    style["avg_sentence_count"] = round((style.get("avg_sentence_count", 0) + sentence_count) / 2, 2)
    style["avg_word_length"] = round((style.get("avg_word_length", 0) + avg_len) / 2, 2)
    insights["writing_style"] = style

    known_topics = len(topic_counts)
    profile.completeness_score = min(100.0, round(profile.completeness_score + 4 + known_topics * 0.5, 2))
    profile.perfil_json = insights

    top_topics = sorted(topic_counts.items(), key=lambda item: item[1], reverse=True)[:2]
    readable_topics = ", ".join(topic for topic, _ in top_topics)
    if readable_topics:
        return f"Se fortalecieron señales en: {readable_topics}."
    return "Se registraron nuevas señales conversacionales."

import json
import re
import time
from dataclasses import dataclass
from typing import Callable
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

    clean = assistant_reply.strip()
    if clean.startswith("```"):
        lines = clean.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        clean = "\n".join(lines).strip()

    try:
        data = json.loads(clean)
        respuesta = str(data.get("respuesta", "")).strip()
        resultado_raw = data.get("resultado", [])
    except json.JSONDecodeError:
        respuesta = assistant_reply
        resultado_raw = []

    resultado_items = _normalize_resultado_items(resultado_raw)
    resultado_final = " ".join(resultado_items)

    _save_message(db, conversation.id, "assistant", resultado_final )

    profile = _get_or_create_profile(db, user_id)
    profile_hint = _update_psychological_profile(profile, resultado_final)

    db.commit()

    return ChatResult(
        conversation_id=conversation.id,
        reply=respuesta,
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
    provider_name, request_fn = _llm_request_factory()
    if request_fn is None:
        return "Gracias por compartirlo. Quiero entenderte mejor: ¿qué situación reciente te hizo sentir así?"

    payload = _build_chat_payload(history, provider_name)
    assistant_reply = request_fn(payload)
    if assistant_reply:
        return assistant_reply

    return "Te leo con atención. ¿Qué valoras más cuando conectas con alguien?"


def _build_chat_payload(history: list[dict[str, str]], provider: str) -> dict[str, object]:
    payload = {
        "model": settings.openai_model if provider == "openai" else settings.mistral_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres una IA empática que conversa en español para onboarding psicológico "
                    "de una app de citas. " 
                    "Responde con un fichero JSON que contenga que contenga dos campos: "
                    "resultado y respuesta "
                    "En resultado muestra un array con algun valor dentro de las caracteristicas mostradas de emociones, valores, vinculo y autoconocimiento "
                    "Ejemplo resultado: [ansiedad, confianza, amor, terapia] "
                    "Posibles valores para cada parametro: "
                    "emociones: [siento, emocion, ansiedad, feliz, triste, miedo] "
                    "valores: [valoro, respeto, confianza, lealtad, honestidad] "
                    "vinculo: [pareja, relación, amor, conectar, compromiso] "
                    "autoconocimiento: [aprendí, terapia, cambié, crecer, mejorar] "
                    "En respuesta responde a lo que la persona te dice con una pregunta abierta que invite a compartir "
                    "más sobre lo que la persona siente o valora, para ir creando un perfil psicológico. "
                    " Los textos posteriores son mensajes del historial de la conversación, con el rol de user o "
                    "assistant. Analízalos para identificar señales psicológicas y generar una respuesta empática y personalizada. "
                ),
            },
            *history,
        ],
        "temperature": 0.7,
    }
    return payload


def _normalize_resultado_items(resultado_raw: object) -> list[str]:
    if isinstance(resultado_raw, list):
        return [str(item).strip() for item in resultado_raw if str(item).strip()]

    if isinstance(resultado_raw, str):
        value = resultado_raw.strip()
        if not value:
            return []

        if value.startswith("[") and value.endswith("]"):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]

        return [part.strip() for part in re.split(r"[,;\s]+", value) if part.strip()]

    return []


def _llm_request_factory() -> tuple[str, Callable[[dict[str, object]], str | None] | None]:
    provider = settings.llm_provider.lower().strip()

    providers: dict[str, Callable[[dict[str, object]], str | None] | None] = {
        "openai": _request_openai_reply if settings.openai_api_key else None,
        "mistral": _request_mistral_reply if settings.mistral_api_key else None,
    }

    if provider in providers and providers[provider] is not None:
        return provider, providers[provider]

    if providers["openai"] is not None:
        return "openai", providers["openai"]

    if providers["mistral"] is not None:
        return "mistral", providers["mistral"]

    return provider, None


def _request_openai_reply(payload: dict[str, object]) -> str | None:
    max_retries = 3
    backoff_seconds = 0.75

    for attempt in range(max_retries):
        req = request.Request(
            url="https://api.openai.com/v1/chat/completions",
            method="POST",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
                "Connection": "close",
            },
            data=json.dumps(payload).encode("utf-8"),
        )

        try:
            with request.urlopen(req, timeout=settings.openai_timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore").lower()
            is_retryable_code = exc.code in {429, 500, 502, 503, 504}
            is_connection_pressure = "too many connections" in body

            if attempt < max_retries - 1 and (is_retryable_code or is_connection_pressure):
                time.sleep(backoff_seconds * (attempt + 1))
                continue
            return None
        except (error.URLError, KeyError, IndexError, json.JSONDecodeError):
            if attempt < max_retries - 1:
                time.sleep(backoff_seconds * (attempt + 1))
                continue
            return None

    return None


def _request_mistral_reply(payload: dict[str, object]) -> str | None:
    max_retries = 3
    backoff_seconds = 0.75

    for attempt in range(max_retries):
        req = request.Request(
            url="https://api.mistral.ai/v1/chat/completions",
            method="POST",
            headers={
                "Authorization": f"Bearer {settings.mistral_api_key}",
                "Content-Type": "application/json",
                "Connection": "close",
            },
            data=json.dumps(payload).encode("utf-8"),
        )

        try:
            with request.urlopen(req, timeout=settings.mistral_timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore").lower()
            is_retryable_code = exc.code in {429, 500, 502, 503, 504}
            is_connection_pressure = "too many connections" in body

            if attempt < max_retries - 1 and (is_retryable_code or is_connection_pressure):
                time.sleep(backoff_seconds * (attempt + 1))
                continue
            return None
        except (error.URLError, KeyError, IndexError, json.JSONDecodeError):
            if attempt < max_retries - 1:
                time.sleep(backoff_seconds * (attempt + 1))
                continue
            return None

    return None


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

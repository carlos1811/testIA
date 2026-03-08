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

    profile = _get_or_create_profile(db, user_id)
    profile_hint = _update_psychological_profile(profile, message_text)

    history = _get_recent_messages(db, conversation.id, history_limit)
    assistant_reply = _generate_assistant_reply(history, profile)
    _save_message(db, conversation.id, "assistant", assistant_reply)

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


def _generate_assistant_reply(history: list[dict[str, str]], profile: PsychologicalProfile) -> str:
    provider_name, request_fn = _llm_request_factory()
    profile_data = profile.perfil_json or {}
    followup_focus = _pending_profile_dimensions(profile_data)

    if request_fn is None:
        return _fallback_dating_agent_question(followup_focus)

    payload = _build_chat_payload(history, provider_name, profile_data, followup_focus)
    assistant_reply = request_fn(payload)
    if assistant_reply:
        return assistant_reply

    return _fallback_dating_agent_question(followup_focus)


def _build_chat_payload(
    history: list[dict[str, str]],
    provider: str,
    profile_data: dict[str, object],
    followup_focus: list[str],
) -> dict[str, object]:
    profile_summary = _compact_profile_summary(profile_data)
    focus_text = ", ".join(followup_focus) if followup_focus else "profundizar en emociones y compatibilidad"

    payload = {
        "model": settings.openai_model if provider == "openai" else settings.mistral_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres un agente de citas y perfilado psicológico en español. Tu objetivo es conocer "
                    "a la persona para recomendarle una pareja compatible. Responde con calidez, valida "
                    "lo que comparte y SIEMPRE termina con una única pregunta abierta y concreta. "
                    f"Áreas a explorar ahora: {focus_text}. "
                    f"Resumen actual del perfil: {profile_summary}."
                ),
            },
            *history,
        ],
        "temperature": 0.7,
    }
    return payload


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
    if not insights:
        insights = {
            "version": "2.0",
            "signal_log": [],
            "topic_counts": {},
            "writing_style": {"avg_word_length": 0.0, "avg_sentence_count": 0.0, "samples": 0},
            "psychological_profile": {
                "personality_traits": {
                    "apertura": 0.5,
                    "estabilidad_emocional": 0.5,
                    "sociabilidad": 0.5,
                    "empatia": 0.5,
                    "responsabilidad_afectiva": 0.5,
                },
                "relationship_preferences": {
                    "valores": [],
                    "actividades": [],
                    "dealbreakers": [],
                    "tipo_de_relacion": [],
                },
                "emotional_patterns": {"emociones_dominantes": [], "estresores": []},
                "communication": {"estilo": [], "necesidades": []},
                "goals": {"corto_plazo": [], "largo_plazo": []},
            },
            "next_questions": [],
        }

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

    psychological_profile = insights.get("psychological_profile", {})
    traits = psychological_profile.get("personality_traits", {})
    rel_preferences = psychological_profile.get("relationship_preferences", {})
    emotions = psychological_profile.get("emotional_patterns", {})
    communication = psychological_profile.get("communication", {})
    goals = psychological_profile.get("goals", {})

    _update_numeric_trait(traits, "apertura", lower, ["me gusta", "nuevo", "aprender", "viajar", "explorar"], 0.05)
    _update_numeric_trait(traits, "sociabilidad", lower, ["amigos", "salir", "social", "plan", "gente"], 0.04)
    _update_numeric_trait(
        traits,
        "estabilidad_emocional",
        lower,
        ["calma", "equilibrio", "terapia", "gestionar", "ansiedad", "estrés"],
        0.03,
    )
    _update_numeric_trait(traits, "empatia", lower, ["escuchar", "comprender", "empat", "cuidar"], 0.04)
    _update_numeric_trait(
        traits,
        "responsabilidad_afectiva",
        lower,
        ["compromiso", "honestidad", "lealtad", "comunicación", "respeto"],
        0.05,
    )

    _append_detected_values(rel_preferences, "valores", lower, ["honestidad", "respeto", "confianza", "lealtad", "humor"])
    _append_detected_values(rel_preferences, "actividades", lower, ["senderismo", "pádel", "padel", "viajar", "cine", "deporte", "cocinar"])
    _append_detected_values(rel_preferences, "dealbreakers", lower, ["mentira", "toxic", "infidelidad", "falta de respeto", "frialdad"])
    _append_detected_values(rel_preferences, "tipo_de_relacion", lower, ["estable", "seria", "casual", "largo plazo", "matrimonio"])

    _append_detected_values(emotions, "emociones_dominantes", lower, ["feliz", "triste", "ansiedad", "miedo", "ilusión", "frustración"])
    _append_detected_values(emotions, "estresores", lower, ["trabajo", "soledad", "rechazo", "incertidumbre", "celos"])

    _append_detected_values(communication, "estilo", lower, ["directo", "claro", "afectuoso", "tranquilo", "intenso"])
    _append_detected_values(communication, "necesidades", lower, ["espacio", "tiempo de calidad", "atención", "validación", "comunicación"])

    _append_goal_if_present(goals, "corto_plazo", user_message)
    _append_goal_if_present(goals, "largo_plazo", user_message, long_term=True)

    psychological_profile["personality_traits"] = traits
    psychological_profile["relationship_preferences"] = rel_preferences
    psychological_profile["emotional_patterns"] = emotions
    psychological_profile["communication"] = communication
    psychological_profile["goals"] = goals
    insights["psychological_profile"] = psychological_profile

    sentence_count = len([p for p in re.split(r"[.!?]+", user_message) if p.strip()])
    words = re.findall(r"\w+", user_message)
    avg_len = sum(len(s) for s in words) / max(len(words), 1)
    style = insights.get("writing_style", {})
    samples = int(style.get("samples", 0))
    style["avg_sentence_count"] = round((style.get("avg_sentence_count", 0) * samples + sentence_count) / (samples + 1), 2)
    style["avg_word_length"] = round((style.get("avg_word_length", 0) * samples + avg_len) / (samples + 1), 2)
    style["samples"] = samples + 1
    insights["writing_style"] = style

    next_questions = _pending_profile_dimensions(insights)
    insights["next_questions"] = next_questions

    profile.completeness_score = _compute_profile_completeness(insights)
    profile.perfil_json = insights

    top_topics = sorted(topic_counts.items(), key=lambda item: item[1], reverse=True)[:2]
    readable_topics = ", ".join(topic for topic, _ in top_topics)
    if readable_topics:
        return f"Perfil actualizado en: {readable_topics}. Próximo foco: {', '.join(next_questions[:2]) or 'profundizar vínculo'}"
    return "Perfil actualizado con nuevas señales conversacionales."


def _update_numeric_trait(traits: dict[str, float], trait: str, text: str, terms: list[str], delta: float) -> None:
    base = float(traits.get(trait, 0.5))
    matches = sum(1 for term in terms if term in text)
    if matches:
        traits[trait] = round(min(1.0, base + delta * matches), 2)


def _append_detected_values(container: dict[str, list[str]], key: str, text: str, terms: list[str]) -> None:
    values = container.get(key, [])
    for term in terms:
        if term in text and term not in values:
            values.append(term)
    container[key] = values


def _append_goal_if_present(goals: dict[str, list[str]], key: str, message: str, long_term: bool = False) -> None:
    lower = message.lower()
    triggers = ["quiero", "me gustaría", "mi objetivo", "busco", "a futuro"]
    if not any(trigger in lower for trigger in triggers):
        return

    if long_term and not any(term in lower for term in ["años", "familia", "futuro", "estabilidad"]):
        return

    snippets = goals.get(key, [])
    excerpt = message.strip()[:120]
    if excerpt and excerpt not in snippets:
        snippets.append(excerpt)
    goals[key] = snippets[-5:]


def _pending_profile_dimensions(insights: dict[str, object]) -> list[str]:
    profile = insights.get("psychological_profile", {}) if isinstance(insights, dict) else {}
    if not isinstance(profile, dict):
        return []

    rel = profile.get("relationship_preferences", {}) if isinstance(profile.get("relationship_preferences"), dict) else {}
    emo = profile.get("emotional_patterns", {}) if isinstance(profile.get("emotional_patterns"), dict) else {}
    comm = profile.get("communication", {}) if isinstance(profile.get("communication"), dict) else {}
    goals = profile.get("goals", {}) if isinstance(profile.get("goals"), dict) else {}

    pending: list[str] = []
    if not rel.get("tipo_de_relacion"):
        pending.append("tipo de relación que busca")
    if not rel.get("valores"):
        pending.append("valores en pareja")
    if not rel.get("dealbreakers"):
        pending.append("límites o dealbreakers")
    if not emo.get("emociones_dominantes"):
        pending.append("emociones frecuentes")
    if not comm.get("necesidades"):
        pending.append("necesidades de comunicación")
    if not goals.get("largo_plazo"):
        pending.append("objetivos de vida en pareja")
    return pending


def _compute_profile_completeness(insights: dict[str, object]) -> float:
    profile = insights.get("psychological_profile", {}) if isinstance(insights, dict) else {}
    if not isinstance(profile, dict):
        return 0.0

    checks = [
        bool((profile.get("relationship_preferences") or {}).get("valores")),
        bool((profile.get("relationship_preferences") or {}).get("tipo_de_relacion")),
        bool((profile.get("relationship_preferences") or {}).get("dealbreakers")),
        bool((profile.get("emotional_patterns") or {}).get("emociones_dominantes")),
        bool((profile.get("communication") or {}).get("necesidades")),
        bool((profile.get("goals") or {}).get("largo_plazo")),
        bool((insights.get("topic_counts") or {})),
        int((insights.get("writing_style") or {}).get("samples", 0)) >= 3,
    ]
    return round(100 * (sum(checks) / len(checks)), 2)


def _compact_profile_summary(profile_data: dict[str, object]) -> str:
    if not profile_data:
        return "perfil inicial vacío"

    profile = profile_data.get("psychological_profile", {})
    if not isinstance(profile, dict):
        return "perfil parcial"

    preferences = profile.get("relationship_preferences", {})
    values = (preferences.get("valores") or [])[:3] if isinstance(preferences, dict) else []
    relation = (preferences.get("tipo_de_relacion") or [])[:2] if isinstance(preferences, dict) else []
    activities = (preferences.get("actividades") or [])[:2] if isinstance(preferences, dict) else []
    return f"valores={values or 'sin datos'}, relación={relation or 'sin datos'}, actividades={activities or 'sin datos'}"


def _fallback_dating_agent_question(followup_focus: list[str]) -> str:
    if followup_focus:
        return (
            "Gracias por abrirte conmigo. Para conocerte mejor y buscarte una pareja compatible, "
            f"¿cómo describirías {followup_focus[0]}?"
        )
    return (
        "Gracias por compartirlo. Para afinar tu perfil psicológico y de compatibilidad, "
        "¿qué tipo de relación te haría sentir más en paz y con ilusión?"
    )

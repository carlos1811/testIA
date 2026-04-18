from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.match import Match
from ..models.psychological_profile import PsychologicalProfile
from ..models.user import User


@dataclass
class MatchResult:
    match_id: UUID
    candidate_user_id: UUID
    candidate_username: str
    compatibility_score: float
    status: str
    shared_topics: list[str]


def generate_matches(db: Session, user_id: UUID, limit: int = 10) -> list[MatchResult]:
    """Genera y persiste matches para el usuario dado basándose en topic_counts del perfil psicológico."""

    my_profile = db.query(PsychologicalProfile).filter(PsychologicalProfile.user_id == user_id).first()
    if my_profile is None or not my_profile.perfil_json:
        return []

    my_topics: dict[str, int] = my_profile.perfil_json.get("topic_counts", {})
    if not my_topics:
        return []

    # Obtener todos los perfiles excepto el propio
    other_profiles = (
        db.query(PsychologicalProfile)
        .filter(PsychologicalProfile.user_id != user_id)
        .all()
    )

    scored: list[tuple[PsychologicalProfile, float, list[str]]] = []
    for profile in other_profiles:
        if not profile.perfil_json:
            continue
        other_topics: dict[str, int] = profile.perfil_json.get("topic_counts", {})
        if not other_topics:
            continue

        score, shared = _calculate_score(my_topics, other_topics)
        if score > 0:
            scored.append((profile, score, shared))

    # Ordenar por score descendente y tomar los mejores
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:limit]

    results: list[MatchResult] = []
    for profile, score, shared in top:
        # Buscar si ya existe el match
        existing = (
            db.query(Match)
            .filter(
                (
                    (Match.user_a_id == user_id) & (Match.user_b_id == profile.user_id)
                ) | (
                    (Match.user_a_id == profile.user_id) & (Match.user_b_id == user_id)
                )
            )
            .first()
        )

        if existing:
            existing.compatibility_score = score
            match = existing
        else:
            match = Match(
                user_a_id=user_id,
                user_b_id=profile.user_id,
                compatibility_score=score,
                status="suggested",
            )
            db.add(match)
            db.flush()

        candidate_user = db.get(User, profile.user_id)
        results.append(
            MatchResult(
                match_id=match.id,
                candidate_user_id=profile.user_id,
                candidate_username=candidate_user.username if candidate_user else "unknown",
                compatibility_score=round(score, 2),
                status=match.status,
                shared_topics=shared,
            )
        )

    db.commit()
    return results


def get_matches(db: Session, user_id: UUID) -> list[MatchResult]:
    """Devuelve los matches ya generados para el usuario."""
    matches = (
        db.query(Match)
        .filter((Match.user_a_id == user_id) | (Match.user_b_id == user_id))
        .order_by(Match.compatibility_score.desc())
        .all()
    )

    results: list[MatchResult] = []
    for match in matches:
        candidate_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id
        candidate_user = db.get(User, candidate_id)

        # Calcular topics compartidos
        my_profile = db.query(PsychologicalProfile).filter(PsychologicalProfile.user_id == user_id).first()
        candidate_profile = db.query(PsychologicalProfile).filter(PsychologicalProfile.user_id == candidate_id).first()

        shared: list[str] = []
        if my_profile and candidate_profile:
            my_topics = set((my_profile.perfil_json or {}).get("topic_counts", {}).keys())
            candidate_topics = set((candidate_profile.perfil_json or {}).get("topic_counts", {}).keys())
            shared = list(my_topics & candidate_topics)

        results.append(
            MatchResult(
                match_id=match.id,
                candidate_user_id=candidate_id,
                candidate_username=candidate_user.username if candidate_user else "unknown",
                compatibility_score=round(match.compatibility_score, 2),
                status=match.status,
                shared_topics=shared,
            )
        )

    return results


def update_match_status(db: Session, match_id: UUID, user_id: UUID, new_status: str) -> Match:
    """Actualiza el estado de un match (accepted / rejected)."""
    match = db.get(Match, match_id)
    if match is None:
        raise ValueError("Match not found")
    if match.user_a_id != user_id and match.user_b_id != user_id:
        raise PermissionError("Match does not belong to this user")

    allowed = {"accepted", "rejected", "suggested"}
    if new_status not in allowed:
        raise ValueError(f"Status must be one of {allowed}")

    match.status = new_status
    db.commit()
    db.refresh(match)
    return match


def _calculate_score(topics_a: dict[str, int], topics_b: dict[str, int]) -> tuple[float, list[str]]:
    """Calcula compatibilidad usando índice Jaccard ponderado por frecuencia."""
    keys_a = set(topics_a.keys())
    keys_b = set(topics_b.keys())

    shared_keys = keys_a & keys_b
    all_keys = keys_a | keys_b

    if not all_keys:
        return 0.0, []

    # Jaccard básico
    jaccard = len(shared_keys) / len(all_keys)

    # Bonus por frecuencia compartida
    frequency_bonus = sum(
        min(topics_a[k], topics_b[k]) / max(topics_a[k], topics_b[k])
        for k in shared_keys
    ) / len(all_keys)

    score = (jaccard + frequency_bonus) / 2 * 100
    return round(score, 2), list(shared_keys)


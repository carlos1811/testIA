import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from ..db.session import Base


class PsychologicalProfile(Base):
    __tablename__ = "psychological_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    writing_style_score: Mapped[float] = mapped_column(Float, default=0)
    empathy_score: Mapped[float] = mapped_column(Float, default=0)
    openness_score: Mapped[float] = mapped_column(Float, default=0)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

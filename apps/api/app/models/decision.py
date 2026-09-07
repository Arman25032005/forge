import uuid

from sqlalchemy import JSON, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enterprise import TenantScopedMixin


class Decision(TenantScopedMixin, Base):
    __tablename__ = "decisions"

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    conclusion: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    # list[{"step_index": int, "summary": str}] — which recorded agent
    # steps the conclusion is actually grounded in.
    evidence: Mapped[list] = mapped_column(JSON, nullable=False)
    recommended_actions: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")

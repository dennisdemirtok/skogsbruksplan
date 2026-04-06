import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PlanStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class Certification(str, enum.Enum):
    none = "none"
    PEFC = "PEFC"
    FSC = "FSC"
    both = "both"


class ForestPlan(Base):
    __tablename__ = "forest_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    share_token: Mapped[str | None] = mapped_column(
        Text, nullable=True, unique=True, index=True
    )
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    certification: Mapped[str] = mapped_column(
        String(10), nullable=False, default="none"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    property = relationship("Property", back_populates="plans")
    created_by_user = relationship("User", back_populates="created_plans")

    def __repr__(self) -> str:
        return f"<ForestPlan {self.name} v{self.version}>"

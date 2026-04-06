import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    designation: Mapped[str] = mapped_column(
        Text, nullable=False, index=True, comment="e.g. Sollefteå Myckelåsen 1:1"
    )
    municipality: Mapped[str] = mapped_column(String(255), nullable=True)
    county: Mapped[str] = mapped_column(String(255), nullable=True)
    geometry = mapped_column(
        Text, nullable=True, comment="GeoJSON geometry (MULTIPOLYGON, SRID 3006)"
    )
    total_area_ha: Mapped[float | None] = mapped_column(Float, nullable=True)
    productive_forest_ha: Mapped[float | None] = mapped_column(Float, nullable=True)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
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

    owner = relationship(
        "User", back_populates="owned_properties", foreign_keys=[owner_id]
    )
    created_by_user = relationship(
        "User", back_populates="created_properties", foreign_keys=[created_by]
    )
    stands = relationship(
        "Stand", back_populates="property", cascade="all, delete-orphan"
    )
    plans = relationship(
        "ForestPlan", back_populates="property", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Property {self.designation}>"

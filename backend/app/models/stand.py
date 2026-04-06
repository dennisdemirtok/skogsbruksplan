import enum
import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TargetClass(str, enum.Enum):
    PG = "PG"
    NS = "NS"
    NO = "NO"
    PF = "PF"


class ProposedAction(str, enum.Enum):
    slutavverkning = "slutavverkning"
    gallring = "gallring"
    rojning = "rojning"
    foryngring = "foryngring"
    ingen = "ingen"


class DataSource(str, enum.Enum):
    auto = "auto"
    field = "field"
    manual = "manual"


class Stand(Base):
    __tablename__ = "stands"

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
    stand_number: Mapped[int] = mapped_column(Integer, nullable=False)
    geometry = mapped_column(
        Geometry(geometry_type="POLYGON", srid=3006, spatial_index=True),
        nullable=True,
    )
    area_ha: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Forest data
    volume_m3_per_ha: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_volume_m3: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_height_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    basal_area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_diameter_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    age_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    site_index: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Bonitet SI H100"
    )

    # Species distribution (percentages, should sum to ~100)
    pine_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=0, comment="Tall %"
    )
    spruce_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=0, comment="Gran %"
    )
    deciduous_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=0, comment="Löv %"
    )
    contorta_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=0, comment="Contorta %"
    )

    # Management classification
    target_class: Mapped[str | None] = mapped_column(
        String(5), nullable=True, default="PG"
    )
    proposed_action: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default="ingen"
    )
    action_urgency: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="1-5, 1=most urgent"
    )
    action_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Economics
    timber_volume_m3: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Timmer m3fub"
    )
    pulpwood_volume_m3: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Massaved m3fub"
    )
    gross_value_sek: Mapped[float | None] = mapped_column(Float, nullable=True)
    harvesting_cost_sek: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_value_sek: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Bark beetle risk
    bark_beetle_risk: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Risk 0.0-1.0"
    )

    # Meta
    data_source: Mapped[str | None] = mapped_column(
        String(10), nullable=True, default="auto"
    )
    field_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

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

    property = relationship("Property", back_populates="stands")
    field_data = relationship(
        "FieldData", back_populates="stand", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Stand {self.stand_number} property={self.property_id}>"

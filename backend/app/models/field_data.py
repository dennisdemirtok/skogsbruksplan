import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SoilMoisture(str, enum.Enum):
    torr = "torr"
    frisk = "frisk"
    fuktig = "fuktig"
    blot = "blot"


class FieldData(Base):
    __tablename__ = "field_data"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    stand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stands.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recorded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    relascope_value: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Relaskoptal m2/ha"
    )
    sample_trees: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment='[{"species": "tall", "dbh_cm": 25, "height_m": 18}, ...]',
    )
    soil_moisture: Mapped[SoilMoisture | None] = mapped_column(
        nullable=True,
    )
    nature_values: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment='{"dead_wood": true, "red_listed_species": ["..."], "key_biotope": false}',
    )
    photos: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of S3 keys for uploaded photos",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    stand = relationship("Stand", back_populates="field_data")
    recorder = relationship("User", back_populates="field_data_entries")

    def __repr__(self) -> str:
        return f"<FieldData {self.id} stand={self.stand_id}>"

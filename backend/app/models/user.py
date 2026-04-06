import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserRole(str, enum.Enum):
    consultant = "consultant"
    owner = "owner"
    reader = "reader"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="owner",
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
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

    owned_properties = relationship(
        "Property", back_populates="owner", foreign_keys="Property.owner_id"
    )
    created_properties = relationship(
        "Property", back_populates="created_by_user", foreign_keys="Property.created_by"
    )
    field_data_entries = relationship("FieldData", back_populates="recorder")
    created_plans = relationship("ForestPlan", back_populates="created_by_user")

    def __repr__(self) -> str:
        return f"<User {self.email}>"

import uuid
from typing import List, Optional

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import MemberStatus
from app.models.mixins import TimestampMixin


class Member(TimestampMixin, Base):
    __tablename__ = "members"
    __table_args__ = (
        UniqueConstraint("cooperative_id", "code", name="uq_members_cooperative_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    specialty: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[MemberStatus] = mapped_column(
        Enum(MemberStatus, native_enum=False),
        nullable=False,
        default=MemberStatus.ACTIVE,
    )

    cooperative: Mapped["Cooperative"] = relationship(back_populates="members")
    fields: Mapped[List["Field"]] = relationship(back_populates="member", cascade="all, delete-orphan")
    inputs: Mapped[List["Input"]] = relationship(back_populates="member")

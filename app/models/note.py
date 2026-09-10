from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.category import Category
    from app.models.tag import Tag


class Note(Base, TimestampMixin):
    __tablename__ = "notes"
    __table_args__ = (
        Index("idx_notes_user_status", "user_id", "is_deleted", "is_archived", "is_pinned"),
        Index("idx_notes_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # Status Flags
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notes")
    category: Mapped[Optional["Category"]] = relationship(
        "Category", back_populates="notes", lazy="selectin"
    )
    tags: Mapped[List["Tag"]] = relationship(
        "Tag", secondary="note_tags", back_populates="notes", lazy="selectin"
    )

    @property
    def formatted_deleted_at(self) -> str:
        if not self.deleted_at:
            return ""
        hour = self.deleted_at.strftime("%I").lstrip("0") or "0"
        return f"{self.deleted_at.strftime('%d %b %Y')}, {hour}:{self.deleted_at.strftime('%M %p')}"

    def __repr__(self) -> str:
        return f"<Note id={self.id} title={self.title[:20]!r} user_id={self.user_id}>"

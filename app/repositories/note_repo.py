from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note
from app.repositories.base import BaseRepository


class NoteRepository(BaseRepository[Note]):
    def __init__(self, session: AsyncSession):
        super().__init__(Note, session)

    async def get_by_id(self, note_id: int, user_id: int) -> Optional[Note]:
        """
        Fetch a specific note strictly verifying ownership and active status.
        Conceptual SQL: WHERE note.id = :note_id AND note.user_id = :user_id AND note.is_deleted IS FALSE
        """
        stmt = select(Note).where(
            Note.id == note_id,
            Note.user_id == user_id,
            Note.is_deleted.is_(False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_user(self, user_id: int) -> List[Note]:
        """
        List all active notes for the current user, ordered by recently updated.
        Conceptual SQL: WHERE note.user_id = :user_id AND note.is_deleted IS FALSE ORDER BY note.updated_at DESC
        """
        stmt = (
            select(Note)
            .where(Note.user_id == user_id, Note.is_deleted.is_(False))
            .order_by(Note.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, user_id: int, title: str, content: str = "") -> Note:
        """Create a new user-owned note."""
        note = Note(
            user_id=user_id,
            title=title.strip(),
            content=content.strip() if content else "",
            is_deleted=False,
            deleted_at=None
        )
        self.session.add(note)
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def update(self, note: Note, title: str, content: str = "") -> Note:
        """Update an existing note's title and content."""
        note.title = title.strip()
        note.content = content.strip() if content else ""
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def update_title(self, note: Note, title: str) -> Note:
        """Update only the title of an existing note."""
        note.title = title.strip()
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def update_content(self, note: Note, content: str = "") -> Note:
        """Update only the content of an existing note."""
        note.content = content.strip() if content else ""
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def append_content(self, note: Note, text: str, separator: str = "\n\n---\n\n") -> Note:
        """Append text to the existing note content with a separator."""
        cleaned_text = text.strip()
        if note.content and note.content.strip():
            note.content = f"{note.content.rstrip()}{separator}{cleaned_text}"
        else:
            note.content = cleaned_text
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def soft_delete(self, note: Note) -> Note:
        """
        Soft delete a note by setting is_deleted=True and timestamping deleted_at.
        Excludes it from normal note listings.
        """
        note.is_deleted = True
        note.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(note)
        return note

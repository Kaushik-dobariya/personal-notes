from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note
from app.repositories.note_repo import NoteRepository
from app.schemas.note import NoteCreate, NoteUpdate


class NoteService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.note_repo = NoteRepository(session)

    async def list_user_notes(self, user_id: int) -> List[Note]:
        """Fetch all non-deleted notes belonging to the current user."""
        return await self.note_repo.get_active_by_user(user_id)

    async def get_user_note(self, note_id: int, user_id: int) -> Optional[Note]:
        """
        Fetch a single note strictly verifying ownership.
        Returns None if note doesn't exist or belongs to another user.
        """
        return await self.note_repo.get_by_id(note_id, user_id)

    async def create_user_note(self, user_id: int, data: NoteCreate) -> Note:
        """Create a new note owned by current user."""
        return await self.note_repo.create(
            user_id=user_id,
            title=data.title,
            content=data.content
        )

    async def update_user_note(self, note_id: int, user_id: int, data: NoteUpdate) -> Note:
        """
        Update an existing note strictly checking ownership.
        Raises ValueError if note is not found or belongs to another user.
        """
        note = await self.note_repo.get_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found.")
        return await self.note_repo.update(note, title=data.title, content=data.content)

    async def update_note_title(self, note_id: int, user_id: int, title: str) -> Note:
        """
        Update title of an existing note strictly checking ownership.
        Raises ValueError if note is not found or belongs to another user.
        """
        note = await self.note_repo.get_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found.")
        return await self.note_repo.update_title(note, title=title)

    async def update_note_content(self, note_id: int, user_id: int, content: str) -> Note:
        """
        Update content of an existing note strictly checking ownership.
        Raises ValueError if note is not found or belongs to another user.
        """
        note = await self.note_repo.get_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found.")
        return await self.note_repo.update_content(note, content=content)

    async def append_note_content(self, note_id: int, user_id: int, text: str) -> Note:
        """
        Append text to existing note content strictly checking ownership.
        Raises ValueError if note is not found or belongs to another user.
        """
        note = await self.note_repo.get_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found.")
        return await self.note_repo.append_content(note, text=text)

    async def soft_delete_user_note(self, note_id: int, user_id: int) -> Note:
        """
        Soft delete a note owned by current user.
        Sets is_deleted=True and deleted_at timestamp.
        Raises ValueError if note is not found or belongs to another user.
        """
        note = await self.note_repo.get_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found.")
        return await self.note_repo.soft_delete(note)

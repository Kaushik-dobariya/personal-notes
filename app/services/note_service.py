from typing import List, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note
from app.repositories.note_repo import NoteRepository
from app.schemas.note import NoteCreate, NoteUpdate


class NoteService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.note_repo = NoteRepository(session)

    async def list_user_notes(
        self,
        user_id: int,
        category_id: Optional[int] = None,
        tag_id: Optional[int] = None
    ) -> List[Note]:
        """Fetch all non-deleted notes belonging to the current user, optionally filtered."""
        return await self.note_repo.get_active_by_user(
            user_id, category_id=category_id, tag_id=tag_id
        )

    async def get_user_note(self, note_id: int, user_id: int) -> Optional[Note]:
        """
        Fetch a single note strictly verifying ownership.
        Returns None if note doesn't exist or belongs to another user.
        """
        return await self.note_repo.get_by_id(note_id, user_id)

    async def create_user_note(
        self,
        user_id: int,
        data: NoteCreate,
        category_id: Optional[int] = None,
        tag_names: Optional[List[str]] = None
    ) -> Note:
        """Create a new note owned by current user with optional category and tags."""
        if category_id is not None:
            from app.repositories.category_repo import CategoryRepository
            cat_repo = CategoryRepository(self.session)
            cat = await cat_repo.get_by_id(category_id, user_id)
            if not cat:
                raise ValueError("Category not found or does not belong to you.")

        note = await self.note_repo.create(
            user_id=user_id,
            title=data.title,
            content=data.content,
            category_id=category_id
        )
        if tag_names:
            from app.repositories.tag_repo import TagRepository
            tag_repo = TagRepository(self.session)
            for t_name in tag_names:
                cleaned = t_name.strip().lstrip("#").lower()
                if cleaned:
                    tag = await tag_repo.get_or_create(cleaned, user_id)
                    await self.note_repo.add_tag(note, tag)
        return note

    async def update_user_note(
        self,
        note_id: int,
        user_id: int,
        data: NoteUpdate,
        category_id: Optional[int] = None,
        tag_names: Optional[List[str]] = None,
        update_category: bool = False,
        update_tags: bool = False
    ) -> Note:
        """
        Update an existing note strictly checking ownership.
        Raises ValueError if note is not found or belongs to another user.
        """
        note = await self.note_repo.get_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found.")

        if update_category:
            if category_id is not None:
                from app.repositories.category_repo import CategoryRepository
                cat_repo = CategoryRepository(self.session)
                cat = await cat_repo.get_by_id(category_id, user_id)
                if not cat:
                    raise ValueError("Category not found or does not belong to you.")
                note.category_id = cat.id
            else:
                note.category_id = None

        if update_tags:
            from app.repositories.tag_repo import TagRepository
            tag_repo = TagRepository(self.session)
            new_tags = []
            if tag_names:
                for t_name in tag_names:
                    cleaned = t_name.strip().lstrip("#").lower()
                    if cleaned:
                        t = await tag_repo.get_or_create(cleaned, user_id)
                        if t.id not in [x.id for x in new_tags]:
                            new_tags.append(t)
            await self.note_repo.set_tags(note, new_tags)

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

    async def assign_category(self, note_id: int, user_id: int, category_id: Optional[int]) -> Note:
        """Assign or remove a category for a user note verifying ownership."""
        note = await self.note_repo.get_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found.")

        target_cat_id = None
        if category_id:
            from app.repositories.category_repo import CategoryRepository
            cat_repo = CategoryRepository(self.session)
            cat = await cat_repo.get_by_id(category_id, user_id)
            if not cat:
                raise ValueError("Category not found or access denied.")
            target_cat_id = cat.id

        return await self.note_repo.assign_category(note, target_cat_id)

    async def remove_category(self, note_id: int, user_id: int) -> Note:
        """Remove category from note."""
        return await self.assign_category(note_id, user_id, None)

    async def add_tag_to_note(
        self,
        note_id: int,
        user_id: int,
        tag_name: Optional[str] = None,
        tag_id: Optional[int] = None,
        tag_ids: Optional[List[int]] = None,
        tag_names: Optional[List[str]] = None
    ) -> Note:
        """Attach one or more tags to note, verifying ownership of note and all tags."""
        note = await self.note_repo.get_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found.")

        from app.repositories.tag_repo import TagRepository
        tag_repo = TagRepository(self.session)

        # Collect tag IDs to attach
        all_ids = [int(i) for i in tag_ids] if tag_ids else []
        if tag_id is not None and tag_id not in all_ids:
            all_ids.append(int(tag_id))

        # Collect tag names to create/attach
        all_names: List[str] = []
        if tag_names:
            for name_item in tag_names:
                for sub in str(name_item).split(","):
                    c = sub.strip().lstrip("#").lower()
                    if c and c not in all_names:
                        all_names.append(c)
        if tag_name:
            for sub in str(tag_name).split(","):
                c = sub.strip().lstrip("#").lower()
                if c and c not in all_names:
                    all_names.append(c)

        if not all_ids and not all_names:
            raise ValueError("Tag name or ID is required.")

        # Attach by ID
        for tid in all_ids:
            tag = await tag_repo.get_by_id(tid, user_id)
            if not tag:
                raise ValueError("Tag not found or access denied.")
            await self.note_repo.add_tag(note, tag)

        # Attach by Name
        for name in all_names:
            tag = await tag_repo.get_or_create(name, user_id)
            await self.note_repo.add_tag(note, tag)

        return note

    async def remove_tag_from_note(self, note_id: int, user_id: int, tag_id: int) -> Note:
        """Remove a tag from note, verifying ownership of both note and tag."""
        note = await self.note_repo.get_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found.")

        from app.repositories.tag_repo import TagRepository
        tag_repo = TagRepository(self.session)
        tag = await tag_repo.get_by_id(tag_id, user_id)
        if not tag:
            raise ValueError("Tag not found or access denied.")

        return await self.note_repo.remove_tag(note, tag)

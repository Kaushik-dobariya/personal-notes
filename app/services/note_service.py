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
        filter_type: Optional[str] = None,
        category_id: Optional[int] = None,
        tag_id: Optional[int] = None,
        search: Optional[str] = None,
        is_favorite: Optional[bool] = None,
        is_pinned: Optional[bool] = None,
        status: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> List[Note]:
        """
        Fetch notes belonging to current user according to search, combined filters, and sorting.
        Strictly verifies ownership of user notes, categories, and tags.
        """
        # Strictly verify category ownership if category_id is provided
        if category_id is not None:
            from app.repositories.category_repo import CategoryRepository
            cat = await CategoryRepository(self.session).get_by_id(category_id, user_id)
            if not cat:
                # Category does not exist or belongs to another user -> return empty list
                return []

        # Strictly verify tag ownership if tag_id is provided
        if tag_id is not None:
            from app.repositories.tag_repo import TagRepository
            tag = await TagRepository(self.session).get_by_id(tag_id, user_id)
            if not tag:
                # Tag does not exist or belongs to another user -> return empty list
                return []

        return await self.note_repo.get_active_by_user(
            user_id=user_id,
            filter_type=filter_type,
            category_id=category_id,
            tag_id=tag_id,
            search=search,
            is_favorite=is_favorite,
            is_pinned=is_pinned,
            status=status,
            sort=sort,
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
        """Create a new note owned by current user with optional category, tags, and status flags."""
        if category_id is not None:
            from app.repositories.category_repo import CategoryRepository
            cat_repo = CategoryRepository(self.session)
            cat = await cat_repo.get_by_id(category_id, user_id)
            if not cat:
                raise ValueError("Category not found or does not belong to you.")

        if data.is_archived and data.is_pinned:
            raise ValueError("Archived notes cannot be pinned.")

        note = await self.note_repo.create(
            user_id=user_id,
            title=data.title,
            content=data.content,
            category_id=category_id,
            is_favorite=bool(data.is_favorite),
            is_pinned=bool(data.is_pinned),
            is_archived=bool(data.is_archived)
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

        if data.is_favorite is not None:
            note.is_favorite = data.is_favorite
        if data.is_archived is not None:
            note.is_archived = data.is_archived
            if note.is_archived:
                note.is_pinned = False
        if data.is_pinned is not None:
            if note.is_archived and data.is_pinned:
                raise ValueError("Archived notes cannot be pinned.")
            note.is_pinned = data.is_pinned

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

    async def get_user_note_counts(self, user_id: int) -> dict:
        """Fetch counts of all, favorites, pinned, and archived notes owned by the user."""
        return await self.note_repo.get_user_note_counts(user_id)

    async def toggle_favorite(self, note_id: int, user_id: int) -> Note:
        """Toggle favorite status of a note verifying ownership."""
        note = await self.note_repo.get_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found.")
        return await self.note_repo.toggle_favorite(note)

    async def set_favorite(self, note_id: int, user_id: int, is_favorite: bool) -> Note:
        """Set favorite status of a note verifying ownership."""
        note = await self.note_repo.get_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found.")
        return await self.note_repo.set_favorite(note, is_favorite)

    async def toggle_pin(self, note_id: int, user_id: int) -> Note:
        """Toggle pinned status of a note verifying ownership."""
        note = await self.note_repo.get_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found.")
        if note.is_archived:
            raise ValueError("Archived notes cannot be pinned.")
        return await self.note_repo.toggle_pin(note)

    async def set_pinned(self, note_id: int, user_id: int, is_pinned: bool) -> Note:
        """Set pinned status of a note verifying ownership."""
        note = await self.note_repo.get_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found.")
        if note.is_archived and is_pinned:
            raise ValueError("Archived notes cannot be pinned.")
        return await self.note_repo.set_pinned(note, is_pinned)

    async def toggle_archive(self, note_id: int, user_id: int) -> Note:
        """Toggle archived status of a note verifying ownership."""
        note = await self.note_repo.get_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found.")
        return await self.note_repo.toggle_archive(note)

    async def set_archived(self, note_id: int, user_id: int, is_archived: bool) -> Note:
        """Set archived status of a note verifying ownership."""
        note = await self.note_repo.get_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found.")
        return await self.note_repo.set_archived(note, is_archived)

    async def get_trashed_note(self, note_id: int, user_id: int) -> Optional[Note]:
        """Fetch a single trashed note strictly verifying ownership."""
        return await self.note_repo.get_deleted_by_id(note_id, user_id)

    async def restore_user_note(self, note_id: int, user_id: int) -> Note:
        """
        Restore a trashed note back to its active state verifying ownership.
        Raises ValueError if note is not found or not in trash.
        """
        note = await self.note_repo.get_deleted_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found in trash.")
        return await self.note_repo.restore(note)

    async def permanent_delete_user_note(self, note_id: int, user_id: int) -> None:
        """
        Permanently delete a note verifying ownership.
        Strictly only allowed if note is already in trash (is_deleted is True).
        Raises ValueError if note is not found or not in trash.
        """
        note = await self.note_repo.get_deleted_by_id(note_id, user_id)
        if not note:
            raise ValueError("Note not found in trash.")
        await self.note_repo.permanent_delete(note)

    async def empty_user_trash(self, user_id: int) -> int:
        """
        Permanently delete all trashed notes for the current user.
        Does not affect any active notes or other users' notes.
        Returns the count of deleted notes.
        """
        return await self.note_repo.empty_trash(user_id)


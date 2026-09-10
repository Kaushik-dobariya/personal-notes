from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note
from app.models.tag import Tag
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

    async def get_deleted_by_id(self, note_id: int, user_id: int) -> Optional[Note]:
        """
        Fetch a trashed note strictly verifying ownership and deleted status.
        Conceptual SQL: WHERE note.id = :note_id AND note.user_id = :user_id AND note.is_deleted IS TRUE
        """
        stmt = select(Note).where(
            Note.id == note_id,
            Note.user_id == user_id,
            Note.is_deleted.is_(True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_user(
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
        List notes for the current user according to combined search, filters, and sorting.
        Guaranteed:
          - Always strictly scoped to Note.user_id == user_id.
          - Excludes deleted notes unless status/filter_type is explicitly 'trash'.
          - Case-insensitive, partial-word search across title and content.
          - Combined filtering across category_id, tag_id, is_favorite, is_pinned, and status (active vs archive vs trash).
          - Sorting:
              * 'updated_desc': Recently Updated
              * 'created_desc': Recently Created
              * 'created_asc': Oldest First
              * 'title_asc': Title A-Z
              * 'title_desc': Title Z-A
              * Default for active notes: Pinned notes first, then recently updated notes.
              * Explicit sort: strictly respects the chosen sort order without pinning bias.
        """
        # 1. Determine deleted vs active/archived status
        is_trash = (filter_type == "trash" or status == "trash")
        if is_trash:
            stmt = select(Note).where(Note.user_id == user_id, Note.is_deleted.is_(True))
        else:
            stmt = select(Note).where(Note.user_id == user_id, Note.is_deleted.is_(False))
            # Handle archive vs active
            if filter_type == "archive" or status == "archived":
                stmt = stmt.where(Note.is_archived.is_(True))
            elif status == "all":
                # Excludes trash, includes both active and archived if explicitly requested
                pass
            else:
                # Default active notes
                stmt = stmt.where(Note.is_archived.is_(False))

        # 2. Favorite Filter
        if is_favorite is True or filter_type == "favorites":
            stmt = stmt.where(Note.is_favorite.is_(True))
        elif is_favorite is False:
            stmt = stmt.where(Note.is_favorite.is_(False))

        # 3. Pinned Filter
        if is_pinned is True or filter_type == "pinned":
            stmt = stmt.where(Note.is_pinned.is_(True))
        elif is_pinned is False:
            stmt = stmt.where(Note.is_pinned.is_(False))

        # 4. Category Filter
        if category_id is not None:
            stmt = stmt.where(Note.category_id == category_id)

        # 5. Tag Filter
        if tag_id is not None:
            stmt = stmt.where(Note.tags.any(Tag.id == tag_id))

        # 6. Global Search across Title and Content (case-insensitive & partial match)
        if search and search.strip():
            search_pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Note.title).like(search_pattern),
                    func.lower(Note.content).like(search_pattern)
                )
            )

        # 7. Sorting
        sort_mode = (sort or "").strip().lower()
        if sort_mode == "updated_desc":
            stmt = stmt.order_by(Note.updated_at.desc())
        elif sort_mode == "created_desc":
            stmt = stmt.order_by(Note.created_at.desc())
        elif sort_mode == "created_asc":
            stmt = stmt.order_by(Note.created_at.asc())
        elif sort_mode == "title_asc":
            stmt = stmt.order_by(func.lower(Note.title).asc(), Note.updated_at.desc())
        elif sort_mode == "title_desc":
            stmt = stmt.order_by(func.lower(Note.title).desc(), Note.updated_at.desc())
        else:
            # Default sorting
            if is_trash:
                stmt = stmt.order_by(Note.deleted_at.desc(), Note.updated_at.desc())
            elif filter_type in ("archive", "pinned") or status == "archived":
                stmt = stmt.order_by(Note.updated_at.desc())
            else:
                # Default for active notes: Pinned notes first, then recently updated
                stmt = stmt.order_by(Note.is_pinned.desc(), Note.updated_at.desc())

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        user_id: int,
        title: str,
        content: str = "",
        category_id: Optional[int] = None,
        is_favorite: bool = False,
        is_pinned: bool = False,
        is_archived: bool = False
    ) -> Note:
        """Create a new user-owned note."""
        note = Note(
            user_id=user_id,
            category_id=category_id,
            title=title.strip(),
            content=content.strip() if content else "",
            is_favorite=is_favorite,
            is_pinned=is_pinned,
            is_archived=is_archived,
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

    async def restore(self, note: Note) -> Note:
        """
        Restore a trashed note back to its appropriate active state.
        Sets is_deleted=False and clears deleted_at.
        Preserves content, category, tags, favorite, pin, and archive state.
        """
        note.is_deleted = False
        note.deleted_at = None
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def permanent_delete(self, note: Note) -> None:
        """
        Physically delete a note from the database.
        Associated tags in note_tags will be removed via cascade.
        """
        await self.session.delete(note)
        await self.session.flush()

    async def empty_trash(self, user_id: int) -> int:
        """
        Permanently delete all trashed notes for the specified user.
        Strictly verifies ownership: only notes where user_id == user_id AND is_deleted == True.
        Returns the number of deleted notes.
        """
        from sqlalchemy import delete as sql_delete
        from app.models.note_tag import NoteTag
        stmt_ids = select(Note.id).where(Note.user_id == user_id, Note.is_deleted.is_(True))
        res_ids = await self.session.execute(stmt_ids)
        trashed_ids = list(res_ids.scalars().all())
        if not trashed_ids:
            return 0

        await self.session.execute(
            sql_delete(NoteTag).where(NoteTag.note_id.in_(trashed_ids))
        )
        await self.session.execute(
            sql_delete(Note).where(Note.id.in_(trashed_ids), Note.user_id == user_id)
        )
        await self.session.flush()
        return len(trashed_ids)

    async def assign_category(self, note: Note, category_id: Optional[int]) -> Note:
        """Assign or remove category for a note."""
        note.category_id = category_id
        await self.session.flush()
        await self.session.refresh(note, attribute_names=["category"])
        return note

    async def add_tag(self, note: Note, tag: Tag) -> Note:
        """Add tag to note if not already attached."""
        if tag.id not in [t.id for t in note.tags]:
            note.tags.append(tag)
            await self.session.flush()
            await self.session.refresh(note, attribute_names=["tags"])
        return note

    async def remove_tag(self, note: Note, tag: Tag) -> Note:
        """Remove tag from note."""
        note.tags = [t for t in note.tags if t.id != tag.id]
        await self.session.flush()
        await self.session.refresh(note, attribute_names=["tags"])
        return note

    async def set_tags(self, note: Note, tags: List[Tag]) -> Note:
        """Replace all tags on note with the provided tags list."""
        note.tags = tags
        await self.session.flush()
        await self.session.refresh(note, attribute_names=["tags"])
        return note

    async def toggle_favorite(self, note: Note) -> Note:
        """Toggle is_favorite status of a note."""
        note.is_favorite = not note.is_favorite
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def set_favorite(self, note: Note, is_favorite: bool) -> Note:
        """Set is_favorite status of a note."""
        note.is_favorite = is_favorite
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def toggle_pin(self, note: Note) -> Note:
        """Toggle is_pinned status of a note."""
        if note.is_archived:
            raise ValueError("Archived notes cannot be pinned.")
        note.is_pinned = not note.is_pinned
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def set_pinned(self, note: Note, is_pinned: bool) -> Note:
        """Set is_pinned status of a note."""
        if note.is_archived and is_pinned:
            raise ValueError("Archived notes cannot be pinned.")
        note.is_pinned = is_pinned
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def toggle_archive(self, note: Note) -> Note:
        """Toggle is_archived status of a note."""
        note.is_archived = not note.is_archived
        if note.is_archived:
            note.is_pinned = False
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def set_archived(self, note: Note, is_archived: bool) -> Note:
        """Set is_archived status of a note."""
        note.is_archived = is_archived
        if note.is_archived:
            note.is_pinned = False
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def get_user_note_counts(self, user_id: int) -> dict:
        """
        Return active note counts for the user:
          all (active non-archived), favorites (active non-archived), pinned (active non-archived), archived, trash.
        """
        from sqlalchemy import case, func
        stmt = select(
            func.count(case((Note.is_deleted.is_(False) & Note.is_archived.is_(False), 1))).label("all_count"),
            func.count(case((Note.is_deleted.is_(False) & Note.is_archived.is_(False) & Note.is_favorite.is_(True), 1))).label("favorites_count"),
            func.count(case((Note.is_deleted.is_(False) & Note.is_archived.is_(False) & Note.is_pinned.is_(True), 1))).label("pinned_count"),
            func.count(case((Note.is_deleted.is_(False) & Note.is_archived.is_(True), 1))).label("archived_count"),
            func.count(case((Note.is_deleted.is_(True), 1))).label("trash_count"),
        ).where(Note.user_id == user_id)
        result = await self.session.execute(stmt)
        row = result.one()
        return {
            "all": row.all_count or 0,
            "favorites": row.favorites_count or 0,
            "pinned": row.pinned_count or 0,
            "archived": row.archived_count or 0,
            "trash": row.trash_count or 0,
        }


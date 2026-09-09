from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag
from app.repositories.base import BaseRepository


class TagRepository(BaseRepository[Tag]):
    def __init__(self, session: AsyncSession):
        super().__init__(Tag, session)

    async def get_all_by_user(self, user_id: int) -> List[Tag]:
        """Fetch all tags belonging to user ordered alphabetically."""
        stmt = (
            select(Tag)
            .where(Tag.user_id == user_id)
            .order_by(Tag.name.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, tag_id: int, user_id: int) -> Optional[Tag]:
        stmt = select(Tag).where(
            Tag.id == tag_id,
            Tag.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str, user_id: int) -> Optional[Tag]:
        cleaned = name.strip().lstrip("#").lower()
        stmt = select(Tag).where(
            Tag.user_id == user_id,
            func.lower(Tag.name) == cleaned
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user_id: int, name: str) -> Tag:
        cleaned = name.strip().lstrip("#").lower()
        tag = Tag(user_id=user_id, name=cleaned)
        self.session.add(tag)
        await self.session.flush()
        await self.session.refresh(tag)
        return tag

    async def get_or_create(self, name: str, user_id: int) -> Tag:
        cleaned = name.strip().lstrip("#").lower()
        existing = await self.get_by_name(cleaned, user_id)
        if existing:
            return existing

        tag = Tag(user_id=user_id, name=cleaned)
        self.session.add(tag)
        await self.session.flush()
        await self.session.refresh(tag)
        return tag

    async def rename(self, tag: Tag, new_name: str) -> Tag:
        tag.name = new_name.strip().lstrip("#").lower()
        await self.session.flush()
        await self.session.refresh(tag)
        return tag

    async def delete(self, tag: Tag) -> None:
        from sqlalchemy import delete as sql_delete
        from app.models.note_tag import NoteTag
        await self.session.execute(
            sql_delete(NoteTag).where(NoteTag.tag_id == tag.id)
        )
        await self.session.delete(tag)
        await self.session.flush()

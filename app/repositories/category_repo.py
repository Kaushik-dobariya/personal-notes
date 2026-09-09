from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.note import Note
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    def __init__(self, session: AsyncSession):
        super().__init__(Category, session)

    async def get_all_by_user(self, user_id: int) -> List[Category]:
        """Fetch all categories belonging to the user."""
        stmt = (
            select(Category)
            .where(Category.user_id == user_id)
            .order_by(Category.name.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_with_counts(self, user_id: int) -> List[Tuple[Category, int]]:
        """Fetch categories with active notes count for the user."""
        stmt = (
            select(
                Category,
                func.count(Note.id).filter(Note.is_deleted.is_(False), Note.is_archived.is_(False)).label("notes_count")
            )
            .outerjoin(Note, (Note.category_id == Category.id) & (Note.user_id == user_id))
            .where(Category.user_id == user_id)
            .group_by(Category.id)
            .order_by(Category.name.asc())
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def get_by_id(self, category_id: int, user_id: int) -> Optional[Category]:
        """Fetch specific category ensuring user ownership."""
        stmt = select(Category).where(
            Category.id == category_id,
            Category.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str, user_id: int) -> Optional[Category]:
        """Fetch category by name for this user."""
        stmt = select(Category).where(
            Category.user_id == user_id,
            func.lower(Category.name) == name.strip().lower()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user_id: int, name: str, color: str = "#4f46e5") -> Category:
        category = Category(
            user_id=user_id,
            name=name.strip(),
            color=color.strip()
        )
        self.session.add(category)
        await self.session.flush()
        await self.session.refresh(category)
        return category

    async def update(self, category: Category, name: Optional[str] = None, color: Optional[str] = None) -> Category:
        if name is not None:
            category.name = name.strip()
        if color is not None:
            category.color = color.strip()
        await self.session.flush()
        await self.session.refresh(category)
        return category

    async def delete(self, category: Category) -> None:
        from sqlalchemy import update
        await self.session.execute(
            update(Note)
            .where(Note.category_id == category.id, Note.user_id == category.user_id)
            .values(category_id=None)
        )
        await self.session.delete(category)
        await self.session.flush()

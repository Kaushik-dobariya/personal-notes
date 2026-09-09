from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.repositories.category_repo import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CategoryRepository(session)

    async def get_user_categories_with_counts(self, user_id: int) -> List[Tuple[Category, int]]:
        return await self.repo.get_all_with_counts(user_id)

    async def get_user_categories(self, user_id: int) -> List[Category]:
        return await self.repo.get_all_by_user(user_id)

    async def get_category(self, user_id: int, category_id: int) -> Optional[Category]:
        return await self.repo.get_by_id(category_id, user_id)

    async def create_category(self, user_id: int, data: CategoryCreate) -> Category:
        existing = await self.repo.get_by_name(data.name, user_id)
        if existing:
            raise ValueError(f"Category '{data.name}' already exists.")
        return await self.repo.create(user_id=user_id, name=data.name, color=data.color)

    async def update_category(self, user_id: int, category_id: int, data: CategoryUpdate) -> Category:
        category = await self.repo.get_by_id(category_id, user_id)
        if not category:
            raise ValueError("Category not found.")

        if data.name and data.name.strip().lower() != category.name.lower():
            existing = await self.repo.get_by_name(data.name, user_id)
            if existing:
                raise ValueError(f"Category '{data.name}' already exists.")

        return await self.repo.update(category, name=data.name, color=data.color)

    async def delete_category(self, user_id: int, category_id: int) -> None:
        category = await self.repo.get_by_id(category_id, user_id)
        if not category:
            raise ValueError("Category not found.")
        await self.repo.delete(category)

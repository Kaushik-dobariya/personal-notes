from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag
from app.repositories.tag_repo import TagRepository


class TagService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TagRepository(session)

    async def get_user_tags(self, user_id: int) -> List[Tag]:
        return await self.repo.get_all_by_user(user_id)

    async def get_tag(self, user_id: int, tag_id: int) -> Optional[Tag]:
        return await self.repo.get_by_id(tag_id, user_id)

    async def create_tag(self, user_id: int, name: str) -> Tag:
        cleaned = name.strip().lstrip("#").lower()
        if not cleaned:
            raise ValueError("Tag name cannot be empty.")
        existing = await self.repo.get_by_name(cleaned, user_id)
        if existing:
            raise ValueError(f"Tag '#{cleaned}' already exists.")
        return await self.repo.create(user_id, cleaned)

    async def rename_tag(self, user_id: int, tag_id: int, new_name: str) -> Tag:
        tag = await self.repo.get_by_id(tag_id, user_id)
        if not tag:
            raise ValueError("Tag not found.")

        cleaned = new_name.strip().lstrip("#").lower()
        if not cleaned:
            raise ValueError("Tag name cannot be empty.")

        existing = await self.repo.get_by_name(cleaned, user_id)
        if existing and existing.id != tag.id:
            raise ValueError(f"Tag '#{cleaned}' already exists.")

        return await self.repo.rename(tag, cleaned)

    async def delete_tag(self, user_id: int, tag_id: int) -> None:
        tag = await self.repo.get_by_id(tag_id, user_id)
        if not tag:
            raise ValueError("Tag not found.")
        await self.repo.delete(tag)

    async def parse_and_sync_tags(self, user_id: int, tag_names_str: Optional[str]) -> List[Tag]:
        """Convert comma-separated tag string (e.g. 'work, urgent, project') into persistent Tag entities."""
        if not tag_names_str:
            return []

        tags = []
        raw_names = [t.strip().lstrip("#").lower() for t in tag_names_str.split(",")]
        # Deduplicate preserving order
        unique_names = list(dict.fromkeys([name for name in raw_names if name]))

        for name in unique_names:
            tag = await self.repo.get_or_create(name, user_id)
            tags.append(tag)
        return tags

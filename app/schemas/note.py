from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(default="")
    is_favorite: Optional[bool] = False
    is_pinned: Optional[bool] = False
    is_archived: Optional[bool] = False

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Title cannot be empty.")
        return cleaned


class NoteUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(default="")
    is_favorite: Optional[bool] = None
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Title cannot be empty.")
        return cleaned


class NoteUpdateTitle(BaseModel):
    title: str = Field(min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Title cannot be empty.")
        return cleaned


class NoteUpdateContent(BaseModel):
    content: str = Field(default="")


class NoteAppend(BaseModel):
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def clean_text(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Appended text cannot be empty.")
        return cleaned


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    content: str
    category_id: Optional[int] = None
    is_favorite: bool = False
    is_pinned: bool = False
    is_archived: bool = False
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

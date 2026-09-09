from pydantic import BaseModel, ConfigDict, Field, field_validator


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        cleaned = v.strip().lstrip("#").lower()
        if not cleaned:
            raise ValueError("Tag name cannot be empty.")
        return cleaned


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class NoteTagAssign(BaseModel):
    name: str = Field(min_length=1, max_length=40)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        cleaned = v.strip().lstrip("#").lower()
        if not cleaned:
            raise ValueError("Tag name cannot be empty.")
        return cleaned

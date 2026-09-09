from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.tag import TagCreate
from app.services.tag_service import TagService

router = APIRouter(prefix="/tags", tags=["Tags"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/modal", response_class=HTMLResponse)
async def tag_create_modal(request: Request):
    """Render modal dialog for creating a new tag."""
    return templates.TemplateResponse(
        request=request,
        name="partials/tag_modal.html",
        context={"tag": None}
    )


@router.get("/{tag_id}/edit-modal", response_class=HTMLResponse)
async def tag_edit_modal(
    request: Request,
    tag_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Render modal dialog for renaming a tag."""
    service = TagService(db)
    tag = await service.get_tag(current_user.id, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    return templates.TemplateResponse(
        request=request,
        name="partials/tag_modal.html",
        context={"tag": tag}
    )


@router.post("", response_class=HTMLResponse)
async def create_tag(
    request: Request,
    response: Response,
    name: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new user tag and return updated sidebar partial."""
    try:
        data = TagCreate(name=name)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.errors()[0]["msg"])

    service = TagService(db)
    await service.create_tag(current_user.id, data.name)

    all_tags = await service.get_user_tags(current_user.id)
    response.headers["HX-Trigger"] = "closeModal"
    return templates.TemplateResponse(
        request=request,
        name="partials/sidebar_tags.html",
        context={"all_tags": all_tags, "current_tag_id": None}
    )


@router.put("/{tag_id}", response_class=HTMLResponse)
async def update_tag(
    request: Request,
    response: Response,
    tag_id: int,
    name: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Rename a user tag and return updated sidebar partial."""
    try:
        data = TagCreate(name=name)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.errors()[0]["msg"])

    service = TagService(db)
    try:
        await service.rename_tag(current_user.id, tag_id, data.name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    all_tags = await service.get_user_tags(current_user.id)
    response.headers["HX-Trigger"] = "closeModal"
    return templates.TemplateResponse(
        request=request,
        name="partials/sidebar_tags.html",
        context={"all_tags": all_tags, "current_tag_id": tag_id}
    )


@router.delete("/{tag_id}", response_class=HTMLResponse)
async def delete_tag(
    request: Request,
    tag_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user tag."""
    service = TagService(db)
    try:
        await service.delete_tag(current_user.id, tag_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    all_tags = await service.get_user_tags(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/sidebar_tags.html",
        context={"all_tags": all_tags, "current_tag_id": None}
    )

from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["Categories"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/modal", response_class=HTMLResponse)
async def category_create_modal(request: Request):
    """Render modal dialog for creating a new category."""
    return templates.TemplateResponse(
        request=request,
        name="partials/category_modal.html",
        context={"category": None}
    )


@router.get("/{category_id}/edit-modal", response_class=HTMLResponse)
async def category_edit_modal(
    request: Request,
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Render modal dialog for editing a category."""
    service = CategoryService(db)
    category = await service.get_category(current_user.id, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    return templates.TemplateResponse(
        request=request,
        name="partials/category_modal.html",
        context={"category": category}
    )


@router.post("", response_class=HTMLResponse)
async def create_category(
    request: Request,
    response: Response,
    name: str = Form(...),
    color: str = Form("#4f46e5"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new user category and return updated sidebar partial."""
    try:
        data = CategoryCreate(name=name, color=color)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.errors()[0]["msg"])

    service = CategoryService(db)
    try:
        await service.create_category(current_user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    categories_with_counts = await service.get_user_categories_with_counts(current_user.id)
    response.headers["HX-Trigger"] = "closeModal"
    return templates.TemplateResponse(
        request=request,
        name="partials/sidebar_categories.html",
        context={"categories_with_counts": categories_with_counts, "current_category_id": None}
    )


@router.put("/{category_id}", response_class=HTMLResponse)
async def update_category(
    request: Request,
    response: Response,
    category_id: int,
    name: str = Form(...),
    color: str = Form("#4f46e5"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a user category and return updated sidebar partial."""
    try:
        data = CategoryUpdate(name=name, color=color)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.errors()[0]["msg"])

    service = CategoryService(db)
    try:
        await service.update_category(current_user.id, category_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    categories_with_counts = await service.get_user_categories_with_counts(current_user.id)
    response.headers["HX-Trigger"] = "closeModal"
    return templates.TemplateResponse(
        request=request,
        name="partials/sidebar_categories.html",
        context={"categories_with_counts": categories_with_counts, "current_category_id": category_id}
    )


@router.delete("/{category_id}", response_class=HTMLResponse)
async def delete_category(
    request: Request,
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user category."""
    service = CategoryService(db)
    try:
        await service.delete_category(current_user.id, category_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    categories_with_counts = await service.get_user_categories_with_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/sidebar_categories.html",
        context={"categories_with_counts": categories_with_counts, "current_category_id": None}
    )

from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["Categories"])
templates = Jinja2Templates(directory="app/templates")


def _is_json_request(request: Request) -> bool:
    content_type = request.headers.get("content-type", "")
    accept = request.headers.get("accept", "")
    return "application/json" in content_type or "application/json" in accept


@router.get("", response_class=HTMLResponse)
@router.get("/sidebar", response_class=HTMLResponse)
async def list_categories(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all categories for the current user."""
    service = CategoryService(db)
    if _is_json_request(request):
        categories = await service.get_user_categories(current_user.id)
        return JSONResponse(
            content=[CategoryOut.model_validate(c).model_dump(mode="json") for c in categories]
        )

    categories_with_counts = await service.get_user_categories_with_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/sidebar_categories.html",
        context={"categories_with_counts": categories_with_counts, "current_category_id": None}
    )


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


@router.get("/{category_id}/inline-edit", response_class=HTMLResponse)
async def category_inline_edit(
    request: Request,
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Render inline edit row for category in sidebar/list."""
    service = CategoryService(db)
    category = await service.get_category(current_user.id, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    return templates.TemplateResponse(
        request=request,
        name="partials/category_item_edit.html",
        context={"category": category}
    )


@router.get("/{category_id}/inline-view", response_class=HTMLResponse)
async def category_inline_view(
    request: Request,
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Render read-only category row."""
    service = CategoryService(db)
    category = await service.get_category(current_user.id, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    pairs = await service.get_user_categories_with_counts(current_user.id)
    count = next((cnt for cat, cnt in pairs if cat.id == category.id), 0)
    return templates.TemplateResponse(
        request=request,
        name="partials/category_item.html",
        context={"category": category, "count": count, "current_category_id": None}
    )


@router.post("", response_class=HTMLResponse)
async def create_category(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new user category and return updated sidebar partial or JSON."""
    is_json = _is_json_request(request)
    if "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        raw_name = body.get("name", "")
        raw_color = body.get("color", "#4f46e5")
    else:
        form = await request.form()
        raw_name = form.get("name", "")
        raw_color = form.get("color", "#4f46e5")

    try:
        data = CategoryCreate(name=raw_name, color=raw_color)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.errors()[0]["msg"])

    service = CategoryService(db)
    try:
        created = await service.create_category(current_user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if is_json:
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=CategoryOut.model_validate(created).model_dump(mode="json")
        )

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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a user category and return updated partial or JSON."""
    is_json = _is_json_request(request)
    if "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        raw_name = body.get("name", None)
        raw_color = body.get("color", None)
    else:
        form = await request.form()
        raw_name = form.get("name", None)
        raw_color = form.get("color", None)

    try:
        data = CategoryUpdate(name=raw_name, color=raw_color)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.errors()[0]["msg"])

    service = CategoryService(db)
    try:
        updated = await service.update_category(current_user.id, category_id, data)
    except ValueError as e:
        err_str = str(e)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in err_str.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=err_str)

    if is_json:
        return JSONResponse(content=CategoryOut.model_validate(updated).model_dump(mode="json"))

    target = request.headers.get("HX-Target", "")
    if target.startswith("category-item-"):
        pairs = await service.get_user_categories_with_counts(current_user.id)
        count = next((cnt for cat, cnt in pairs if cat.id == updated.id), 0)
        return templates.TemplateResponse(
            request=request,
            name="partials/category_item.html",
            context={"category": updated, "count": count, "current_category_id": None}
        )

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

    if _is_json_request(request):
        return JSONResponse(content={"success": True, "message": "Category deleted", "id": category_id})

    target = request.headers.get("HX-Target", "")
    if target.startswith("category-item-"):
        return HTMLResponse(content="", status_code=status.HTTP_200_OK)

    categories_with_counts = await service.get_user_categories_with_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/sidebar_categories.html",
        context={"categories_with_counts": categories_with_counts, "current_category_id": None}
    )

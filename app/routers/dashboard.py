from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.category_service import CategoryService
from app.services.note_service import NoteService
from app.services.tag_service import TagService

router = APIRouter(tags=["Dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard_index(
    request: Request,
    category_id: Optional[int] = Query(None),
    tag_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Main dashboard showing user-owned active notes.
    Supports filtering by category_id and tag_id.
    """
    note_service = NoteService(db)
    cat_service = CategoryService(db)
    tag_service = TagService(db)

    notes = await note_service.list_user_notes(
        current_user.id, category_id=category_id, tag_id=tag_id
    )
    categories_with_counts = await cat_service.get_user_categories_with_counts(current_user.id)
    all_tags = await tag_service.get_user_tags(current_user.id)
    all_categories = [c for c, _ in categories_with_counts]

    selected_category = None
    if category_id:
        selected_category = await cat_service.get_category(current_user.id, category_id)

    selected_tag = None
    if tag_id:
        selected_tag = await tag_service.get_tag(current_user.id, tag_id)

    return templates.TemplateResponse(
        request=request,
        name="pages/dashboard/index.html",
        context={
            "current_user": current_user,
            "notes": notes,
            "categories_with_counts": categories_with_counts,
            "all_categories": all_categories,
            "all_tags": all_tags,
            "current_category_id": category_id,
            "current_tag_id": tag_id,
            "selected_category": selected_category,
            "selected_tag": selected_tag
        }
    )

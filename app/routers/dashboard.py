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
    filter: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    tag_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Main dashboard showing user-owned notes.
    Supports filtering by filter ('favorites', 'pinned', 'archive', 'trash'), category_id, tag_id,
    live text search, and multiple sort orders.
    """
    note_service = NoteService(db)
    cat_service = CategoryService(db)
    tag_service = TagService(db)

    # Normalize filter
    normalized_filter = filter.strip().lower() if filter else None
    if normalized_filter not in ("favorites", "pinned", "archive", "trash"):
        normalized_filter = None

    normalized_sort = sort.strip() if sort else None
    cleaned_search = search.strip() if search and search.strip() else None

    notes = await note_service.list_user_notes(
        current_user.id,
        filter_type=normalized_filter,
        category_id=category_id,
        tag_id=tag_id,
        search=cleaned_search,
        sort=normalized_sort
    )
    note_counts = await note_service.get_user_note_counts(current_user.id)
    categories_with_counts = await cat_service.get_user_categories_with_counts(current_user.id)
    all_tags = await tag_service.get_user_tags(current_user.id)
    all_categories = [c for c, _ in categories_with_counts]

    selected_category = None
    if category_id:
        selected_category = await cat_service.get_category(current_user.id, category_id)

    selected_tag = None
    if tag_id:
        selected_tag = await tag_service.get_tag(current_user.id, tag_id)

    context = {
        "request": request,
        "current_user": current_user,
        "notes": notes,
        "note_counts": note_counts,
        "current_filter": normalized_filter,
        "categories_with_counts": categories_with_counts,
        "all_categories": all_categories,
        "all_tags": all_tags,
        "current_category_id": category_id,
        "current_tag_id": tag_id,
        "selected_category": selected_category,
        "selected_tag": selected_tag,
        "search_query": cleaned_search,
        "current_sort": normalized_sort
    }

    # If requested specifically by HTMX to update the notes grid (search/filter/sort)
    if request.headers.get("HX-Target") in ("notes-grid", "notes-list-container"):
        return templates.TemplateResponse(
            request=request,
            name="partials/note_list.html",
            context=context
        )

    return templates.TemplateResponse(
        request=request,
        name="pages/dashboard/index.html",
        context=context
    )


@router.get("/favorites", response_class=HTMLResponse)
async def dashboard_favorites(
    request: Request,
    category_id: Optional[int] = Query(None),
    tag_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Convenience route for Favorites view."""
    return await dashboard_index(
        request=request,
        filter="favorites",
        category_id=category_id,
        tag_id=tag_id,
        search=search,
        sort=sort,
        current_user=current_user,
        db=db
    )


@router.get("/pinned", response_class=HTMLResponse)
async def dashboard_pinned(
    request: Request,
    category_id: Optional[int] = Query(None),
    tag_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Convenience route for Pinned Notes view."""
    return await dashboard_index(
        request=request,
        filter="pinned",
        category_id=category_id,
        tag_id=tag_id,
        search=search,
        sort=sort,
        current_user=current_user,
        db=db
    )


@router.get("/archive", response_class=HTMLResponse)
async def dashboard_archive(
    request: Request,
    category_id: Optional[int] = Query(None),
    tag_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Convenience route for Archive view."""
    return await dashboard_index(
        request=request,
        filter="archive",
        category_id=category_id,
        tag_id=tag_id,
        search=search,
        sort=sort,
        current_user=current_user,
        db=db
    )


@router.get("/trash", response_class=HTMLResponse)
async def dashboard_trash(
    request: Request,
    category_id: Optional[int] = Query(None),
    tag_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Convenience route for Trash view."""
    return await dashboard_index(
        request=request,
        filter="trash",
        category_id=category_id,
        tag_id=tag_id,
        search=search,
        sort=sort,
        current_user=current_user,
        db=db
    )

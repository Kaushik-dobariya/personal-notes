from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.note import (
    NoteAppend,
    NoteCreate,
    NoteOut,
    NoteUpdate,
    NoteUpdateContent,
    NoteUpdateTitle,
)
from app.services.note_service import NoteService

router = APIRouter(prefix="/notes", tags=["Notes"])
templates = Jinja2Templates(directory="app/templates")


def _is_json_request(request: Request) -> bool:
    """Helper to detect whether the incoming request prefers/provides JSON."""
    content_type = request.headers.get("content-type", "")
    accept = request.headers.get("accept", "")
    return "application/json" in content_type or "application/json" in accept


# ==========================================
# Standard CRUD Endpoints
# ==========================================

@router.get("", response_class=HTMLResponse)
async def list_notes_redirect():
    """Redirect /notes directly to main dashboard."""
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/favorites", response_class=HTMLResponse)
async def list_favorites_redirect():
    """Redirect /notes/favorites to /favorites."""
    return RedirectResponse(url="/favorites", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/pinned", response_class=HTMLResponse)
async def list_pinned_redirect():
    """Redirect /notes/pinned to /pinned."""
    return RedirectResponse(url="/pinned", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/archive", response_class=HTMLResponse)
async def list_archive_redirect():
    """Redirect /notes/archive to /archive."""
    return RedirectResponse(url="/archive", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/trash", response_class=HTMLResponse)
async def list_trash_redirect():
    """Redirect /notes/trash to /trash."""
    return RedirectResponse(url="/trash", status_code=status.HTTP_303_SEE_OTHER)


@router.delete("/trash/empty", response_class=HTMLResponse)
@router.post("/trash/empty", response_class=HTMLResponse)
async def empty_trash(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Permanently delete all trashed notes for the current user.
    Strictly verifies ownership: only affects notes where user_id == current_user.id AND is_deleted == True.
    """
    note_service = NoteService(db)
    deleted_count = await note_service.empty_user_trash(current_user.id)

    if _is_json_request(request):
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": True, "message": f"{deleted_count} notes permanently deleted.", "count": deleted_count}
        )

    if "HX-Request" in request.headers:
        note_counts = await note_service.get_user_note_counts(current_user.id)
        empty_state_html = (
            '<div class="card border-dashed py-5 text-center my-4 shadow-sm" '
            'style="border: 2px dashed var(--card-border); background-color: var(--card-bg);" id="notes-grid">'
            '  <div class="card-body py-5">'
            '    <div class="display-5 text-muted mb-3"><i class="bi bi-trash3 text-muted"></i></div>'
            '    <h2 class="h4 fw-bold mb-2">Trash is Empty</h2>'
            '    <p class="text-muted small mb-4" style="max-width: 420px; margin: 0 auto;">'
            '      Deleted notes will appear here before being permanently removed.'
            '    </p>'
            '    <a href="/" class="btn btn-outline-primary rounded-pill px-4">'
            '      <i class="bi bi-arrow-left me-1"></i> Return to Notes'
            '    </a>'
            '  </div>'
            '</div>'
            f'<span id="sidebar-trash-count" hx-swap-oob="innerHTML">{note_counts["trash"]}</span>'
            '<span id="trash-header-count" hx-swap-oob="innerHTML">0</span>'
            '<div id="empty-trash-btn-wrapper" hx-swap-oob="innerHTML"></div>'
        )
        return HTMLResponse(content=empty_state_html)

    return RedirectResponse(url="/trash", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/new", response_class=HTMLResponse)
async def create_note_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Render the Create Note form page."""
    from app.services.category_service import CategoryService
    from app.services.tag_service import TagService
    categories = await CategoryService(db).get_user_categories(current_user.id)
    all_tags = await TagService(db).get_user_tags(current_user.id)
    note_counts = await NoteService(db).get_user_note_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="pages/notes/create.html",
        context={
            "current_user": current_user,
            "title": "",
            "content": "",
            "categories": categories,
            "all_tags": all_tags,
            "note_counts": note_counts,
            "error": None
        }
    )


@router.post("", response_class=HTMLResponse)
async def create_note(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new note owned by current_user.
    Supports both HTML Form submissions and JSON payloads.
    """
    is_json = _is_json_request(request)
    raw_category_id = None
    raw_tags = None
    if "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        raw_title = body.get("title", "")
        raw_content = body.get("content", "")
        raw_category_id = body.get("category_id")
        raw_tags = body.get("tags") or body.get("tag_names")
        raw_is_fav = body.get("is_favorite", False)
        raw_is_pinned = body.get("is_pinned", False)
        raw_is_archived = body.get("is_archived", False)
    else:
        form_data = await request.form()
        raw_title = form_data.get("title", "")
        raw_content = form_data.get("content", "")
        raw_category_id = form_data.get("category_id")
        raw_tags = form_data.get("tags") or form_data.get("tag_names")
        raw_is_fav = form_data.get("is_favorite") in ("true", "True", "1", "on", True)
        raw_is_pinned = form_data.get("is_pinned") in ("true", "True", "1", "on", True)
        raw_is_archived = form_data.get("is_archived") in ("true", "True", "1", "on", True)

    try:
        data = NoteCreate(
            title=raw_title,
            content=raw_content or "",
            is_favorite=bool(raw_is_fav),
            is_pinned=bool(raw_is_pinned),
            is_archived=bool(raw_is_archived)
        )
    except (ValidationError, ValueError) as e:
        error_msg = e.errors()[0]["msg"] if hasattr(e, "errors") else str(e)
        if is_json:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        from app.services.category_service import CategoryService
        from app.services.tag_service import TagService
        categories = await CategoryService(db).get_user_categories(current_user.id)
        all_tags = await TagService(db).get_user_tags(current_user.id)
        return templates.TemplateResponse(
            request=request,
            name="pages/notes/create.html",
            context={
                "current_user": current_user,
                "title": raw_title,
                "content": raw_content,
                "categories": categories,
                "all_tags": all_tags,
                "error": error_msg
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    cat_id = None
    if raw_category_id is not None and str(raw_category_id).strip() and str(raw_category_id).strip().lower() not in ("none", "null", ""):
        try:
            cat_id = int(raw_category_id)
        except (ValueError, TypeError):
            if is_json:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category ID.")
            cat_id = None

    tag_list = None
    if raw_tags:
        if isinstance(raw_tags, list):
            tag_list = [str(t) for t in raw_tags if str(t).strip()]
        elif isinstance(raw_tags, str):
            tag_list = [t.strip() for t in raw_tags.split(",") if t.strip()]

    note_service = NoteService(db)
    try:
        note = await note_service.create_user_note(
            current_user.id,
            data,
            category_id=cat_id,
            tag_names=tag_list
        )
    except ValueError as e:
        if is_json:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        from app.services.category_service import CategoryService
        from app.services.tag_service import TagService
        categories = await CategoryService(db).get_user_categories(current_user.id)
        all_tags = await TagService(db).get_user_tags(current_user.id)
        return templates.TemplateResponse(
            request=request,
            name="pages/notes/create.html",
            context={
                "current_user": current_user,
                "title": raw_title,
                "content": raw_content,
                "categories": categories,
                "all_tags": all_tags,
                "error": str(e)
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    if is_json:
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=NoteOut.model_validate(note).model_dump(mode="json")
        )

    return RedirectResponse(url=f"/notes/{note.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{note_id}", response_class=HTMLResponse)
async def view_note(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    View a single note.
    Strictly verifies ownership: queries Note.id == note_id AND Note.user_id == current_user.id.
    Returns 404 if the note doesn't exist or belongs to another user.
    """
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if _is_json_request(request):
        return JSONResponse(content=NoteOut.model_validate(note).model_dump(mode="json"))

    note_counts = await note_service.get_user_note_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="pages/notes/view.html",
        context={
            "current_user": current_user,
            "note": note,
            "note_counts": note_counts
        }
    )


@router.get("/{note_id}/edit", response_class=HTMLResponse)
async def edit_note_page(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Render full edit form page for note.
    Strictly verifies ownership: returns 404 if note belongs to another user.
    """
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    from app.services.category_service import CategoryService
    from app.services.tag_service import TagService
    categories = await CategoryService(db).get_user_categories(current_user.id)
    all_tags = await TagService(db).get_user_tags(current_user.id)

    note_counts = await note_service.get_user_note_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="pages/notes/edit.html",
        context={
            "current_user": current_user,
            "note": note,
            "categories": categories,
            "all_tags": all_tags,
            "note_counts": note_counts,
            "error": None
        }
    )


@router.post("/{note_id}/edit", response_class=HTMLResponse)
@router.put("/{note_id}", response_class=HTMLResponse)
async def update_note(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update note title, content, category, and tags via full page form or API.
    Strictly verifies ownership: returns 404 if note belongs to another user.
    """
    note_service = NoteService(db)
    existing_note = await note_service.get_user_note(note_id, current_user.id)
    if not existing_note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    is_json = _is_json_request(request)
    raw_category_id = None
    raw_tags = None
    update_category = False
    update_tags = False

    if "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        raw_title = body.get("title", "")
        raw_content = body.get("content", "")
        if "category_id" in body:
            update_category = True
            raw_category_id = body.get("category_id")
        if "tags" in body or "tag_names" in body:
            update_tags = True
            raw_tags = body.get("tags") or body.get("tag_names")
    else:
        form_data = await request.form()
        raw_title = form_data.get("title", "")
        raw_content = form_data.get("content", "")
        if "category_id" in form_data:
            update_category = True
            raw_category_id = form_data.get("category_id")
        if "tags" in form_data or "tag_names" in form_data:
            update_tags = True
            raw_tags = form_data.get("tags") or form_data.get("tag_names")

    try:
        data = NoteUpdate(title=raw_title, content=raw_content or "")
    except (ValidationError, ValueError) as e:
        error_msg = e.errors()[0]["msg"] if hasattr(e, "errors") else str(e)
        if is_json:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        from app.services.category_service import CategoryService
        from app.services.tag_service import TagService
        categories = await CategoryService(db).get_user_categories(current_user.id)
        all_tags = await TagService(db).get_user_tags(current_user.id)
        return templates.TemplateResponse(
            request=request,
            name="pages/notes/edit.html",
            context={
                "current_user": current_user,
                "note": existing_note,
                "categories": categories,
                "all_tags": all_tags,
                "error": error_msg
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    cat_id = None
    if update_category and raw_category_id is not None and str(raw_category_id).strip() and str(raw_category_id).strip().lower() not in ("none", "null", ""):
        try:
            cat_id = int(raw_category_id)
        except (ValueError, TypeError):
            if is_json:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category ID.")
            cat_id = None

    tag_list = None
    if update_tags and raw_tags is not None:
        if isinstance(raw_tags, list):
            tag_list = [str(t) for t in raw_tags if str(t).strip()]
        elif isinstance(raw_tags, str):
            tag_list = [t.strip() for t in raw_tags.split(",") if t.strip()]

    try:
        updated_note = await note_service.update_user_note(
            note_id,
            current_user.id,
            data,
            category_id=cat_id,
            tag_names=tag_list,
            update_category=update_category,
            update_tags=update_tags
        )
    except ValueError as e:
        err = str(e)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in err.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=err)

    if is_json:
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    return RedirectResponse(url=f"/notes/{note_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{note_id}/delete", response_class=HTMLResponse)
@router.delete("/{note_id}", response_class=HTMLResponse)
async def delete_note(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Soft delete note.
    Sets is_deleted=True, deleted_at=now, excludes from active notes list.
    Strictly verifies ownership: returns 404 if note belongs to another user.
    """
    note_service = NoteService(db)
    try:
        await note_service.soft_delete_user_note(note_id, current_user.id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if _is_json_request(request):
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": True, "message": "Note deleted successfully", "id": note_id}
        )

    if "HX-Request" in request.headers:
        note_counts = await note_service.get_user_note_counts(current_user.id)
        oob_counts = (
            f'<span id="sidebar-all-count" hx-swap-oob="innerHTML">{note_counts["all"]}</span>'
            f'<span id="sidebar-favorites-count" hx-swap-oob="innerHTML">{note_counts["favorites"]}</span>'
            f'<span id="sidebar-pinned-count" hx-swap-oob="innerHTML">{note_counts["pinned"]}</span>'
            f'<span id="sidebar-archive-count" hx-swap-oob="innerHTML">{note_counts["archived"]}</span>'
            f'<span id="sidebar-trash-count" hx-swap-oob="innerHTML">{note_counts["trash"]}</span>'
        )
        return HTMLResponse(content=f"<!-- note {note_id} deleted -->{oob_counts}")

    if request.method == "DELETE":
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": True, "message": "Note deleted successfully", "id": note_id}
        )

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.patch("/{note_id}/restore", response_class=HTMLResponse)
@router.post("/{note_id}/restore", response_class=HTMLResponse)
async def restore_note(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Restore note from trash.
    Sets is_deleted=False, deleted_at=None.
    Strictly verifies ownership: returns 404 if note does not exist,
    belongs to another user, or is not in trash.
    """
    note_service = NoteService(db)
    try:
        restored_note = await note_service.restore_user_note(note_id, current_user.id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found in trash")

    if _is_json_request(request):
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=NoteOut.model_validate(restored_note).model_dump(mode="json")
        )

    if "HX-Request" in request.headers:
        note_counts = await note_service.get_user_note_counts(current_user.id)
        oob_counts = (
            f'<span id="sidebar-all-count" hx-swap-oob="innerHTML">{note_counts["all"]}</span>'
            f'<span id="sidebar-favorites-count" hx-swap-oob="innerHTML">{note_counts["favorites"]}</span>'
            f'<span id="sidebar-pinned-count" hx-swap-oob="innerHTML">{note_counts["pinned"]}</span>'
            f'<span id="sidebar-archive-count" hx-swap-oob="innerHTML">{note_counts["archived"]}</span>'
            f'<span id="sidebar-trash-count" hx-swap-oob="innerHTML">{note_counts["trash"]}</span>'
            f'<span id="trash-header-count" hx-swap-oob="innerHTML">{note_counts["trash"]}</span>'
        )
        return HTMLResponse(content=f"<!-- note {note_id} restored -->{oob_counts}")

    return RedirectResponse(url="/trash", status_code=status.HTTP_303_SEE_OTHER)


@router.delete("/{note_id}/permanent", response_class=HTMLResponse)
@router.post("/{note_id}/permanent", response_class=HTMLResponse)
async def permanent_delete_note(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Permanently delete a note from the database.
    Strictly verifies ownership and that the note is in trash:
    returns 404 if note does not exist, belongs to another user, or is NOT in trash.
    Cannot permanently delete active notes directly.
    """
    note_service = NoteService(db)
    try:
        await note_service.permanent_delete_user_note(note_id, current_user.id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found in trash")

    if _is_json_request(request):
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": True, "message": "Note permanently deleted", "id": note_id}
        )

    if "HX-Request" in request.headers:
        note_counts = await note_service.get_user_note_counts(current_user.id)
        oob_counts = (
            f'<span id="sidebar-trash-count" hx-swap-oob="innerHTML">{note_counts["trash"]}</span>'
            f'<span id="trash-header-count" hx-swap-oob="innerHTML">{note_counts["trash"]}</span>'
        )
        return HTMLResponse(content=f"<!-- note {note_id} permanently deleted -->{oob_counts}")

    return RedirectResponse(url="/trash", status_code=status.HTTP_303_SEE_OTHER)


# ==========================================
# HTMX Inline Title Endpoints
# ==========================================

@router.get("/{note_id}/title", response_class=HTMLResponse)
async def get_note_title(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the read-only title fragment for HTMX."""
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    return templates.TemplateResponse(
        request=request,
        name="partials/note_title.html",
        context={"note": note, "current_user": current_user}
    )


@router.get("/{note_id}/title/edit", response_class=HTMLResponse)
async def get_note_title_edit(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the inline title edit form fragment for HTMX."""
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    return templates.TemplateResponse(
        request=request,
        name="partials/note_title_edit.html",
        context={"note": note, "current_user": current_user, "error": None}
    )


@router.put("/{note_id}/title", response_class=HTMLResponse)
@router.post("/{note_id}/title", response_class=HTMLResponse)
async def update_note_title(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Save the updated title inline via HTMX.
    Returns the updated note_title.html fragment on success, or note_title_edit.html with error.
    """
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    is_json = _is_json_request(request)
    if "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        raw_title = body.get("title", "")
    else:
        form_data = await request.form()
        raw_title = form_data.get("title", "")

    try:
        data = NoteUpdateTitle(title=raw_title)
    except (ValidationError, ValueError) as e:
        error_msg = e.errors()[0]["msg"] if hasattr(e, "errors") else str(e)
        if is_json:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        return templates.TemplateResponse(
            request=request,
            name="partials/note_title_edit.html",
            context={
                "note": note,
                "title": raw_title,
                "error": error_msg,
                "current_user": current_user
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    updated_note = await note_service.update_note_title(note_id, current_user.id, data.title)

    if is_json:
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    return templates.TemplateResponse(
        request=request,
        name="partials/note_title.html",
        context={"note": updated_note, "current_user": current_user}
    )


# ==========================================
# HTMX Inline Content Endpoints
# ==========================================

@router.get("/{note_id}/content", response_class=HTMLResponse)
async def get_note_content(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the read-only content fragment for HTMX."""
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    return templates.TemplateResponse(
        request=request,
        name="partials/note_content.html",
        context={"note": note, "current_user": current_user}
    )


@router.get("/{note_id}/content/edit", response_class=HTMLResponse)
async def get_note_content_edit(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the inline content edit form fragment for HTMX."""
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    return templates.TemplateResponse(
        request=request,
        name="partials/note_content_edit.html",
        context={"note": note, "current_user": current_user, "error": None}
    )


@router.put("/{note_id}/content", response_class=HTMLResponse)
@router.post("/{note_id}/content", response_class=HTMLResponse)
async def update_note_content(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Save the updated content inline via HTMX.
    Returns the updated note_content.html fragment.
    """
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    is_json = _is_json_request(request)
    if "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        raw_content = body.get("content", "")
    else:
        form_data = await request.form()
        raw_content = form_data.get("content", "")

    data = NoteUpdateContent(content=raw_content or "")
    updated_note = await note_service.update_note_content(note_id, current_user.id, data.content)

    if is_json:
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    return templates.TemplateResponse(
        request=request,
        name="partials/note_content.html",
        context={"note": updated_note, "current_user": current_user}
    )


# ==========================================
# HTMX Inline Append Endpoints
# ==========================================

@router.get("/{note_id}/append", response_class=HTMLResponse)
async def get_note_append(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the inline append form fragment for HTMX."""
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    return templates.TemplateResponse(
        request=request,
        name="partials/note_append.html",
        context={"note": note, "current_user": current_user, "error": None}
    )


@router.post("/{note_id}/append", response_class=HTMLResponse)
async def append_note_content(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Append text to existing note content via HTMX.
    Separates with '---' if existing content exists.
    Returns the updated note_content.html fragment.
    """
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    is_json = _is_json_request(request)
    if "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        raw_text = body.get("text", "")
    else:
        form_data = await request.form()
        raw_text = form_data.get("text", "")

    try:
        data = NoteAppend(text=raw_text)
    except (ValidationError, ValueError) as e:
        error_msg = e.errors()[0]["msg"] if hasattr(e, "errors") else str(e)
        if is_json:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        return templates.TemplateResponse(
            request=request,
            name="partials/note_append.html",
            context={
                "note": note,
                "text": raw_text,
                "error": error_msg,
                "current_user": current_user
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    updated_note = await note_service.append_note_content(note_id, current_user.id, data.text)

    if is_json:
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    return templates.TemplateResponse(
        request=request,
        name="partials/note_content.html",
        context={"note": updated_note, "current_user": current_user}
    )


# ==========================================
# HTMX Note Category Endpoints
# ==========================================

@router.get("/{note_id}/category", response_class=HTMLResponse)
async def get_note_category(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the read-only category fragment for a note."""
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    return templates.TemplateResponse(
        request=request,
        name="partials/note_category.html",
        context={"note": note, "current_user": current_user}
    )


@router.get("/{note_id}/category/edit", response_class=HTMLResponse)
async def get_note_category_edit(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the inline category selector form for a note."""
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    from app.services.category_service import CategoryService
    all_categories = await CategoryService(db).get_user_categories(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/note_category_edit.html",
        context={"note": note, "all_categories": all_categories, "current_user": current_user}
    )


@router.patch("/{note_id}/category", response_class=HTMLResponse)
@router.put("/{note_id}/category", response_class=HTMLResponse)
@router.post("/{note_id}/category", response_class=HTMLResponse)
async def assign_note_category(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Assign or change category for a note.
    Strictly verifies ownership:
      - Returns 404 if note does not belong to current user.
      - Returns 400 if category does not belong to current user.
    """
    is_json = _is_json_request(request)
    if "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        raw_category_id = body.get("category_id")
    else:
        form = await request.form()
        raw_category_id = form.get("category_id")

    cat_id = None
    if raw_category_id is not None and str(raw_category_id).strip() and str(raw_category_id).strip().lower() not in ("none", "null", ""):
        try:
            cat_id = int(raw_category_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category ID.")

    note_service = NoteService(db)
    try:
        updated_note = await note_service.assign_category(note_id, current_user.id, cat_id)
    except ValueError as e:
        err = str(e)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in err.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=err)

    if is_json:
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    target = request.headers.get("HX-Target", "")
    if target.startswith("note-card-"):
        from app.services.category_service import CategoryService
        all_categories = await CategoryService(db).get_user_categories(current_user.id)
        return templates.TemplateResponse(
            request=request,
            name="partials/note_card.html",
            context={"note": updated_note, "all_categories": all_categories, "current_user": current_user}
        )

    return templates.TemplateResponse(
        request=request,
        name="partials/note_category.html",
        context={"note": updated_note, "current_user": current_user}
    )


@router.delete("/{note_id}/category", response_class=HTMLResponse)
async def remove_note_category(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove category from note."""
    note_service = NoteService(db)
    try:
        updated_note = await note_service.remove_category(note_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if _is_json_request(request):
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    target = request.headers.get("HX-Target", "")
    if target.startswith("note-card-"):
        from app.services.category_service import CategoryService
        all_categories = await CategoryService(db).get_user_categories(current_user.id)
        return templates.TemplateResponse(
            request=request,
            name="partials/note_card.html",
            context={"note": updated_note, "all_categories": all_categories, "current_user": current_user}
        )

    return templates.TemplateResponse(
        request=request,
        name="partials/note_category.html",
        context={"note": updated_note, "current_user": current_user}
    )


# ==========================================
# HTMX Note Tag Endpoints
# ==========================================

@router.get("/{note_id}/tags", response_class=HTMLResponse)
async def get_note_tags(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the read-only tags fragment for a note."""
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    return templates.TemplateResponse(
        request=request,
        name="partials/note_tags.html",
        context={"note": note, "current_user": current_user}
    )


@router.get("/{note_id}/tags/selector", response_class=HTMLResponse)
async def get_note_tags_selector(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the tag selector / quick add form for a note."""
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    from app.services.tag_service import TagService
    all_tags = await TagService(db).get_user_tags(current_user.id)
    note_tag_ids = {tag.id for tag in note.tags}
    available_tags = [t for t in all_tags if t.id not in note_tag_ids]
    return templates.TemplateResponse(
        request=request,
        name="partials/tag_selector.html",
        context={
            "note": note,
            "all_tags": all_tags,
            "available_tags": available_tags,
            "current_user": current_user
        }
    )


@router.post("/{note_id}/tags", response_class=HTMLResponse)
async def add_tag_to_note(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Attach a tag to a note (by name or by ID).
    Strictly verifies ownership:
      - Returns 404 if note does not belong to current user.
      - Returns 400 if tag does not belong to current user.
    """
    is_json = _is_json_request(request)
    raw_name = None
    raw_tag_id = None
    if "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        raw_name = body.get("name")
        raw_tag_id = body.get("tag_id")
    else:
        form = await request.form()
        raw_name = form.get("name")
        raw_tag_id = form.get("tag_id")

    tag_id = int(raw_tag_id) if raw_tag_id and str(raw_tag_id).isdigit() else None

    note_service = NoteService(db)
    try:
        updated_note = await note_service.add_tag_to_note(
            note_id, current_user.id, tag_name=raw_name, tag_id=tag_id
        )
    except ValueError as e:
        err = str(e)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in err.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=err)

    if is_json:
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    from app.services.tag_service import TagService
    all_tags = await TagService(db).get_user_tags(current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="partials/note_tags.html",
        context={"note": updated_note, "all_tags": all_tags, "current_user": current_user}
    )


@router.delete("/{note_id}/tags/{tag_id}", response_class=HTMLResponse)
async def remove_tag_from_note(
    request: Request,
    note_id: int,
    tag_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a tag from a note.
    Strictly verifies ownership:
      - Returns 404 if note does not belong to current user.
      - Returns 400/404 if tag does not belong to current user.
    """
    note_service = NoteService(db)
    try:
        updated_note = await note_service.remove_tag_from_note(note_id, current_user.id, tag_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if _is_json_request(request):
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    return templates.TemplateResponse(
        request=request,
        name="partials/note_tags.html",
        context={"note": updated_note, "current_user": current_user}
    )


# ==========================================
# Favorite Endpoints
# ==========================================

@router.get("/{note_id}/favorite", response_class=HTMLResponse)
async def get_note_favorite_fragment(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the favorite action fragment for a note."""
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    note_counts = await note_service.get_user_note_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/note_favorite_action.html",
        context={"note": note, "current_user": current_user, "note_counts": note_counts}
    )


@router.patch("/{note_id}/toggle-favorite", response_class=HTMLResponse)
@router.post("/{note_id}/toggle-favorite", response_class=HTMLResponse)
async def toggle_note_favorite(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Toggle favorite status of a note verifying ownership."""
    note_service = NoteService(db)
    try:
        updated_note = await note_service.toggle_favorite(note_id, current_user.id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if _is_json_request(request):
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    note_counts = await note_service.get_user_note_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/note_favorite_action.html",
        context={"note": updated_note, "current_user": current_user, "note_counts": note_counts}
    )


@router.patch("/{note_id}/favorite", response_class=HTMLResponse)
@router.post("/{note_id}/favorite", response_class=HTMLResponse)
async def mark_note_favorite(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Explicitly mark note as favorite verifying ownership."""
    note_service = NoteService(db)
    try:
        updated_note = await note_service.set_favorite(note_id, current_user.id, is_favorite=True)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if _is_json_request(request):
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    note_counts = await note_service.get_user_note_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/note_favorite_action.html",
        context={"note": updated_note, "current_user": current_user, "note_counts": note_counts}
    )


@router.patch("/{note_id}/unfavorite", response_class=HTMLResponse)
@router.post("/{note_id}/unfavorite", response_class=HTMLResponse)
async def unmark_note_favorite(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Explicitly remove note from favorites verifying ownership."""
    note_service = NoteService(db)
    try:
        updated_note = await note_service.set_favorite(note_id, current_user.id, is_favorite=False)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if _is_json_request(request):
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    note_counts = await note_service.get_user_note_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/note_favorite_action.html",
        context={"note": updated_note, "current_user": current_user, "note_counts": note_counts}
    )


# ==========================================
# Pin Endpoints
# ==========================================

@router.get("/{note_id}/pin", response_class=HTMLResponse)
async def get_note_pin_fragment(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the pin action fragment for a note."""
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    note_counts = await note_service.get_user_note_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/note_pin_action.html",
        context={"note": note, "current_user": current_user, "note_counts": note_counts}
    )


@router.patch("/{note_id}/toggle-pin", response_class=HTMLResponse)
@router.post("/{note_id}/toggle-pin", response_class=HTMLResponse)
async def toggle_note_pin(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Toggle pin status of a note verifying ownership."""
    note_service = NoteService(db)
    try:
        updated_note = await note_service.toggle_pin(note_id, current_user.id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if _is_json_request(request):
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    note_counts = await note_service.get_user_note_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/note_pin_action.html",
        context={"note": updated_note, "current_user": current_user, "note_counts": note_counts}
    )


@router.patch("/{note_id}/pin", response_class=HTMLResponse)
@router.post("/{note_id}/pin", response_class=HTMLResponse)
async def mark_note_pinned(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Explicitly pin note verifying ownership."""
    note_service = NoteService(db)
    try:
        updated_note = await note_service.set_pinned(note_id, current_user.id, is_pinned=True)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if _is_json_request(request):
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    note_counts = await note_service.get_user_note_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/note_pin_action.html",
        context={"note": updated_note, "current_user": current_user, "note_counts": note_counts}
    )


@router.patch("/{note_id}/unpin", response_class=HTMLResponse)
@router.post("/{note_id}/unpin", response_class=HTMLResponse)
async def unmark_note_pinned(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Explicitly unpin note verifying ownership."""
    note_service = NoteService(db)
    try:
        updated_note = await note_service.set_pinned(note_id, current_user.id, is_pinned=False)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if _is_json_request(request):
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    note_counts = await note_service.get_user_note_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/note_pin_action.html",
        context={"note": updated_note, "current_user": current_user, "note_counts": note_counts}
    )


# ==========================================
# Archive Endpoints
# ==========================================

@router.get("/{note_id}/archive", response_class=HTMLResponse)
async def get_note_archive_fragment(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the archive action fragment for a note."""
    note_service = NoteService(db)
    note = await note_service.get_user_note(note_id, current_user.id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    note_counts = await note_service.get_user_note_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/note_archive_action.html",
        context={"note": note, "current_user": current_user, "note_counts": note_counts}
    )


@router.patch("/{note_id}/toggle-archive", response_class=HTMLResponse)
@router.post("/{note_id}/toggle-archive", response_class=HTMLResponse)
async def toggle_note_archive(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Toggle archived status of a note verifying ownership."""
    note_service = NoteService(db)
    try:
        updated_note = await note_service.toggle_archive(note_id, current_user.id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if _is_json_request(request):
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    target = request.headers.get("HX-Target", "")
    note_counts = await note_service.get_user_note_counts(current_user.id)

    # When target is the note card col, remove the card from the view
    if target.startswith("note-card-col-") or target.startswith("note-card-"):
        oob_counts = (
            f'<span id="sidebar-all-count" hx-swap-oob="innerHTML">{note_counts["all"]}</span>'
            f'<span id="sidebar-favorites-count" hx-swap-oob="innerHTML">{note_counts["favorites"]}</span>'
            f'<span id="sidebar-pinned-count" hx-swap-oob="innerHTML">{note_counts["pinned"]}</span>'
            f'<span id="sidebar-archive-count" hx-swap-oob="innerHTML">{note_counts["archived"]}</span>'
        )
        return HTMLResponse(content=f"<!-- note {note_id} archived/unarchived -->{oob_counts}")

    return templates.TemplateResponse(
        request=request,
        name="partials/note_archive_action.html",
        context={"note": updated_note, "current_user": current_user, "note_counts": note_counts}
    )


@router.patch("/{note_id}/archive", response_class=HTMLResponse)
@router.post("/{note_id}/archive", response_class=HTMLResponse)
async def mark_note_archived(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Explicitly archive note verifying ownership."""
    note_service = NoteService(db)
    try:
        updated_note = await note_service.set_archived(note_id, current_user.id, is_archived=True)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if _is_json_request(request):
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    target = request.headers.get("HX-Target", "")
    note_counts = await note_service.get_user_note_counts(current_user.id)

    if target.startswith("note-card-col-") or target.startswith("note-card-"):
        oob_counts = (
            f'<span id="sidebar-all-count" hx-swap-oob="innerHTML">{note_counts["all"]}</span>'
            f'<span id="sidebar-favorites-count" hx-swap-oob="innerHTML">{note_counts["favorites"]}</span>'
            f'<span id="sidebar-pinned-count" hx-swap-oob="innerHTML">{note_counts["pinned"]}</span>'
            f'<span id="sidebar-archive-count" hx-swap-oob="innerHTML">{note_counts["archived"]}</span>'
        )
        return HTMLResponse(content=f"<!-- note {note_id} archived -->{oob_counts}")

    return templates.TemplateResponse(
        request=request,
        name="partials/note_archive_action.html",
        context={"note": updated_note, "current_user": current_user, "note_counts": note_counts}
    )


@router.patch("/{note_id}/unarchive", response_class=HTMLResponse)
@router.post("/{note_id}/unarchive", response_class=HTMLResponse)
async def mark_note_unarchived(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Explicitly unarchive note verifying ownership."""
    note_service = NoteService(db)
    try:
        updated_note = await note_service.set_archived(note_id, current_user.id, is_archived=False)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if _is_json_request(request):
        return JSONResponse(content=NoteOut.model_validate(updated_note).model_dump(mode="json"))

    target = request.headers.get("HX-Target", "")
    note_counts = await note_service.get_user_note_counts(current_user.id)

    if target.startswith("note-card-col-") or target.startswith("note-card-"):
        oob_counts = (
            f'<span id="sidebar-all-count" hx-swap-oob="innerHTML">{note_counts["all"]}</span>'
            f'<span id="sidebar-favorites-count" hx-swap-oob="innerHTML">{note_counts["favorites"]}</span>'
            f'<span id="sidebar-pinned-count" hx-swap-oob="innerHTML">{note_counts["pinned"]}</span>'
            f'<span id="sidebar-archive-count" hx-swap-oob="innerHTML">{note_counts["archived"]}</span>'
        )
        return HTMLResponse(content=f"<!-- note {note_id} unarchived -->{oob_counts}")

    return templates.TemplateResponse(
        request=request,
        name="partials/note_archive_action.html",
        context={"note": updated_note, "current_user": current_user, "note_counts": note_counts}
    )


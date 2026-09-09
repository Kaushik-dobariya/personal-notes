from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.tag import TagCreate, TagOut
from app.services.tag_service import TagService

router = APIRouter(prefix="/tags", tags=["Tags"])
templates = Jinja2Templates(directory="app/templates")


def _is_json_request(request: Request) -> bool:
    content_type = request.headers.get("content-type", "")
    accept = request.headers.get("accept", "")
    return "application/json" in content_type or "application/json" in accept


@router.get("", response_class=HTMLResponse)
@router.get("/sidebar", response_class=HTMLResponse)
async def list_tags(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all tags for the current user."""
    service = TagService(db)
    all_tags = await service.get_user_tags(current_user.id)
    if _is_json_request(request):
        return JSONResponse(
            content=[TagOut.model_validate(t).model_dump(mode="json") for t in all_tags]
        )

    return templates.TemplateResponse(
        request=request,
        name="partials/sidebar_tags.html",
        context={"all_tags": all_tags, "current_tag_id": None}
    )


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


@router.get("/{tag_id}/inline-edit", response_class=HTMLResponse)
async def tag_inline_edit(
    request: Request,
    tag_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Render inline edit form for tag in sidebar or list."""
    service = TagService(db)
    tag = await service.get_tag(current_user.id, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    content = f'''
    <div class="btn-group btn-group-sm mb-1" role="group" id="tag-item-{tag.id}">
      <form class="d-inline-flex align-items-center gap-1"
            hx-put="/tags/{tag.id}"
            hx-target="#tag-item-{tag.id}"
            hx-swap="outerHTML">
        <input type="text" name="name" value="{tag.name}" class="form-control form-control-sm py-0 px-2" style="font-size: 0.75rem; width: 100px;" required autofocus>
        <button type="submit" class="btn btn-sm btn-primary py-0 px-2" style="font-size: 0.7rem;">Save</button>
        <button type="button" class="btn btn-sm btn-outline-secondary py-0 px-1" style="font-size: 0.7rem;" hx-get="/tags/{tag.id}/inline-view" hx-target="#tag-item-{tag.id}" hx-swap="outerHTML" title="Cancel">
          <i class="bi bi-x"></i>
        </button>
      </form>
    </div>
    '''
    return HTMLResponse(content=content)


@router.get("/{tag_id}/inline-view", response_class=HTMLResponse)
async def tag_inline_view(
    request: Request,
    tag_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Render read-only tag item."""
    service = TagService(db)
    tag = await service.get_tag(current_user.id, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    return templates.TemplateResponse(
        request=request,
        name="partials/tag_item.html",
        context={"tag": tag, "current_tag_id": None}
    )


@router.post("", response_class=HTMLResponse)
async def create_tag(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new user tag and return updated sidebar partial or JSON."""
    is_json = _is_json_request(request)
    if "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        raw_name = body.get("name", "")
    else:
        form = await request.form()
        raw_name = form.get("name", "")

    try:
        data = TagCreate(name=raw_name)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.errors()[0]["msg"])

    service = TagService(db)
    try:
        created = await service.create_tag(current_user.id, data.name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if is_json:
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=TagOut.model_validate(created).model_dump(mode="json")
        )

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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Rename a user tag and return updated partial or JSON."""
    is_json = _is_json_request(request)
    if "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        raw_name = body.get("name", "")
    else:
        form = await request.form()
        raw_name = form.get("name", "")

    try:
        data = TagCreate(name=raw_name)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.errors()[0]["msg"])

    service = TagService(db)
    try:
        updated = await service.rename_tag(current_user.id, tag_id, data.name)
    except ValueError as e:
        err_str = str(e)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in err_str.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=err_str)

    if is_json:
        return JSONResponse(content=TagOut.model_validate(updated).model_dump(mode="json"))

    target = request.headers.get("HX-Target", "")
    if target.startswith("tag-item-"):
        return templates.TemplateResponse(
            request=request,
            name="partials/tag_item.html",
            context={"tag": updated, "current_tag_id": None}
        )

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

    if _is_json_request(request):
        return JSONResponse(content={"success": True, "message": "Tag deleted", "id": tag_id})

    target = request.headers.get("HX-Target", "")
    if target.startswith("tag-item-") or target.startswith("sidebar-tag-"):
        return HTMLResponse(content="", status_code=status.HTTP_200_OK)

    all_tags = await service.get_user_tags(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="partials/sidebar_tags.html",
        context={"all_tags": all_tags, "current_tag_id": None}
    )

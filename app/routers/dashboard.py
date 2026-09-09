from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.note_service import NoteService

router = APIRouter(tags=["Dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard_index(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Main dashboard showing user-owned active notes."""
    note_service = NoteService(db)
    notes = await note_service.list_user_notes(current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="pages/dashboard/index.html",
        context={
            "current_user": current_user,
            "notes": notes
        }
    )

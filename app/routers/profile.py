from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import PasswordChange
from app.services.auth_service import AuthService

router = APIRouter(prefix="/profile", tags=["Profile"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """View user profile."""
    from app.services.note_service import NoteService
    note_counts = await NoteService(db).get_user_note_counts(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="pages/profile/index.html",
        context={"current_user": current_user, "note_counts": note_counts}
    )


@router.post("/change-password", response_class=HTMLResponse)
async def change_password_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Process password change for authenticated user."""
    try:
        data = PasswordChange(
            current_password=current_password,
            new_password=new_password,
            confirm_password=confirm_password
        )
    except ValidationError as e:
        error_msg = e.errors()[0]["msg"]
        return templates.TemplateResponse(
            request=request,
            name="pages/profile/index.html",
            context={"current_user": current_user, "error": error_msg},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    auth_service = AuthService(db)
    try:
        await auth_service.change_password(current_user, data)
    except ValueError as e:
        return templates.TemplateResponse(
            request=request,
            name="pages/profile/index.html",
            context={"current_user": current_user, "error": str(e)},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    return templates.TemplateResponse(
        request=request,
        name="pages/profile/index.html",
        context={"current_user": current_user, "message": "Password successfully updated."}
    )

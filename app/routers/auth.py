from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user_optional
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import ForgotPasswordRequest, ResetPasswordRequest, UserCreate, UserLogin
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """Render login page or redirect if already authenticated."""
    if current_user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request=request, name="pages/auth/login.html", context={})


@router.post("/login")
async def login_submit(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Process login form submission."""
    try:
        credentials = UserLogin(email=email, password=password)
    except ValidationError as e:
        error_msg = e.errors()[0]["msg"]
        return templates.TemplateResponse(
            request=request,
            name="pages/auth/login.html",
            context={"email": email, "error": error_msg},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    auth_service = AuthService(db)
    user = await auth_service.authenticate_user(credentials.email, credentials.password)
    if not user:
        return templates.TemplateResponse(
            request=request,
            name="pages/auth/login.html",
            context={"email": email, "error": "Invalid email address or password."},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    token = create_access_token({"sub": str(user.id), "email": user.email})
    redirect_resp = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    redirect_resp.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/"
    )
    return redirect_resp


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """Render user registration page."""
    if current_user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request=request, name="pages/auth/signup.html", context={})


@router.post("/signup")
async def signup_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Process user registration."""
    try:
        user_in = UserCreate(
            full_name=full_name,
            email=email,
            password=password,
            confirm_password=confirm_password
        )
    except ValidationError as e:
        error_msg = e.errors()[0]["msg"]
        return templates.TemplateResponse(
            request=request,
            name="pages/auth/signup.html",
            context={"full_name": full_name, "email": email, "error": error_msg},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    auth_service = AuthService(db)
    try:
        user = await auth_service.register_user(user_in)
    except ValueError as e:
        return templates.TemplateResponse(
            request=request,
            name="pages/auth/signup.html",
            context={"full_name": full_name, "email": email, "error": str(e)},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    token = create_access_token({"sub": str(user.id), "email": user.email})
    redirect_resp = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    redirect_resp.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/"
    )
    return redirect_resp


@router.post("/logout")
async def logout(response: Response):
    """Log out by invalidating session cookie."""
    redirect_resp = RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    redirect_resp.delete_cookie(
        key=settings.COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE
    )
    return redirect_resp


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Render forgot password request page."""
    return templates.TemplateResponse(request=request, name="pages/auth/forgot_password.html", context={})


@router.post("/forgot-password")
async def forgot_password_submit(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Initiate password reset token generation and email dispatch."""
    try:
        data = ForgotPasswordRequest(email=email)
    except ValidationError as e:
        error_msg = e.errors()[0]["msg"]
        return templates.TemplateResponse(
            request=request,
            name="pages/auth/forgot_password.html",
            context={"error": error_msg},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    base_url = str(request.base_url)
    auth_service = AuthService(db)
    await auth_service.request_password_reset(data.email, base_url)

    success_msg = (
        f"If an active account exists for {data.email}, you will receive password reset instructions shortly. "
        "For local development, check your terminal console for the direct link!"
    )
    return templates.TemplateResponse(
        request=request,
        name="pages/auth/forgot_password.html",
        context={"message": success_msg}
    )


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str):
    """Render password reset form."""
    if not token:
        return RedirectResponse(url="/auth/forgot-password", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request=request,
        name="pages/auth/reset_password.html",
        context={"token": token}
    )


@router.post("/reset-password")
async def reset_password_submit(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Finalize password reset."""
    try:
        data = ResetPasswordRequest(
            token=token,
            new_password=new_password,
            confirm_password=confirm_password
        )
    except ValidationError as e:
        error_msg = e.errors()[0]["msg"]
        return templates.TemplateResponse(
            request=request,
            name="pages/auth/reset_password.html",
            context={"token": token, "error": error_msg},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    auth_service = AuthService(db)
    try:
        await auth_service.reset_password(data)
    except ValueError as e:
        return templates.TemplateResponse(
            request=request,
            name="pages/auth/reset_password.html",
            context={"token": token, "error": str(e)},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    return templates.TemplateResponse(
        request=request,
        name="pages/auth/login.html",
        context={"message": "Your password has been successfully updated. Please sign in."}
    )

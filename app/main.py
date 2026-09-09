from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.dependencies import AuthenticationRequiredException
from app.db.base import Base
from app.db.session import async_engine
from app.routers import (
    auth_router,
    categories_router,
    dashboard_router,
    notes_router,
    profile_router,
    tags_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown routines."""
    # Ensure tables exist (especially helpful for sqlite dev setups)
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Clean up engine connection pool on shutdown
    await async_engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan
)

# Mount static assets
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


# Exception Handlers
@app.exception_handler(AuthenticationRequiredException)
async def auth_required_exception_handler(request: Request, exc: AuthenticationRequiredException):
    """Redirect unauthenticated requests to login or emit HTMX redirect header."""
    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"HX-Redirect": "/auth/login"}
        )
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)


@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc):
    """Clean 404 handler for HTML pages."""
    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return HTMLResponse(
            content='<div class="alert alert-warning small">Requested item not found.</div>',
            status_code=status.HTTP_404_NOT_FOUND
        )
    return HTMLResponse(
        content='''
        <!DOCTYPE html>
        <html>
        <head><title>404 - Not Found</title><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"></head>
        <body class="d-flex align-items-center justify-content-center min-vh-100 bg-light">
          <div class="text-center">
            <h1 class="display-4 fw-bold">404</h1>
            <p class="text-muted">The page or note you requested does not exist.</p>
            <a href="/" class="btn btn-primary btn-sm">Return to Dashboard</a>
          </div>
        </body>
        </html>
        ''',
        status_code=status.HTTP_404_NOT_FOUND
    )


# Register Routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(notes_router)
app.include_router(categories_router)
app.include_router(tags_router)
app.include_router(profile_router)

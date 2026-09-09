import asyncio
import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Force testing environment and SQLite test database
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_personal_notes.db"
os.environ["ENVIRONMENT"] = "testing"

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Setup test async database engine
test_engine = create_async_engine(
    "sqlite+aiosqlite:///./test_personal_notes.db",
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database():
    """Create all tables before test run and tear down after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()
    # Clean up test database file
    if os.path.exists("./test_personal_notes.db"):
        try:
            os.remove("./test_personal_notes.db")
        except OSError:
            pass


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for making test requests against the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    """Yield an independent async DB session for verifying DB states in tests."""
    async with TestSessionLocal() as session:
        yield session


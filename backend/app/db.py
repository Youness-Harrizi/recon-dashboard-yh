from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


# Async engine + session for the FastAPI app (request handlers).
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


# Sync engine + session for Celery workers. Celery tasks are synchronous, so
# running async SQLAlchemy inside them requires asyncio.run() — not worth the
# overhead when psycopg2 works fine for a background worker.
_sync_url = settings.database_url.replace("+asyncpg", "")
sync_engine = create_engine(_sync_url, pool_pre_ping=True)
SyncSessionLocal: sessionmaker[Session] = sessionmaker(
    sync_engine, expire_on_commit=False, autoflush=False
)

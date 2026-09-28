import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from worker.src.config import settings

logger = logging.getLogger("worker.database")

Base = declarative_base()

engine_kwargs = {"echo": False, "pool_pre_ping": True}
if "sqlite" not in settings.DATABASE_URL:
    engine_kwargs.update({"pool_size": 5, "max_overflow": 10})

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

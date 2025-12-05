import contextlib
import logging
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker, create_async_engine, )
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class DatabaseSessionManager:
    def __init__(self, host: str, engine_kwargs: dict = None):
        self._engine = create_async_engine(host, **(engine_kwargs or {}))
        self._sessionmaker = async_sessionmaker(autocommit=False, bind=self._engine, expire_on_commit=False)

    async def close(self):
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")
        await self._engine.dispose()

        self._engine = None
        self._sessionmaker = None

    async def cleanup(self):
        if self._engine:
            logger.warning("Closing database connection pool.")
            await self.close()

    async def create_tables(self, base: DeclarativeBase):
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")

        async with self._engine.begin() as conn:
            await conn.run_sync(base.metadata.create_all)

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._sessionmaker is None:
            raise Exception("DatabaseSessionManager is not initialized")

        async with self._sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


class Base(DeclarativeBase):
    pass


sessionmanager = DatabaseSessionManager("sqlite+aiosqlite:///./app.db", {"echo": False})


async def get_db():
    async with sessionmanager.session() as session:
        yield session
import os
from datetime import datetime
from typing import Optional, Dict, Any, AsyncGenerator

from sqlalchemy import Column, JSON
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Field

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")

engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Report(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    property_id: str
    name: str
    params: Dict[str, Any] = Field(sa_column=Column(JSON))
    result: Dict[str, Any] = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

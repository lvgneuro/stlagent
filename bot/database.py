from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    user_message = Column(String, nullable=False)
    bot_response = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class UserFactModel(Base):
    __tablename__ = "user_facts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    fact_type = Column(String, nullable=False)
    fact_value = Column(String, nullable=False)
    context = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


@dataclass
class Message:
    user_id: int
    username: str | None
    first_name: str | None
    user_message: str
    bot_response: str
    created_at: datetime


class Database:
    def __init__(self) -> None:
        database_url = os.getenv("DATABASE_URL")
        
        if database_url:
            if "postgresql://" in database_url:
                database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif "postgres://" in database_url:
                database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
            self._engine = create_async_engine(database_url, echo=False)
        else:
            self._engine = create_async_engine("sqlite+aiosqlite:///messages.db", echo=False)
        
        Base.metadata.create_all(self._engine)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def save_message(
        self,
        user_id: int,
        username: str | None,
        first_name: str | None,
        user_message: str,
        bot_response: str,
    ) -> None:
        async with self._session_factory() as session:
            msg = MessageModel(
                user_id=user_id,
                username=username,
                first_name=first_name,
                user_message=user_message,
                bot_response=bot_response,
            )
            session.add(msg)
            await session.commit()
            logger.info(f"Saved message from user {user_id}")

    async def get_user_messages(self, user_id: int, limit: int = 50) -> list[Message]:
        async with self._session_factory() as session:
            from sqlalchemy import select
            stmt = (
                select(MessageModel)
                .where(MessageModel.user_id == user_id)
                .order_by(MessageModel.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                Message(
                    user_id=int(row.user_id),
                    username=str(row.username) if row.username else None,
                    first_name=str(row.first_name) if row.first_name else None,
                    user_message=str(row.user_message),
                    bot_response=str(row.bot_response),
                    created_at=datetime.now(timezone.utc) if row.created_at is None else row.created_at,
                )
                for row in rows
            ]

    async def get_all_users(self) -> list[int]:
        async with self._session_factory() as session:
            from sqlalchemy import select
            stmt = select(MessageModel.user_id).distinct()
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def save_fact(
        self,
        user_id: int,
        fact_type: str,
        fact_value: str,
        context: str | None = None,
    ) -> None:
        async with self._session_factory() as session:
            from sqlalchemy import select
            stmt = select(UserFactModel).where(
                UserFactModel.user_id == user_id,
                UserFactModel.fact_type == fact_type,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                existing.fact_value = fact_value
                if context:
                    existing.context = context
            else:
                fact = UserFactModel(
                    user_id=user_id,
                    fact_type=fact_type,
                    fact_value=fact_value,
                    context=context,
                )
                session.add(fact)
            await session.commit()

    async def get_user_facts(self, user_id: int) -> dict[str, str]:
        async with self._session_factory() as session:
            from sqlalchemy import select
            stmt = select(UserFactModel).where(UserFactModel.user_id == user_id)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return {row.fact_type: row.fact_value for row in rows}

    async def search_context(self, user_id: int, query: str) -> list[str]:
        async with self._session_factory() as session:
            from sqlalchemy import select
            stmt = (
                select(MessageModel)
                .where(MessageModel.user_id == user_id)
                .order_by(MessageModel.created_at.desc())
                .limit(20)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            results = []
            query_lower = query.lower()
            for row in rows:
                text = f"{row.user_message} {row.bot_response}".lower()
                if query_lower in text or any(word in text for word in query_lower.split()[:3]):
                    results.append(f"Вопрос: {row.user_message}\nОтвет: {row.bot_response}")
            return results[-5:]


db = Database()
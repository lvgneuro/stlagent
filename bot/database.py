from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Column, Integer, String, DateTime, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Session

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
    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = Path("messages.db")
        self._engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self._engine)

    async def save_message(
        self,
        user_id: int,
        username: str | None,
        first_name: str | None,
        user_message: str,
        bot_response: str,
    ) -> None:
        with Session(self._engine) as session:
            msg = MessageModel(
                user_id=user_id,
                username=username,
                first_name=first_name,
                user_message=user_message,
                bot_response=bot_response,
            )
            session.add(msg)
            session.commit()
            logger.info(f"Saved message from user {user_id}")

    async def get_user_messages(self, user_id: int, limit: int = 50) -> list[Message]:
        with Session(self._engine) as session:
            stmt = (
                select(MessageModel)
                .where(MessageModel.user_id == user_id)
                .order_by(MessageModel.created_at.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                Message(
                    user_id=int(row.user_id),
                    username=str(row.username) if row.username else None,
                    first_name=str(row.first_name) if row.first_name else None,
                    user_message=str(row.user_message),
                    bot_response=str(row.bot_response),
                    created_at=datetime.now(timezone.utc) if row.created_at is None else row.created_at,  # type: ignore[arg-type]
                )
                for row in rows
            ]

    async def get_all_users(self) -> list[int]:
        with Session(self._engine) as session:
            stmt = select(MessageModel.user_id).distinct()
            return list(session.execute(stmt).scalars().all())

    async def save_fact(
        self,
        user_id: int,
        fact_type: str,
        fact_value: str,
        context: str | None = None,
    ) -> None:
        with Session(self._engine) as session:
            existing = (
                select(UserFactModel)
                .where(
                    UserFactModel.user_id == user_id,
                    UserFactModel.fact_type == fact_type,
                )
                .first()
            )
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
            session.commit()

    async def get_user_facts(self, user_id: int) -> dict[str, str]:
        with Session(self._engine) as session:
            stmt = select(UserFactModel).where(UserFactModel.user_id == user_id)
            rows = session.execute(stmt).scalars().all()
            return {row.fact_type: row.fact_value for row in rows}

    async def search_context(self, user_id: int, query: str) -> list[str]:
        with Session(self._engine) as session:
            stmt = (
                select(MessageModel)
                .where(MessageModel.user_id == user_id)
                .order_by(MessageModel.created_at.desc())
                .limit(20)
            )
            rows = session.execute(stmt).scalars().all()
            results = []
            query_lower = query.lower()
            for row in rows:
                text = f"{row.user_message} {row.bot_response}".lower()
                if query_lower in text or any(word in text for word in query_lower.split()[:3]):
                    results.append(f"Вопрос: {row.user_message}\nОтвет: {row.bot_response}")
            return results[-5:]


db = Database()
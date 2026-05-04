from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Column, Integer, String, DateTime, create_engine, select
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


db = Database()
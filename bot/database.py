from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Column, BigInteger, Integer, String, DateTime, Text, LargeBinary
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    user_message = Column(String, nullable=False)
    bot_response = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class UserFactModel(Base):
    __tablename__ = "user_facts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    fact_type = Column(String, nullable=False)
    fact_value = Column(String, nullable=False)
    context = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class UserImageModel(Base):
    __tablename__ = "user_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    image_data = Column(LargeBinary, nullable=False)
    file_id = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class SofaModel(Base):
    __tablename__ = "sofas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    category = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    features = Column(Text, nullable=True)
    image_urls = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.now)


@dataclass
class Message:
    user_id: int
    username: str | None
    first_name: str | None
    user_message: str
    bot_response: str
    created_at: datetime


@dataclass
class UserImage:
    id: int
    user_id: int
    image_data: bytes
    file_id: str | None
    description: str | None
    created_at: datetime


@dataclass
class Sofa:
    id: int
    slug: str
    name: str
    url: str
    category: str | None
    description: str | None
    features: str | None
    image_urls: str | None
    updated_at: datetime


class Database:
    def __init__(self) -> None:
        database_url = os.getenv("DATABASE_URL")

        if database_url:
            if "postgresql://" in database_url:
                database_url = database_url.replace(
                    "postgresql://", "postgresql+asyncpg://", 1
                )
            elif "postgres://" in database_url:
                database_url = database_url.replace(
                    "postgres://", "postgresql+asyncpg://", 1
                )
            self._engine = create_async_engine(database_url, echo=False)
        else:
            self._engine = create_async_engine(
                "sqlite+aiosqlite:///messages.db", echo=False
            )

        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def init_db(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

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
                    created_at=datetime.now()
                    if row.created_at is None
                    else row.created_at,
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
                if query_lower in text or any(
                    word in text for word in query_lower.split()[:3]
                ):
                    results.append(
                        f"Вопрос: {row.user_message}\nОтвет: {row.bot_response}"
                    )
            return results[-5:]

    async def get_recent_messages(self, limit: int = 50) -> list[dict]:
        async with self._session_factory() as session:
            from sqlalchemy import select, desc

            stmt = (
                select(MessageModel)
                .order_by(desc(MessageModel.created_at))
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "id": row.id,
                    "user_id": row.user_id,
                    "first_name": row.first_name,
                    "message": row.user_message[:100],
                    "response": row.bot_response[:150],
                    "created_at": row.created_at.isoformat()
                    if row.created_at
                    else None,
                }
                for row in rows
            ]

    async def save_image(
        self,
        user_id: int,
        image_data: bytes,
        file_id: str | None = None,
        description: str | None = None,
    ) -> int:
        async with self._session_factory() as session:
            image = UserImageModel(
                user_id=user_id,
                image_data=image_data,
                file_id=file_id,
                description=description,
            )
            session.add(image)
            await session.commit()
            logger.info(f"Saved image for user {user_id}")
            return image.id

    async def get_user_images(self, user_id: int, limit: int = 20) -> list[UserImage]:
        async with self._session_factory() as session:
            from sqlalchemy import select

            stmt = (
                select(UserImageModel)
                .where(UserImageModel.user_id == user_id)
                .order_by(UserImageModel.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                UserImage(
                    id=row.id,
                    user_id=int(row.user_id),
                    image_data=row.image_data,
                    file_id=str(row.file_id) if row.file_id else None,
                    description=str(row.description) if row.description else None,
                    created_at=datetime.now()
                    if row.created_at is None
                    else row.created_at,
                )
                for row in rows
            ]

    async def get_image_by_id(self, image_id: int, user_id: int) -> UserImage | None:
        async with self._session_factory() as session:
            from sqlalchemy import select

            stmt = select(UserImageModel).where(
                UserImageModel.id == image_id,
                UserImageModel.user_id == user_id,
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                return UserImage(
                    id=row.id,
                    user_id=int(row.user_id),
                    image_data=row.image_data,
                    file_id=str(row.file_id) if row.file_id else None,
                    description=str(row.description) if row.description else None,
                    created_at=datetime.now()
                    if row.created_at is None
                    else row.created_at,
                )
            return None

async def save_sofa(
        self,
        slug: str,
        name: str,
        url: str,
        category: str | None = None,
        description: str | None = None,
        features: str | None = None,
        image_urls: str | None = None,
    ) -> None:
        async with self._session_factory() as session:
            from sqlalchemy import select
            stmt = select(SofaModel).where(SofaModel.slug == slug)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            now = datetime.now()
            logger.info(f"Saving sofa: slug={slug}, name={name}, url={url[:50]}...")
            if existing:
                existing.name = name
                existing.url = url
                existing.category = category
                existing.description = description
                existing.features = features
                existing.image_urls = image_urls
                existing.updated_at = now
            else:
                sofa = SofaModel(
                    slug=slug,
                    name=name,
                    url=url,
                    category=category,
                    description=description,
                    features=features,
                    image_urls=image_urls,
                    updated_at=now,
                )
                session.add(sofa)
            await session.commit()
            logger.info(f"Saved sofa: {name}")

    async def search_sofas(self, query: str, limit: int = 10) -> list[Sofa]:
        async with self._session_factory() as session:
            from sqlalchemy import select

            stmt = (
                select(SofaModel)
                .where(
                    (SofaModel.name.ilike(f"%{query}%"))
                    | (SofaModel.description.ilike(f"%{query}%"))
                    | (SofaModel.category.ilike(f"%{query}%"))
                )
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                Sofa(
                    id=row.id,
                    slug=row.slug,
                    name=str(row.name),
                    url=str(row.url),
                    category=str(row.category) if row.category else None,
                    description=str(row.description) if row.description else None,
                    features=str(row.features) if row.features else None,
                    image_urls=str(row.image_urls) if row.image_urls else None,
                    updated_at=datetime.now()
                    if row.updated_at is None
                    else row.updated_at,
                )
                for row in rows
            ]

    async def get_all_sofas(self, limit: int = 1000) -> list[Sofa]:
        async with self._session_factory() as session:
            from sqlalchemy import select

            stmt = select(SofaModel).order_by(SofaModel.name).limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                Sofa(
                    id=row.id,
                    slug=row.slug,
                    name=str(row.name),
                    url=str(row.url),
                    category=str(row.category) if row.category else None,
                    description=str(row.description) if row.description else None,
                    features=str(row.features) if row.features else None,
                    image_urls=str(row.image_urls) if row.image_urls else None,
                    updated_at=datetime.now()
                    if row.updated_at is None
                    else row.updated_at,
                )
                for row in rows
            ]

    async def get_sofa_count(self) -> int:
        async with self._session_factory() as session:
            from sqlalchemy import select, func

            stmt = select(func.count(SofaModel.id))
            result = await session.execute(stmt)
            return result.scalar() or 0


db = Database()

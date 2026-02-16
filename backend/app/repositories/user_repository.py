"""User repository."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: UUID) -> User | None:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> User | None:
        result = await session.execute(select(User).where(User.email == email))
        return result.scalars().first()

    @staticmethod
    async def create(session: AsyncSession, email: str, hashed_password: str) -> User:
        user = User(email=email, hashed_password=hashed_password)
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user

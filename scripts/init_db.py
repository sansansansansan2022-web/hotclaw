"""Database initialization script. Creates all tables."""

import asyncio
from app.db.session import engine
from app.models.tables import Base


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully.")


if __name__ == "__main__":
    asyncio.run(init_db())

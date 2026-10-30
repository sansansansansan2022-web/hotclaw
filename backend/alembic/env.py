"""Alembic environment configuration for async SQLAlchemy."""

import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from alembic.script import ScriptDirectory

from app.core.config import settings
from app.models.tables import Base
import app.models.wechat_config  # noqa: F401 - register all runtime tables

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        if not inspect(connection).get_table_names():
            # The historical migrations start after the core tables were created.
            # A fresh install needs the current schema before it can be versioned.
            target_metadata.create_all(connection)
            context.get_context().stamp(ScriptDirectory.from_config(config), "head")
            connection.commit()
        else:
            context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

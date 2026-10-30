"""A fresh database must be ready for the backend after Alembic upgrade."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine

from app.services.schema_guard_service import SchemaGuardService


def test_fresh_sqlite_upgrade_is_ready_and_repeatable(tmp_path: Path):
    backend_dir = Path(__file__).resolve().parents[1]
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'fresh.db').as_posix()}"
    env = {**os.environ, "DATABASE_URL": database_url}

    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    engine = create_engine(database_url.replace("+aiosqlite", ""))
    try:
        with engine.connect() as connection:
            report = SchemaGuardService().inspect_connection_schema(connection)
        assert report.is_ready, report.failure_message()
        assert report.current_revisions == report.head_revisions
    finally:
        engine.dispose()

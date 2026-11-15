from __future__ import annotations

from logging.config import fileConfig
import os
import sys
from pathlib import Path

# Make the package importable when Alembic is invoked from account_server/
# itself as well as from backend/.  This keeps the documented migration
# command independent of the caller's current working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alembic import context
from sqlalchemy import engine_from_config, pool

from account_server.database import Base
from account_server import models  # noqa: F401

config = context.config
# The local ini intentionally contains only Alembic settings; application
# logging is configured by the API process.
config.set_main_option("sqlalchemy.url", os.getenv("ACCOUNT_DATABASE_URL", config.get_main_option("sqlalchemy.url")))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


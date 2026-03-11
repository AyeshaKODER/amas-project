# alembic/env.py - functional Alembic environment for this project
from __future__ import with_statement
import os
from logging.config import fileConfig
import logging

from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config

if config.config_file_name:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger('alembic').info(
            "alembic.env: logging config not found or invalid in alembic.ini; using basicConfig fallback"
        )

try:
    from app.db.session import Base
    target_metadata = Base.metadata
except Exception:
    target_metadata = None
    logging.getLogger('alembic').warning(
        "Could not import app.db.session.Base; target_metadata set to None. "
        "If you want autogenerate support, ensure Base is importable from app.db.session."
    )

def get_url():
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Alembic requires it inside the container."
        )
    return url


def run_migrations_offline():
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section) or {}
    if not configuration.get("sqlalchemy.url"):
        configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()




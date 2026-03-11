# alembic/env.py - functional Alembic environment for this project
from __future__ import with_statement
import os
from logging.config import fileConfig
import logging

from sqlalchemy import engine_from_config, pool
from alembic import context

# this is the Alembic Config object, which provides access to the values within the .ini file.
config = context.config

# Configure logging; if alembic.ini contains logging sections this will use them.
if config.config_file_name:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger('alembic').info(
            "alembic.env: logging config not found or invalid in alembic.ini; using basicConfig fallback"
        )

# Import your app's MetaData object here
# Adjust this import if your Base metadata is located elsewhere
try:
    # common pattern: models import Base from app.db.session
    from app.db.session import Base
    target_metadata = Base.metadata
except Exception:
    # Fallback if your project uses a different path, leave None but migrations won't autogenerate
    target_metadata = None
    logging.getLogger('alembic').warning(
        "Could not import app.db.session.Base; target_metadata set to None. "
        "If you want autogenerate support, ensure Base is importable from app.db.session."
    )

def get_url():
    # prefer alembic.ini sqlalchemy.url, otherwise read DATABASE_URL env var
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    return os.environ.get("DATABASE_URL")

def run_migrations_offline():
    """Run migrations in 'offline' mode (generate SQL only)."""
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
    """Run migrations in 'online' mode (apply to DB directly)."""
    connectable = None
    configuration = config.get_section(config.config_ini_section) or {}
    # if sqlalchemy.url isn't set in ini, read from env
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
            compare_type=True,  # detect column type changes if autogenerate used
        )

        with context.begin_transaction():
            context.run_migrations()

# Entry point
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()



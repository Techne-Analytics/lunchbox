import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from lunchbox.db import Base
import lunchbox.models  # noqa: F401 — registers models with Base

config = context.config

# Read DATABASE_URL directly so migrations don't require SECRET_KEY or other app settings
database_url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL is not set and sqlalchemy.url in alembic.ini is empty. "
        "Set DATABASE_URL in your environment or copy .env.example to .env."
    )
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

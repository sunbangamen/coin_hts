"""Alembic environment configuration

This module configures Alembic for database migrations.
It supports both offline and online modes.
"""

from __future__ import with_statement

import os
import logging
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Get the SQLAlchemy metadata from the application
# For now, we'll use target_metadata = None for autogenerate to work
# In the future, we can import ORM models here and set target_metadata = Base.metadata
target_metadata = None

# this is the Alembic Config object, which provides
# the values of the [alembic] section of the alembic.ini
# file as Python dictionary for use in process.py
# file. An environment variable can also be used to override
# the sqlalchemy.url value.
config = context.config

# Interpret the config file for Python dotenv.
dotenv_path = config.get_main_option('dotenv_path')
if dotenv_path is not None:
    import dotenv
    dotenv.load_dotenv(dotenv_path)

# Use DATABASE_URL environment variable if available
database_url = os.environ.get('DATABASE_URL')
if database_url:
    config.set_main_option('sqlalchemy.url', database_url)

# Attach the configuration's fileConfig to the logging module
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section)

    # Get DATABASE_URL from environment if available
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        configuration['sqlalchemy.url'] = database_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

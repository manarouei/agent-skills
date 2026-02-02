from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add parent directory to path so we can import modules
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

# Import your models and config
from database.models import Base
from config import settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override the sqlalchemy.url with our application's settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set metadata to your SQLAlchemy models
target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    # Use the async compatible version if you're using AsyncSession
    if settings.DATABASE_URL.startswith("postgresql+asyncpg"):
        # Handle async engine by stripping the +asyncpg part for Alembic
        synchronous_url = settings.DATABASE_URL.replace(
            "postgresql+asyncpg", "postgresql+psycopg"
        )
        
        connectable = engine_from_config(
            {"url": synchronous_url},
            prefix="",
            poolclass=pool.NullPool,
        )
    else:
        # Regular synchronous engine
        connectable = engine_from_config(
            config.get_section(config.config_ini_section),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            # Support PostgreSQL-specific column types
            compare_type=True,
            # Include schemas beyond the default public schema
            include_schemas=False,
            # Generate more-optimal UPDATE statements for table changes
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
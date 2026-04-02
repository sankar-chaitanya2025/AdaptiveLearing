import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 1. Setup Path so Alembic can find your 'database.py' and 'models/'
# This looks one folder up from the alembic folder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 2. Import your Database Base and ALL Models
# Importing models here is what makes 'autogenerate' work!
from database import Base, DATABASE_URL
# Import ALL models so autogenerate detects every table and column.
from models import (  # noqa: F401  (side-effects: registers mappers with Base.metadata)
    User,
    CapabilityVector,
    Problem,
    Submission,
    Session,
    PlatoLog,   # Stage 9 extended model
    StudyMetric,
    # Stage 12 study module
    StudyTestSession,
    StudyTestSubmission,
    StudyConfidenceSurvey,
    # Stage 13 fatigue detection
    FatigueEvent,
)
from models.dialogue import DialogueSession  # Stage 8 model

config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_url():
    """
    Smart URL logic:
    1. Grabs the URL from your database.py or environment.
    2. If running on Windows (localhost), it fixes the 'postgres' host name.
    3. Ensures the psycopg2 driver is specified.
    """
    url = os.environ.get("DATABASE_URL", DATABASE_URL)
    
    # Bridge: If we are running migrations from Windows but the DB is in Docker
    # We must talk to localhost:5432, not the service name 'postgres'
    if "postgres:5432" in url and os.name == 'nt':
        url = url.replace("postgres:5432", "localhost:5432")
    
    # Ensure the driver is correct
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://")
        
    return url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        # Added safeguard for UUID extension if needed by your schema
        context.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Build the configuration dict manually to override the 'placeholder'
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    
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
            context.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
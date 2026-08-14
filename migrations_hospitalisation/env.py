from __future__ import annotations
import sys
from logging.config import fileConfig
from pathlib import Path
from alembic import context
from sqlalchemy import create_engine, pool

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path: sys.path.insert(0, str(ROOT_DIR))
from database.hospitalisation_base import HospitalisationBase
from services.hospitalisation.config import DATABASE_URL
from services.hospitalisation import models  # noqa: F401

config = context.config
if config.config_file_name is not None: fileConfig(config.config_file_name)
target_metadata = HospitalisationBase.metadata

def run_migrations_offline():
    context.configure(url=DATABASE_URL.render_as_string(hide_password=False), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle":"named"}, compare_type=True)
    with context.begin_transaction(): context.run_migrations()

def run_migrations_online():
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        connection.exec_driver_sql("SET time_zone = '+00:00'")
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction(): context.run_migrations()

if context.is_offline_mode(): run_migrations_offline()
else: run_migrations_online()

"""Alembic environment. URL is injected by prompt_studio.db.run_migrations."""

from alembic import context
from sqlalchemy import create_engine, pool

from prompt_studio.models import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()  # end the implicit transaction so Alembic's own transaction is the outer one
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline SQL generation is not supported")
run_migrations_online()

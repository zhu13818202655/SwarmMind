"""SwarmMind Alembic environment.

Loads the database URL from :class:`SwarmMindConfig` (falling back to the
``SWARMMIND_POSTGRES__DSN`` / ``POSTGRES_DSN`` / ``DATABASE_URL`` env vars
or the alembic.ini override) so ops only ever maintain *one* DSN source.

We do **not** use SQLAlchemy ORM models — the project's storage layer is
plain DDL + JSONB. ``target_metadata`` is therefore ``None`` and migration
authors hand-roll DDL with :mod:`alembic.op`. ``--autogenerate`` is not
supported (and intentionally so: it would overwrite the JSONB schema).
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool


config = context.config

if config.config_file_name is not None:  # pragma: no branch - alembic guarantees
    fileConfig(config.config_file_name)


def _resolve_database_url() -> str:
    """Resolve the SQLAlchemy URL from settings + env, in priority order."""
    # 1. explicit -x url=... on the alembic CLI
    cmd_kwargs = context.get_x_argument(as_dictionary=True)
    if "url" in cmd_kwargs:
        return _ensure_sqlalchemy_url(cmd_kwargs["url"])

    # 2. alembic.ini sqlalchemy.url (kept blank in checked-in file)
    cfg_url = config.get_main_option("sqlalchemy.url") or ""
    if cfg_url:
        return _ensure_sqlalchemy_url(cfg_url)

    # 3. SwarmMind settings (already merges defaults + YAML + env vars)
    try:
        from swarmmind.config import get_settings

        settings = get_settings()
        return _ensure_sqlalchemy_url(settings.postgres.dsn)
    except Exception:  # pragma: no cover - bootstrap fallback
        pass

    # 4. raw env vars as a last resort
    for key in ("SWARMMIND_POSTGRES__DSN", "POSTGRES_DSN", "DATABASE_URL"):
        value = os.environ.get(key)
        if value:
            return _ensure_sqlalchemy_url(value)

    raise RuntimeError(
        "Cannot resolve database URL for Alembic. Set SWARMMIND_POSTGRES__DSN "
        "or pass `-x url=postgresql+psycopg://...`."
    )


def _ensure_sqlalchemy_url(dsn: str) -> str:
    """Normalise a libpq-style DSN to a SQLAlchemy URL using psycopg3."""
    if dsn.startswith("postgresql+"):
        return dsn
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://"):]
    if dsn.startswith("postgresql://"):
        return "postgresql+psycopg://" + dsn[len("postgresql://"):]
    return dsn


# No declarative metadata — migrations are hand-written DDL.
target_metadata = None


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of executing it (``alembic upgrade --sql``)."""
    url = _resolve_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=False,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the configured database and apply migrations."""
    url = _resolve_database_url()
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = url
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

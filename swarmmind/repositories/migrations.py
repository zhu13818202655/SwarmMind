"""Programmatic Alembic runner used by the application bootstrap.

The platform runs ``alembic upgrade head`` automatically when
``settings.postgres.auto_init_schema`` is true. We deliberately do not
call the ``alembic`` CLI here — going through the Python API gives us:

- A single resolution path for the DSN (the active SwarmMindConfig).
- Easier error handling / logging in lifespan / DI code.
- The ability to call from sync *or* async contexts via
  :func:`asyncio.to_thread` without subprocess overhead.

For ad-hoc operator use (offline SQL dump, history, downgrade) the
``alembic`` CLI continues to work because it shares the same
``alembic.ini`` and ``alembic/env.py``.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Final

from alembic import command
from alembic.config import Config


logger = logging.getLogger(__name__)


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
ALEMBIC_INI_PATH: Final[Path] = PROJECT_ROOT / "alembic.ini"
ALEMBIC_SCRIPT_LOCATION: Final[Path] = PROJECT_ROOT / "alembic"


def _build_config(dsn: str | None = None) -> Config:
    """Build an :class:`alembic.config.Config` pointed at the repo's ini."""
    if not ALEMBIC_INI_PATH.is_file():
        raise FileNotFoundError(
            f"alembic.ini not found at {ALEMBIC_INI_PATH}; "
            "is the package installed in editable mode?"
        )
    cfg = Config(str(ALEMBIC_INI_PATH))
    # Force the script location to the absolute path so the runtime works
    # regardless of the cwd a uvicorn worker happened to land in.
    cfg.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    if dsn:
        cfg.cmd_opts = None  # type: ignore[assignment]
        cfg.attributes["x"] = {"url": dsn}
        # ``-x url=...`` semantics: env.py reads context.get_x_argument()
        cfg.set_main_option("sqlalchemy.url", "")
        # Older alembics expect the dict on ``cmd_opts``; new ones honour
        # ``attributes``. We set both via the documented hook below.
        from argparse import Namespace

        cfg.cmd_opts = Namespace(x=[f"url={dsn}"])
    return cfg


def upgrade_head_sync(dsn: str | None = None) -> None:
    """Apply all pending migrations up to ``head`` (blocking)."""
    cfg = _build_config(dsn)
    logger.info(
        "alembic.upgrade_head_start",
        extra={"script_location": str(ALEMBIC_SCRIPT_LOCATION)},
    )
    command.upgrade(cfg, "head")
    logger.info("alembic.upgrade_head_done")


def downgrade_base_sync(dsn: str | None = None) -> None:
    """Drop every object created by the baseline migration (blocking).

    Used by the test harness to keep PG round-trip tests hermetic.
    """
    cfg = _build_config(dsn)
    command.downgrade(cfg, "base")


def current_revision_sync(dsn: str | None = None) -> str | None:
    """Return the database's current revision id, or ``None`` if unstamped."""
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    target = dsn
    if target is None:
        from swarmmind.config import get_settings

        target = get_settings().postgres.dsn
    sa_url = _to_sqlalchemy_url(target)
    engine = create_engine(sa_url, future=True)
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            return ctx.get_current_revision()
    finally:
        engine.dispose()


def _to_sqlalchemy_url(dsn: str) -> str:
    if dsn.startswith("postgresql+"):
        return dsn
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://"):]
    if dsn.startswith("postgresql://"):
        return "postgresql+psycopg://" + dsn[len("postgresql://"):]
    return dsn


async def upgrade_head(dsn: str | None = None) -> None:
    """Async-friendly wrapper around :func:`upgrade_head_sync`."""
    await asyncio.to_thread(upgrade_head_sync, dsn)


async def current_revision(dsn: str | None = None) -> str | None:
    """Async-friendly wrapper around :func:`current_revision_sync`."""
    return await asyncio.to_thread(current_revision_sync, dsn)


__all__ = [
    "ALEMBIC_INI_PATH",
    "ALEMBIC_SCRIPT_LOCATION",
    "current_revision",
    "current_revision_sync",
    "downgrade_base_sync",
    "upgrade_head",
    "upgrade_head_sync",
]

# Alembic versions directory.
#
# Each migration is a Python module named
# ``YYYYMMDD_HHMM_<slug>.py`` containing ``upgrade()`` / ``downgrade()``.
#
# Conventions:
# - Always hand-write DDL (do **not** rely on autogenerate).
# - Make every operation idempotent where reasonable
#   (``op.execute("CREATE INDEX IF NOT EXISTS ...")``) so that re-running
#   against partially-migrated databases is safe.
# - Add new tables / columns in a *new* revision; never edit a released one.

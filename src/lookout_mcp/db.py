"""Bootstrap database CLI placeholders.

The domain/data-model phase will add real SQL migrations and deterministic seed data. These
commands exist now so the repository has stable setup scripts from the first phase.
"""

from __future__ import annotations

import argparse
import sqlite3

from lookout_mcp.config import load_config


def migrate() -> None:
    """Create the SQLite file and enable baseline connection settings."""

    config = load_config()
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS _lookout_bootstrap "
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT OR REPLACE INTO _lookout_bootstrap (key, value) VALUES (?, ?)",
            ("schema_phase", "bootstrap"),
        )


def seed() -> None:
    """Run the bootstrap seed step.

    Real deterministic BI seed data is intentionally deferred to the domain/data-model phase.
    """

    migrate()


def main() -> None:
    parser = argparse.ArgumentParser(prog="lookout-db")
    parser.add_argument("command", choices=("migrate", "seed"))
    args = parser.parse_args()

    if args.command == "migrate":
        migrate()
    else:
        seed()


if __name__ == "__main__":
    main()

"""Verify currency migration ONLY in an explicitly named isolated test database.

Restore a private pre-conversion backup into that DB first. Never points the
migration at the configured application DB. Prints no records or credentials.
"""

import argparse
import os
import subprocess
from decimal import Decimal
from pathlib import Path

from backend.app.core.config import get_settings
from backend.app.db import models  # noqa: F401
from backend.app.db.base import Base
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine, make_url


def state(engine: Engine, money_columns: dict[str, tuple[str, ...]]) -> dict:
    result = {}
    with engine.connect() as connection:
        for name, names in money_columns.items():
            table = Base.metadata.tables[name]
            controls = [
                c
                for c in table.c
                if c.name
                in {
                    "percentage",
                    "quantity",
                    "exam_count",
                    "session_count",
                    "grade",
                    "academic_year",
                }
            ]
            rows = connection.execute(
                select(table.c.id, *(table.c[c] for c in names), *controls)
            ).mappings()
            result[name] = {str(row["id"]): dict(row) for row in rows}
        discount = Base.metadata.tables["school_discount_codes"]
        result["school_discount_codes"] = {
            str(row.id): row.percentage
            for row in connection.execute(select(discount.c.id, discount.c.percentage))
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    source = make_url(get_settings().DATABASE_URL)
    if (
        not args.database.startswith("azari_toman_")
        or "test" not in args.database
        or args.database == source.database
        or not args.database.replace("_", "").isalnum()
    ):
        raise RuntimeError("Only an isolated azari_toman_*test* database may be verified")
    target = source.set(database=args.database)
    engine = create_engine(target)
    import runpy

    migration = runpy.run_path(
        str(Path(__file__).parents[1] / "alembic/versions/20261021_0032_toman_currency.py")
    )
    inventory = migration["MONEY_COLUMNS"]
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    if revision != "20261020_0031":
        raise RuntimeError("Restore a revision 0031 backup into the isolated DB before testing")
    before = state(engine, inventory)
    env = dict(os.environ, DATABASE_URL=target.render_as_string(hide_password=False))
    command = ["alembic", "-c", str(Path(__file__).parents[1] / "alembic.ini")]
    subprocess.run([*command, "upgrade", "head"], env=env, check=True)
    after = state(engine, inventory)
    for name, columns in inventory.items():
        assert set(before[name]) == set(after[name]), "Record IDs/counts changed"
        for key, old in before[name].items():
            for column, value in old.items():
                expected = (
                    value / Decimal("10") if column in columns and value is not None else value
                )
                assert after[name][key][column] == expected, f"Mismatch: {name}.{column}"
    assert before["school_discount_codes"] == after["school_discount_codes"], (
        "Discount rates changed"
    )
    subprocess.run([*command, "upgrade", "head"], env=env, check=True)
    assert state(engine, inventory) == after, "Repeated upgrade converted amounts twice"
    subprocess.run([*command, "check"], env=env, check=True)
    print(
        "PASS: all 62 monetary columns divided exactly once; "
        "IDs, counts, grades, years and rates preserved"
    )
    engine.dispose()


if __name__ == "__main__":
    main()

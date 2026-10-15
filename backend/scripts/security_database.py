"""Inspect database exposure; optionally deny direct Supabase browser-role access.

The app authenticates through FastAPI, not Supabase Auth. Browser database roles
must therefore have no direct access. This does not replace tenant-scoped API
authorization. Never prints the database URL or credentials.
"""

import argparse
import json

from backend.app.db import models  # noqa: F401 - populate application metadata.
from backend.app.db.base import Base
from backend.app.db.database import engine
from sqlalchemy import text


def inspect_database(harden: bool = False) -> int:
    if engine.dialect.name != "postgresql":
        raise ValueError("This check requires PostgreSQL")
    with engine.begin() as connection:
        roles = list(
            connection.execute(
                text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
            ).scalars()
        )
        tables = [
            name
            for name in Base.metadata.tables
            if connection.scalar(
                text("SELECT to_regclass(:name) IS NOT NULL"), {"name": "public." + name}
            )
        ]
        role_info = connection.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
        quote = connection.dialect.identifier_preparer.quote_identifier
        if harden and roles:
            # Default-deny RLS must not accidentally lock the API out. Require
            # the deployment's server connection to own the tables or bypass RLS.
            owns_all = all(
                connection.scalar(
                    text(
                        "SELECT pg_get_userbyid(relowner) = current_user FROM pg_class "
                        "WHERE oid = to_regclass(:table)"
                    ),
                    {"table": "public." + name},
                )
                for name in tables
            )
            if not (role_info.rolsuper or role_info.rolbypassrls or owns_all):
                raise ValueError(
                    "Use a reviewed server owner connection before hardening browser roles"
                )
            for name in tables:
                qualified = f"public.{quote(name)}"
                for role in roles:
                    connection.execute(
                        text(f"REVOKE ALL PRIVILEGES ON TABLE {qualified} FROM {quote(role)}")
                    )
                connection.execute(text(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY"))
        exposure = []
        for role in roles:
            for name in tables:
                if connection.scalar(
                    text(
                        "SELECT has_table_privilege(:role, :table, "
                        "'SELECT, INSERT, UPDATE, DELETE')"
                    ),
                    {"role": role, "table": "public." + name},
                ):
                    exposure.append({"role": role, "table": name})
        print(
            json.dumps(
                {
                    "application_tables_checked": len(tables),
                    "browser_roles": roles,
                    "direct_browser_grants": exposure,
                    "server_role_is_superuser": role_info.rolsuper,
                    "server_role_bypasses_rls": role_info.rolbypassrls,
                    "hardened_browser_roles": harden and bool(roles),
                },
                indent=2,
            )
        )
        return 1 if exposure else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harden-supabase", action="store_true")
    raise SystemExit(inspect_database(parser.parse_args().harden_supabase))

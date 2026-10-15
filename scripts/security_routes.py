"""Inventory FastAPI authentication dependencies without connecting to the database."""

import json

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from backend.app.api.dependencies import get_current_user
from backend.app.main import app

PUBLIC = {
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/register"),
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/ready"),
}


def authenticated(dependency: Dependant) -> bool:
    return dependency.call is get_current_user or any(
        authenticated(child) for child in dependency.dependencies
    )


def inventory() -> list[dict[str, object]]:
    # FastAPI versions represent included routers either as flattened APIRoutes
    # or lazy effective contexts. Inspect both; tests reject an empty inventory.
    effective = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            effective.append(route)
        elif callable(contexts := getattr(route, "effective_route_contexts", None)):
            effective.extend(
                context
                for context in contexts()
                if isinstance(context.original_route, APIRoute)
            )
    return [
        {
            "method": method,
            "path": route.path,
            "authenticated": authenticated(route.dependant),
            "intentionally_public": (method, route.path) in PUBLIC,
        }
        for route in effective
        for method in sorted(route.methods)
    ]


if __name__ == "__main__":
    routes = inventory()
    print(json.dumps(routes, indent=2))
    if not routes:
        raise SystemExit("No API routes inspected; refusing a false pass")
    raise SystemExit(
        int(
            any(
                not row["authenticated"] and not row["intentionally_public"]
                for row in routes
            )
        )
    )

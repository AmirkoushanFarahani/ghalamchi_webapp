"""Check this Python environment against the official PyPI vulnerability feed.

Read-only fallback when pip-audit cannot be installed. Any unavailable advisory
lookup fails the command rather than being reported as a clean audit.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import distributions
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen


def inspect_package(package: tuple[str, str]) -> dict[str, object]:
    name, version = package
    url = f"https://pypi.org/pypi/{quote(name, safe='')}/{quote(version, safe='')}/json"
    try:
        with urlopen(url, timeout=20) as response:
            data = json.load(response)
        return {
            "package": name,
            "version": version,
            "advisories": [
                {
                    "id": item["id"],
                    "fixed_in": item.get("fixed_in", []),
                    "link": item.get("link"),
                }
                for item in data.get("vulnerabilities", [])
                if not item.get("withdrawn")
            ],
        }
    except HTTPError as exc:
        if exc.code == 404 and name == "azari-accounting-backend":
            return {
                "package": name,
                "version": version,
                "local_project": True,
                "advisories": [],
            }
        return {
            "package": name,
            "version": version,
            "error": f"advisory HTTP {exc.code}",
        }
    except (OSError, ValueError):
        return {
            "package": name,
            "version": version,
            "error": "advisory lookup unavailable",
        }


def main() -> int:
    packages = sorted(
        {(item.metadata["Name"], item.version) for item in distributions()}
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(inspect_package, packages))
    findings = [item for item in results if item.get("advisories") or item.get("error")]
    print(
        json.dumps(
            {
                "source": "PyPI version vulnerability feed",
                "packages_checked": len(packages),
                "findings": findings,
            },
            indent=2,
        )
    )
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

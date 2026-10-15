"""Bounded, unauthenticated GET checks tailored to Azari's same-origin deployment.

Only use against an application you own or are authorized to test. No login
attempts, payload injection, writes, credentials, or response bodies are recorded.
This is not an authorization/tenant-isolation audit or penetration test.
"""

import argparse
import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_BODY = 1_048_576
SENSITIVE_PATHS = (
    "/.env",
    "/.env.production",
    "/.git/config",
    "/backup.sql",
    "/dump.sql",
    "/backups/",
    "/backend/pyproject.toml",
    "/scripts/",
    "/security/",
    "/assets/security-probe.js.map",
)
PROTECTED_PATHS = (
    "/api/v1/auth/me",
    "/api/v1/users",
    "/api/v1/school/students",
    "/api/v1/school/costs",
    "/api/v1/school/institutes/comparison",
    "/api/v1/dashboard",
)


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url: str, origin: str | None = None) -> Response:
    headers = {"User-Agent": "Azari-Security-Check/1.0", "Accept": "*/*"}
    if origin:
        headers["Origin"] = origin
    request = Request(url, headers=headers)
    try:
        response = build_opener(NoRedirect()).open(request, timeout=8)
    except HTTPError as exc:
        response = exc
    with response:
        return Response(
            response.status,
            {key.lower(): value for key, value in response.headers.items()},
            response.read(MAX_BODY),
        )


def csp_issues(policy: str) -> list[str]:
    directives = {
        words[0]: words[1:]
        for part in policy.split(";")
        if (words := part.strip().split())
    }
    issues = []
    for name in ("default-src", "base-uri", "form-action", "frame-ancestors"):
        if not directives.get(name) or "*" in directives[name]:
            issues.append(name)
    script = directives.get("script-src", directives.get("default-src", []))
    if not script or any(
        item
        in {
            "'unsafe-inline'",
            "'unsafe-eval'",
            "*",
            "data:",
            "blob:",
            "http:",
            "https:",
        }
        or "*" in item
        for item in script
    ):
        issues.append("script-src")
    if directives.get("object-src") != ["'none'"]:
        issues.append("object-src")
    for name in ("connect-src", "frame-src"):
        if "*" in directives.get(name, []):
            issues.append(name)
    return issues


def sensitive_response(response: Response) -> bool:
    if response.status in {403, 404}:
        return False
    # A SPA fallback is not a leaked .env. Never print the body when detecting one.
    text = response.body.decode("utf-8", errors="replace")
    return bool(
        re.search(
            r"(?im)^\s*(?:DATABASE_URL|JWT_SECRET|POSTGRES_PASSWORD)\s*=|"
            r"\[core\]|CREATE TABLE|PostgreSQL database dump|Index of /|"
            r'"version"\s*:\s*3\s*[,}]',
            text,
        )
    )


def scan(base: str, development: bool = False) -> list[dict[str, str]]:
    parsed = urlsplit(base)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError(
            "Use a plain http(s) origin without credentials, path or query"
        )
    base = base.rstrip("/")
    results: list[dict[str, str]] = []

    def record(check: str, status: str, detail: str) -> None:
        results.append({"check": check, "status": status, "detail": detail})

    landing = fetch(base + "/")
    if landing.status != 200:
        record("homepage", "FAIL", f"HTTP {landing.status}; redirects are not followed")
        return results
    record("homepage", "PASS", "HTTP 200")
    record("https", "PASS" if parsed.scheme == "https" else "WARN", parsed.scheme)
    targets = [("HTML", landing)]
    match = re.search(rb'<script[^>]+src=["\']([^"\']+)["\']', landing.body)
    if match:
        asset = urljoin(base + "/", match[1].decode("utf-8"))
        if (
            urlsplit(asset).netloc == parsed.netloc
            and urlsplit(asset).scheme == parsed.scheme
        ):
            targets.append(("JavaScript", fetch(asset)))
            mapped = fetch(asset.split("?", 1)[0] + ".map")
            record(
                "bundle-source-map",
                "FAIL" if sensitive_response(mapped) else "PASS",
                "No source-map contents recorded",
            )
    if len(targets) == 1:
        record(
            "static-asset",
            "WARN",
            "No same-origin script located; check assets manually",
        )
    for label, response in targets:
        record(
            f"{label}:served",
            "PASS" if response.status == 200 else "FAIL",
            f"HTTP {response.status}",
        )
        required = {
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
        }
        for name, value in required.items():
            passed = response.headers.get(name, "").lower() == value.lower()
            record(
                f"{label}:{name}", "PASS" if passed else "FAIL", "Header value checked"
            )
        record(
            f"{label}:referrer-policy",
            "PASS"
            if response.headers.get("referrer-policy")
            in {"no-referrer", "strict-origin", "strict-origin-when-cross-origin"}
            else "FAIL",
            "Header value checked",
        )
        issues = csp_issues(response.headers.get("content-security-policy", ""))
        record(
            f"{label}:CSP",
            "FAIL" if issues else "PASS",
            ", ".join(issues) or "Strict baseline",
        )
        if parsed.scheme == "https":
            hsts = response.headers.get("strict-transport-security", "").lower()
            age = re.search(r"max-age\s*=\s*(\d+)", hsts)
            passed = bool(
                age and int(age[1]) >= 31536000 and "includesubdomains" in hsts
            )
            record(f"{label}:HSTS", "PASS" if passed else "FAIL", "HTTPS HSTS checked")
    for path in SENSITIVE_PATHS:
        response = fetch(base + path)
        status = (
            "FAIL"
            if sensitive_response(response)
            else ("PASS" if response.status in {403, 404} else "WARN")
        )
        record(path, status, f"HTTP {response.status}; body never recorded")
    for path in PROTECTED_PATHS:
        response = fetch(base + path)
        record(
            path,
            "PASS" if response.status == 401 else "FAIL",
            f"HTTP {response.status}",
        )
        if path.endswith("/me"):
            record(
                "API:no-store",
                "PASS"
                if response.headers.get("cache-control") == "no-store"
                else "FAIL",
                "Authentication response cache policy",
            )
    for path in ("/docs", "/redoc", "/openapi.json"):
        response = fetch(base + path)
        is_docs = (
            b"openapi" in response.body.lower() or b"swagger" in response.body.lower()
        )
        record(
            path,
            ("WARN" if development else "FAIL")
            if response.status == 200 and is_docs
            else "PASS",
            f"HTTP {response.status}",
        )
    for path in ("/", "/api/v1/auth/me"):
        response = fetch(base + path, origin="https://untrusted.invalid")
        unsafe = response.headers.get("access-control-allow-origin") in {
            "*",
            "https://untrusted.invalid",
        }
        record(
            f"CORS:{path}", "FAIL" if unsafe else "PASS", "Untrusted origin not allowed"
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--development", action="store_true", help="Allow development API docs"
    )
    args = parser.parse_args()
    try:
        results = scan(args.url, args.development)
    except (ValueError, URLError, TimeoutError, OSError):
        # Exceptions can include user-info or response details. Do not echo them.
        results = [
            {
                "check": "connection",
                "status": "FAIL",
                "detail": "Invalid origin or unavailable target",
            }
        ]
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for item in results:
            print(f"{item['status']:4} {item['check']}: {item['detail']}")
    return int(any(item["status"] == "FAIL" for item in results))


if __name__ == "__main__":
    raise SystemExit(main())

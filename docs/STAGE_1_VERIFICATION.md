# Stage 1 Verification

Verification date: 2026-08-17

## Current result

Stage 1 is **PASS**. The repository build-context defect is fixed, both Docker
images build successfully, and the complete three-service Compose stack is
running. PostgreSQL is healthy, the backend is reachable on port 8000, and the
frontend is reachable on approved host port 4173 while retaining container
port 80.

Stage 2 has not started.

## Build-context diagnosis and correction

The backend service uses the repository root as its context:

```yaml
build:
  context: .
  dockerfile: backend/Dockerfile
```

There was no root `.dockerignore`. Docker therefore attempted to traverse every
artifact under the repository, including `backend/.pytest_cache`, and Windows
denied access while the client was assembling the context. A hypothetical
`backend/.dockerignore` would not have applied because `backend/` is not the
context root.

The correction adds:

- root `.dockerignore` for the backend's repository-root context;
- `frontend/.dockerignore` for the frontend's separate context;
- exclusions for Python caches, coverage, virtual environments, egg metadata,
  secrets, Git metadata, frontend dependencies, and build output;
- an explicit root-context exclusion for `frontend/`, since the backend image
  only copies `backend/` and `ml/`;
- `npm ci` in the frontend image so the committed lockfile drives installation.

No cache directory was manually deleted to obtain the result;
`backend/.pytest_cache` still exists on the host and is successfully ignored.
Backend and ML source remain in the backend context. Frontend source, manifests,
lockfile, and Nginx configuration remain in the frontend context.

## Command results

### Docker installation

- `docker --version`: Docker 29.7.2
- `docker compose version`: Docker Compose v5.4.0
- Docker daemon access: verified when run with the required host permissions

### Compose configuration

`docker compose config` completed successfully after the ignore-file changes.
Resolved secrets are intentionally not reproduced in this document.

### Foreground build and startup

`docker compose up --build` was run without `-d`.

Build evidence from the uncached run:

- backend `.dockerignore` transfer: 469 B;
- backend build context transfer: 7.51 kB;
- frontend `.dockerignore` transfer: 171 B;
- frontend build context transfer: 69.09 kB;
- backend dependency installation inside Python 3.12 image: successful;
- backend image: built successfully;
- frontend `npm ci` and Vite production build: successful;
- frontend Nginx image: built successfully.

After the final ignore/Dockerfile refinement, the required foreground command
was repeated. Docker transferred only 1.09 kB for the backend context and 827 B
for the frontend context; `npm ci`, TypeScript checking, and the Vite build all
completed successfully. It then reached the same host port rejection.

This demonstrates that the ignore rules do not remove dependency manifests or
application source required by either image.

Runtime evidence before the frontend bind failure:

- PostgreSQL container: running and `healthy` according to `pg_isready`;
- backend container: running with host mapping `8000:8000`;
- `GET http://localhost:8000/api/v1/health`: HTTP 200 with status `ok`;
- frontend container: created but not started;
- `http://localhost:5173`: not reachable.

The foreground Compose command ended with:

```text
ports are not available ... listen tcp 0.0.0.0:5173:
An attempt was made to access a socket in a way forbidden by its access permissions.
```

## Initial port 5173 diagnosis

No process was listening on port 5173. Windows reported this excluded TCP range:

```text
Start Port  End Port
5141        5240
```

Port 5173 falls inside that range. Direct bind tests to both `127.0.0.1:5173`
and `[::1]:5173` failed with the same access-permission error. Therefore, this
is an OS host-port reservation rather than a Dockerfile, Compose syntax, or
application failure.

## Port 5174 re-verification

The repository-wide search identified `compose.yaml` as the only source of the
Docker host mapping. It was changed from `5173:80` to `5174:80`; the container
port remains 80. The actual `.env` and example CORS origins, Vite development
port, and live-access documentation were aligned to `http://localhost:5174`.

`docker compose config` then rendered:

```text
published: "5174"
target: 80
```

There was no override retaining 5173. After `docker compose down`, the required
foreground `docker compose up --build` rebuilt both images and reached frontend
startup, but Windows rejected the correctly rendered mapping:

```text
listen tcp 0.0.0.0:5174: bind:
An attempt was made to access a socket in a way forbidden by its access permissions.
```

Final `docker compose ps -a` and host probes showed:

- PostgreSQL: running and healthy;
- backend: running on `8000:8000`;
- backend health endpoint: HTTP 200;
- frontend: created but not started;
- `http://localhost:5174`: not reachable.

Port 5174 is also inside the Windows excluded range 5141-5240. This second
failure confirms the configured mapping changed correctly and that the
remaining blocker is external to the repository.

## Final port 4173 verification

The approved host mapping is now `4173:80`. Active host URL references were
updated to `http://localhost:4173`; historical 5173/5174 failure records above
were intentionally retained.

`docker compose config` rendered:

```text
frontend published: "4173"
frontend target: 80
backend published: "8000"
backend target: 8000
```

`docker compose down` completed, followed by foreground
`docker compose up --build` without `-d`. The build completed and remained
attached with all services running. Final `docker compose ps` reported:

- PostgreSQL: Up and healthy;
- backend: Up with `8000:8000`;
- frontend: Up with `4173:80`.

Host verification:

- `GET http://localhost:8000/api/v1/health`: HTTP 200, JSON response;
- `GET http://localhost:4173`: HTTP 200, HTML application shell.

Quality verification:

- pytest: 3 passed;
- Ruff: all checks passed;
- strict mypy: no issues in 13 source files;
- frontend TypeScript/Vite production build: passed, 30 modules transformed.

Stage 1 therefore passes its complete runtime and quality gate. Stage 2 has not
started.

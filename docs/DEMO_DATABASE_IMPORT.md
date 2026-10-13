# Import the school demo on the server

The committed snapshot `backend/scripts/data/demo_database.json.gz.b64` is a
gzip-compressed JSON export encoded as text. It contains only the school demo:
three demo users, two institutes, synthetic students, enrollments, payments,
course catalogs, exam/book plans, and demo costs. It excludes stored password
hashes, non-demo user accounts, audit history, and deployment secrets.

## Before importing

Deploy the latest code and apply Alembic migrations to the server database.
The import runs using the backend's configured `DATABASE_URL`. It does not copy
your local `.env`. It refuses to overwrite existing demo accounts or record IDs.
All inserts occur in one transaction; a failure rolls them back.

## Docker server

Docker now imports the demo automatically at startup after migrations and role
bootstrap. Set `DEMO_IMPORT_PASSWORD` in the server environment to a private
password of 12–128 characters, then rebuild/redeploy from GitHub. It imports into
the database specified by `DATABASE_URL`, not a database baked into the image.
All three demo accounts receive the password you set. Future restarts skip the
import and preserve existing passwords, edits, and data. Remove the environment
variable after the first successful import if desired.

No separate import command is needed for normal Docker deployment. The following
command remains available for a manual import:

Replace `YOUR_BACKEND_CONTAINER` with the actual server container name. Run on
the server, not the local computer:

```sh
docker exec -it YOUR_BACKEND_CONTAINER python -c "import getpass,os; os.environ['DEMO_IMPORT_PASSWORD']=getpass.getpass('New demo password (12+ characters): '); from backend.scripts.demo_database import import_demo; import_demo()"
```

The prompt hides your input. Use a new private password of 12–128 characters.
All demo accounts receive this password. No password is stored in GitHub.

## Python server without Docker

From the repository root, with the backend environment and database settings:

```sh
python -c "import getpass,os; os.environ['DEMO_IMPORT_PASSWORD']=getpass.getpass('New demo password (12+ characters): '); from backend.scripts.demo_database import import_demo; import_demo()"
```

## Accounts

- Manager: `demo.school.manager2@example.com`
- Secretary: `demo.school.secretary2@example.com`
- Secretary: `demo.school.secretary3@example.com`

Their original institute assignments are preserved. Use the password you chose
at the import prompt. The old local password is not transferred.

This is a demo-data transfer, not a backup of the entire database. Automatic
startup import requires `DEMO_IMPORT_PASSWORD` to be configured on the server.

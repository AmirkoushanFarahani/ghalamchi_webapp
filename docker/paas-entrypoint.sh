#!/bin/sh
set -eu

: "${PORT:=8080}"
export PORT

# PaaS providers usually inject PORT at runtime. Render the server block then
# run the application as an unprivileged user through Supervisor.
envsubst '${PORT}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

if [ "${RUN_MIGRATIONS}" = "true" ]; then
  su --shell /bin/sh azari --command \
    "alembic -c /app/backend/alembic.ini upgrade head"
  su --shell /bin/sh azari --command \
    "python -m backend.app.db.bootstrap"
fi

exec supervisord --nodaemon --configuration /etc/supervisor/supervisord.conf

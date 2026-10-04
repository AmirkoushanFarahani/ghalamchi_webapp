# Production image for PaaS providers that deploy one public container.
# It serves the React SPA and proxies /api/v1 to FastAPI on the same origin.

FROM node:22-alpine AS frontend-build

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./

# Keep API calls on the public application's own origin. Nginx proxies them
# internally, so no public backend URL is embedded in the JavaScript bundle.
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    RUN_MIGRATIONS=true

WORKDIR /app

# nginx serves the SPA, supervisor keeps nginx and uvicorn alive, and envsubst
# writes the PaaS-assigned port into nginx's configuration at container start.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends nginx supervisor gettext-base \
    && rm -rf /var/lib/apt/lists/*

COPY backend /app/backend
RUN pip install --no-cache-dir "/app/backend[ml]"
COPY ml /app/ml
COPY --from=frontend-build /build/dist /var/www/azari
COPY docker/paas-entrypoint.sh /app/docker/paas-entrypoint.sh
COPY docker/nginx-paas.conf /etc/nginx/nginx.conf
COPY docker/nginx-paas.conf.template /etc/nginx/templates/default.conf.template
COPY docker/supervisord.conf /etc/supervisor/conf.d/azari.conf

RUN groupadd --system azari \
    && useradd --system --gid azari --home-dir /nonexistent --no-create-home azari \
    && rm --force /etc/nginx/sites-enabled/default \
    && mkdir --parents /tmp/nginx-client-body /tmp/nginx-proxy /var/cache/nginx /var/log/supervisor \
    && chown --recursive azari:azari /app /var/www/azari /tmp/nginx-client-body /tmp/nginx-proxy /var/cache/nginx /var/log/supervisor \
    && chmod 0555 /app/docker/paas-entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/app/docker/paas-entrypoint.sh"]

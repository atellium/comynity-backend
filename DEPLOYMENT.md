# VPS deployment with Docker

This stack runs Django behind Nginx with Gunicorn. Redis runs in Docker, while
PostgreSQL remains outside Docker.

## 1. Prepare PostgreSQL

Install PostgreSQL with the matching PostGIS package, then create the
database/user on the VPS (or use a PostGIS-capable managed PostgreSQL server).
The deployment user must be allowed to enable the `postgis` extension for the
initial migration. Alternatively, a database administrator can run this once:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

The Docker image includes GDAL and GEOS. When running Django directly on
Windows, install OSGeo4W or QGIS and set the native DLL paths in `.env`, for
example:

```env
GDAL_LIBRARY_PATH=C:\OSGeo4W\bin\gdal311.dll
GEOS_LIBRARY_PATH=C:\OSGeo4W\bin\geos_c.dll
```

Use the actual GDAL DLL filename installed on the machine.

If
PostgreSQL is installed on the same VPS, allow connections from Docker's bridge
network in `postgresql.conf` and `pg_hba.conf`; keep port 5432 firewalled from
the public internet.

The compose file maps `host.docker.internal` to the Linux Docker host. A local
VPS PostgreSQL URL therefore looks like:

```env
DATABASE_URL=postgresql://comynity:strong-password@host.docker.internal:5432/comynity
```

For managed/remote PostgreSQL, replace the host with the provider hostname and
use its required SSL query option, usually `?sslmode=require`.

## 2. Configure the app

Install Docker Engine and the Docker Compose plugin, clone the repository, then:

```sh
cp .env.example .env
nano .env
```

At minimum, set:

```env
ENVIRONMENT=prod
SECRET_KEY=generate-a-long-random-value
DATABASE_URL=postgresql://comynity:strong-password@host.docker.internal:5432/comynity
ALLOWED_HOSTS=api.example.com
CORS_ALLOWED_ORIGINS=https://example.com
CSRF_TRUSTED_ORIGINS=https://example.com,https://api.example.com
SECURE_SSL_REDIRECT=True
```

`REDIS_URL` is supplied by Compose. Give every app a unique `HTTP_PORT`. It is
bound only to `127.0.0.1`, for access through the host reverse proxy. Do not
commit `.env`.

Also give every deployment a unique `COMPOSE_PROJECT_NAME`. Compose uses it to
isolate container, network, and volume names from the other projects on the VPS.
Keep `BIND_ADDRESS=127.0.0.1` unless the container Nginx must be reachable
directly from another machine.

## 3. Build and start

```sh
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs -f web nginx
```

Run migrations once as an explicit release step, then start the application:

```sh
docker compose run --rm -e RUN_MIGRATIONS=true -e COLLECT_STATIC=true web true
docker compose up -d
```

The normal web entrypoint does not run migrations, which prevents multiple
replicas from racing during rolling deployments. Normal replicas also skip
`collectstatic`; the one-off release command performs it once.

Seed or update the production categories from `seed_categories.json` with:

```sh
docker compose exec web python manage.py seed_categories
```

The command imports only `name`, `display_name`, `label`, and `aliases`. New
categories retain the model defaults for every other field. Re-running it is
safe and updates the four seeded fields on categories matched by `name`.

When upgrading an older deployment whose named static/media volumes were
created by a root container, repair their ownership once before the release:

```sh
docker compose run --rm --user root -e RUN_MIGRATIONS=false -e COLLECT_STATIC=false web \
  sh -c "chown -R app:app /app/staticfiles /app/media"
```
To run Django administration commands:

```sh
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py check --deploy
```

## Direct R2 gallery uploads

Business gallery uploads use short-lived presigned R2 URLs and are normalized
asynchronously by the `worker` service. Apply migrations and start both web and
worker services during deployment:

```sh
docker compose run --rm -e RUN_MIGRATIONS=true -e COLLECT_STATIC=false web true
docker compose up -d --build web worker
```

In the R2 bucket settings, add a browser CORS rule for each frontend origin:

```json
[
  {
    "AllowedOrigins": ["https://your-frontend.example"],
    "AllowedMethods": ["PUT"],
    "AllowedHeaders": ["Content-Type"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

The worker uses the same `R2_*` and `REDIS_URL` values as the web service.
Presigned URLs expire after five minutes. Configure an R2 lifecycle rule to
remove objects under `media/businesses/gallery/pending/` after one day.

## Updates and backups

```sh
git pull
docker compose up -d --build
docker image prune -f
```

Back up the external PostgreSQL database independently with `pg_dump`. Uploaded
local media and Redis persistence are stored in named Docker volumes.

## HTTPS

The container Nginx is published on the loopback-only `HTTP_PORT`. Put a
TLS-enabled host proxy (such as Nginx with Certbot or Caddy) in front of it.
Once HTTPS is forwarding `X-Forwarded-Proto: https`, set
`SECURE_SSL_REDIRECT=True`. Do not enable that setting before the HTTPS proxy is
working.

## Multiple projects on one VPS

Keep each repository in its own directory and set a unique Compose project name
and loopback port in each repository's `.env`:

```text
/srv/apps/project-one/.env   COMPOSE_PROJECT_NAME=project_one  HTTP_PORT=8081
/srv/apps/project-two/.env   COMPOSE_PROJECT_NAME=project_two  HTTP_PORT=8082
```

Start each stack from its own directory with `docker compose up -d --build`.
Only each stack's Nginx port is published to the host; Django and Redis remain
on that project's private Compose network. This prevents host-port collisions
and avoids exposing Redis publicly.
Route each domain through the host-level Nginx:

```nginx
server {
    listen 80;
    server_name api.project-one.com;

    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Create another server block for project two and proxy it to port `8082`.

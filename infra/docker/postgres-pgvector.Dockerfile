# Local development image with PostGIS and pgvector extensions pre-installed
FROM postgis/postgis:16-3.4

RUN set -eux; \
    apt-get update; \
    apt-get install -y postgresql-16-pgvector; \
    rm -rf /var/lib/apt/lists/*; \
    mkdir -p /docker-entrypoint-initdb.d; \
    echo 'CREATE EXTENSION IF NOT EXISTS postgis;' > /docker-entrypoint-initdb.d/00_extensions.sql; \
    echo 'CREATE EXTENSION IF NOT EXISTS vector;' >> /docker-entrypoint-initdb.d/00_extensions.sql

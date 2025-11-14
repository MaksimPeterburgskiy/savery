FROM postgres:16-bookworm

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        postgresql-16-postgis-3 \
        postgresql-16-postgis-3-scripts \
        postgresql-16-pgvector \
        postgis; \
    rm -rf /var/lib/apt/lists/*; \
    mkdir -p /docker-entrypoint-initdb.d; \
    echo 'CREATE EXTENSION IF NOT EXISTS postgis;' > /docker-entrypoint-initdb.d/00_extensions.sql; \
    echo 'CREATE EXTENSION IF NOT EXISTS vector;' >> /docker-entrypoint-initdb.d/00_extensions.sql

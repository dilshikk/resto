# Migration runner image.
# Uses the same PostgreSQL major version as the db service so psql is compatible.
FROM postgres:16-alpine

COPY migrate/migrate.sh /usr/local/bin/migrate.sh
COPY migrations/ /migrations/

RUN chmod +x /usr/local/bin/migrate.sh

ENV MIGRATIONS_DIR=/migrations

# Override the postgres entrypoint: this container only runs migrations and exits.
ENTRYPOINT ["/usr/local/bin/migrate.sh"]

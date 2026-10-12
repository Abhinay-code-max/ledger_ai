FROM postgres:17-alpine

COPY tools/postgres-init.sh /docker-entrypoint-initdb.d/10-ledgerai-roles.sh
RUN sed -i 's/\r$//' /docker-entrypoint-initdb.d/10-ledgerai-roles.sh \
    && chmod 0555 /docker-entrypoint-initdb.d/10-ledgerai-roles.sh

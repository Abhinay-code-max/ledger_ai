FROM golang:1.24-bookworm AS build

ARG MINIO_VERSION=RELEASE.2025-04-22T22-12-26Z
ARG MC_VERSION=RELEASE.2025-04-16T18-13-26Z
RUN CGO_ENABLED=0 GOBIN=/out go install github.com/minio/minio@${MINIO_VERSION} \
    && CGO_ENABLED=0 GOBIN=/out go install github.com/minio/mc@${MC_VERSION}

FROM debian:bookworm-slim AS server
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /out/minio /usr/local/bin/minio
ENTRYPOINT ["/usr/local/bin/minio"]

FROM debian:bookworm-slim AS client
COPY --from=build /out/mc /usr/local/bin/mc
ENTRYPOINT ["/usr/local/bin/mc"]

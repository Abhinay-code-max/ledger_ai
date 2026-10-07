# ADR 0017: Celery and Redis remain replaceable adapters

Status: Accepted

Celery with Redis is the MVP dispatch mechanism, hidden behind `JobQueuePort` and
`EventPublisherPort`. Domain models contain no Celery task types and no Redis keys. Queue payloads
contain resource, event, job, and correlation identifiers only—never documents, CSV bodies,
credentials, or financial rows.

Workers use late acknowledgement, low prefetch, bounded time limits, and named queues. Durable job,
attempt, outbox, and inbox state stays in PostgreSQL, permitting later replacement with another
workflow engine without changing the domain API.

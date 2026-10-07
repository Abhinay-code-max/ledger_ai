# ADR 0022: Posting-request idempotency

Status: Accepted

Role 4 emits a posting request only after checking exact proposal version, compatible policy,
required live approval, evidence, exception state, and unposted/not-validated proposal state. A
partial unique index over tenant, posting event type, resource type, and resource ID makes the
outbox insertion the concurrency authority. Retries preserve the service operation ID. The event
means request only; Phase 3 does not fabricate a posted journal.

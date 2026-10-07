# ADR 0021: Version-bound approvals

Status: Accepted

Each approval request names one immutable resource ID and version. Actions require optimistic
request version, idempotency key, active membership permission, and maker-checker separation when
configured. The request row is locked and only the first valid terminal decision succeeds.
Correction creates a new proposal version and supersedes prior approval. This prevents replay,
self-approval, stale approval, and concurrent double decisions.

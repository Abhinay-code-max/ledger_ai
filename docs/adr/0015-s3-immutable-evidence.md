# ADR 0015: Private S3-compatible immutable evidence storage

Status: Accepted

Phase 2 stores evidence in a private S3-compatible bucket. The database stores only opaque,
server-generated object keys and immutable version metadata. Upload URLs are short-lived and
operation-specific; clients cannot select buckets or keys. Completion rereads the object and
verifies size, SHA-256, allowed media type, and magic bytes. Bucket versioning and server-side
encryption are enabled locally and in CI. Public ACLs and arbitrary remote URL fetching are not
supported.

Original filenames are display metadata and never influence a path. Re-upload creates a new
version rather than overwriting an existing object. Quarantined, rejected, or foreign evidence has
no download endpoint.

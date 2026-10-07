# ADR 0005: S3-compatible storage for immutable evidence

- Status: Accepted architecture; implementation deferred
- Context: Documents and other large evidence should not bloat operational rows and must retain immutable versions.
- Decision: Store large immutable evidence in S3-compatible object storage and expose only opaque references in contracts.
- Consequences: Database records remain small and evidence can be versioned; lifecycle and access policies span two stores.
- Alternatives considered: Database blobs (cost and operational burden); local filesystem (not portable or resilient).
- Deferred production concerns: Provider selection, object lock, encryption, malware scanning, signed access, retention, residency, and deletion workflows.


# ADR 0019: Secure service adapter boundary

Status: Accepted

Role 4 calls Roles 1, 2, 3, and 6 through fixed-path adapters on explicitly configured origins.
Production requires HTTPS and short-lived audience-bound service tokens. Responses are bounded,
strictly typed, tenant-bound, non-redirecting, identity-encoded JSON. Transient retries retain one
operation ID and use bounded backoff; terminal contract or authorization failures are not retried.
This prevents client-controlled SSRF, credential forwarding, and external proposals bypassing the
control plane.

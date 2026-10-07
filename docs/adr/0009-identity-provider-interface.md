# ADR 0009: External identity-provider interface

- Status: Accepted architecture; implementation deferred
- Context: Building secure password storage is outside hackathon scope, while tenant membership must still be verified.
- Decision: Verify authentication through an identity-provider port. Role 4 will not build a custom password system.
- Consequences: Authentication implementation is replaceable; authorization still requires explicit tenant and role checks.
- Alternatives considered: Custom credentials (unacceptable security scope); hard-coded identity (not viable beyond local fixtures).
- Deferred production concerns: Provider selection, token validation, key rotation, session revocation, MFA, SCIM, audit, and emergency access.


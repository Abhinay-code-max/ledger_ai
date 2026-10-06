# ADR 0009: External identity-provider interface

- Status: Accepted; Phase 1 verification boundary implemented
- Context: Building secure password storage is outside hackathon scope, while tenant membership must still be verified.
- Decision: Verify authentication through an identity-provider port. Role 4 will not build a custom password system.
- Consequences: Authentication implementation is replaceable; authorization still requires explicit tenant and role checks.
- Alternatives considered: Custom credentials (unacceptable security scope); hard-coded identity (not viable beyond local fixtures).
- Phase 1 implementation: Asymmetric JWT/JWKS verification validates signature, algorithm, issuer,
  audience, time claims, subject, and key ID. A deterministic adapter exists only by explicit test
  injection.
- Deferred production concerns: Provider selection, session revocation, MFA, SCIM, identity audit,
  emergency access, and provider-specific outage handling.


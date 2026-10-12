# NOVA backend release-candidate operations

## Safety boundary

The demo is synthetic and non-production only. It refuses `production`, requires
`LEDGERAI_DEMO_ENABLED=true`, requires the exact reset confirmation `RESET_NOVA_ONLY`, and resets
only the stable NOVA tenant ID. Service endpoints must use HTTP origins whose hostnames appear in
the explicit demo allowlist. Real credentials belong in the operator environment, never in Git.

## Stub mode: one command

From the repository root:

```powershell
docker compose -f compose.yaml -f compose.nova.yaml --profile nova-stub up --build --abort-on-container-exit --exit-code-from nova-runner-stub nova-runner-stub
```

This starts PostgreSQL, Redis, private versioned MinIO, migrates from the current head, starts
strict Role 1/2/3/6 protocol stubs and the Role 4 API, then executes the full NOVA workflow. The
runner prints progress and ends with one normalized JSON summary.

## Real-service mode

Set the database, migration, Redis, object-storage, Role 1/2/3/6, and Role 4 API URLs plus an
explicit comma-separated `LEDGERAI_DEMO_ALLOWED_HOSTS`. All endpoints must be dedicated
non-production integration resources. Then run:

```powershell
docker compose -f compose.yaml -f compose.nova.yaml --profile nova-real run --rm nova-runner-real
```

The runner does not start or mutate production services. Missing values, remote hosts absent from
the allowlist, credential-bearing URLs, query strings, fragments, or a production environment fail
closed.

## Reproducibility gate

Run the workflow twice and save only the final JSON line as `run1.json` and `run2.json`, then run:

```powershell
uv run --frozen ledgerai-demo-compare run1.json run2.json
uv run --frozen ledgerai-demo-compare run1.json demo/nova/expected/summary.json
```

The comparator removes only known volatile metadata and sorts scalar collections. Financial
amounts, states, provenance, audit actions, and control outcomes remain exact.

## Antigravity verification

1. Check out the exact `integration/backend-e2e` release-candidate SHA and verify the remote tip.
2. Confirm every role entry in `compatibility-manifest.json` is `INTEGRATED` with a full source
   SHA; reject `PENDING` or `REJECTED` entries.
3. Run the end-of-day commands recorded in the release handoff, including empty/repeat migration,
   seed twice, full tests, both NOVA executions, dependency audit, secret scan, and path scan.
4. Inspect the Role 2 migration under the non-owner runtime role and verify forced RLS plus
   append-only triggers.
5. Exercise cross-tenant, wrong-audience, expired-token, wrong-operation, duplicate posting,
   unknown-outcome recovery, stale approval, and maker self-approval failures.
6. Verify all three statement snapshots trace through the posted journal, approval, proposal,
   reconciliation, extraction, immutable document version, and source evidence.
7. Do not promote or merge if generated contracts/OpenAPI drift, either demo result differs, the
   worktree is dirty, or the manifest contains fewer than Roles 1, 2, 3, 4, and 6.

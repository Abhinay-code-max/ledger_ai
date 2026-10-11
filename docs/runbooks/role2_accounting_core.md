# Role 2 Deterministic Accounting and Financial Core Runbook & Recovery Guide

## 1. Overview and Architecture

Role 2 is the deterministic financial core of LedgerAI. It provides mathematical, explainable double-entry bookkeeping, invariant enforcement, immutable posting histories, period close management, and financial statement snapshots.

**Core Principle:** No accounting decisions are delegated to LLMs or heuristics. All validation, posting, and reporting operations are exact, deterministic, and independently verifiable.

### Component Structure
- `ledgerai_role2.domain`: Pure domain models, accounting invariants, double-entry calculators, and reversal engine.
- `ledgerai_role2.database`: Multi-tenant SQLAlchemy models, RLS policies, append-only triggers, and atomic repositories.
- `ledgerai_role2.security`: Token verification, claim binding, request size limiting, concurrency semaphores, and diagnostic sanitization.
- `ledgerai_role2.api`: High-performance FastAPI endpoints strictly adhering to Role 4 adapter contracts.
- `ledgerai_role2.nova`: Golden-ledger definitions and reproducible enterprise financial benchmarks.

---

## 2. Non-Negotiable Accounting Invariants

1. **Exact Double-Entry Equality:**
   $$\sum \text{Debits} = \sum \text{Credits}$$
   Verified using fixed-precision `Decimal`. Floating-point arithmetic is strictly prohibited.
2. **Directed Positive Amounts:**
   Every ledger line specifies an explicit direction (`DEBIT` or `CREDIT`) and a strictly positive Decimal amount ($> 0$).
3. **Database-Level Immutability:**
   Posted journals and financial statement lines are append-only. PostgreSQL triggers (`reject_append_only_mutation`) raise SQLSTATE `55000` on any attempted `UPDATE` or `DELETE`.
4. **Error Correction via Reversals:**
   Posted entries are never edited or removed. Corrections require an explicit reversing journal that transposes debits and credits, followed by a replacement journal.
5. **Period Gating:**
   Ordinary postings are accepted only when the referenced accounting period is `OPEN` and the journal date falls within the period bounds $[start, end]$. Closed or closing periods deterministically reject postings.
6. **Provenance Chain:**
   Every ledger line references its source evidence chain (document ID, page number, and SHA-256 evidence hash).
7. **Role 4 Authorization:**
   Posting requires authenticated Role 4 authorization passed via audience-bound service tokens.

---

## 3. Idempotency State Machine & Recovery Procedures

Every posting operation is identified by an immutable `operation_id` generated upstream by Role 4.

### State Transitions
```
                +--------------+
                |   PENDING    |
                +-------+------+
                        |
            +-----------+-----------+
            |                       |
            v                       v
      +-----------+           +-----------+
      | VALIDATED |           | REJECTED  | (Terminal)
      +-----+-----+           +-----------+
            |
            v
      +-----------+
      |  POSTED   | (Terminal)
      +-----------+
            |
    (Timeout/Network)
            |
            v
      +-----------+
      |  UNKNOWN  |
      +-----+-----+
            |
     (Status Lookup)
            v
      +-----------+
      |  POSTED   | (Recovered)
      +-----------+
```

### Recovery Runbooks

#### Scenario A: Timeout After Commit Before Response
- **Symptom:** Role 4 receives a network timeout (HTTP 408/504) while posting.
- **State in DB:** Journal is posted; operation state is `POSTED`.
- **Action:** Role 4 calls `/v1/journal-posting-status` with `operation_id`. Role 2 looks up the existing row, retrieves the posted journal ID, and returns `outcome="POSTED"` without creating duplicate entries.

#### Scenario B: Same Operation ID with Conflicting Payload
- **Symptom:** Client re-submits the same `operation_id` but alters the accounts, amounts, or period.
- **Handling:** Role 2 computes the SHA-256 hash of the payload. If the hash differs from the recorded hash, Role 2 immediately returns HTTP 409 `IDEMPOTENCY_CONFLICT`.

#### Scenario C: Unknown Outcome Recovery
- **Symptom:** Posting process was interrupted (e.g. process termination).
- **Action:** Call `/v1/journal-posting-status`. If a journal record exists for that `operation_id`, status transitions to `POSTED`. If no journal exists, status returns `UNKNOWN` or `FAILED`, allowing Role 4 to initiate a fresh retry.

---

## 4. Period Close Workflow

Prerequisites verified prior to closing:
1. All postings within the period are confirmed (`POSTED`).
2. No pending, validating, or unknown postings exist for the period.
3. Trial balance is balanced ($\sum \text{Debits} = \sum \text{Credits}$).
4. Period state is `OPEN`.

### Execution
1. Transition period state to `CLOSED`.
2. Generate immutable statement snapshots (`TRIAL_BALANCE`, `PROFIT_AND_LOSS`, `BALANCE_SHEET`).
3. Store statement lines with full provenance references to underlying posted journals.

---

## 5. Security & Isolation Controls

- **Service Tokens:** HS256 tokens signed with `LEDGERAI_SERVICE_TOKEN_SECRET`.
  - Claims required: `iss`, `sub`, `aud="role2"`, `iat`, `exp`, `tenant_id`, `operation_id`.
  - Validation: Token `tenant_id` must match `X-Tenant-ID` header and payload `tenant_context.tenant_id`.
- **Database Row-Level Security:**
  - `FORCE ROW LEVEL SECURITY` applied across all Role 2 tables.
  - Policy: `USING (tenant_id = ledgerai.current_tenant_id()) WITH CHECK (tenant_id = ledgerai.current_tenant_id())`.
- **Least-Privilege Role:** Runtime access is granted to `ledgerai_runtime` with `SELECT, INSERT` on append-only tables and `SELECT, INSERT, UPDATE` on state tables.
- **Sanitized Errors:** Internal SQL queries, tracebacks, and database connection strings are stripped from all API responses.

---

## 6. Known Limitations
- Multi-currency conversions require explicit exchange rates in journal line definitions.
- Archival of closed accounting periods older than 7 years should be handled via database partition detachment rather than table deletion.

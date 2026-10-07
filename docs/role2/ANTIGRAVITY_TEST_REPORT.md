# LedgerAI Role 2 — Financial Engine & Accounting QA Test Report

**Evaluator:** Independent QA Engineer  
**Date:** 2026-10-06  
**Target Workstream:** Role 2 (Financial Engine & Accounting)  
**Repository:** `C:\Users\E028.28\Documents\frontend for ledger\ledger_ai`  
**Expected Branch:** `role2/financial-engine`  

---

## 1. Git State and Tested Baseline

### Git Verification
- **Active Branch:** `role2/financial-engine`
- **Remote Origin:** `https://github.com/Abhinay-code-max/ledger_ai.git` (fetch & push)
- **Base Commit:** `8b4e648 ci(contracts): enforce contract compatibility checks`
- **Branch Parity:** Matches expected branch. No commits, merges, resets, or stashes were performed.
- **Git Status Summary:**
  ```text
  ?? docs/role2/ANTIGRAVITY_TEST_REPORT.md
  ?? tests/role2/test_antigravity_financial_core.py
  ```
  *(Preserved pre-existing untracked files: `docs/role2/`, `src/financial_core/`, `tests/role2/`)*

### Tested Scope
An entity-bound, in-memory double-entry accounting reference engine comprising:
- Chart of Accounts validation and active-status enforcement
- Exact money calculations with configurable currency precision (minor-unit integer conversions)
- JournalProposal validation (balance, evidence, lines, tenant boundaries, accounts)
- ApprovalDecision binding (action, actor type, separation of duties, version matching)
- Idempotent posting with conflict detection and double-post prevention
- Append-only reversal with date ordering, link preservation, and balance offset
- General Ledger, Account Balances, and multi-currency Trial Balance
- Profit & Loss and Balance Sheet generation with retained earnings flow into equity
- Period close with posting/reversal locks through closed period end
- Deterministic AP/AR demo templates (`AP_INVOICE`, `AP_PAYMENT`, `AR_INVOICE`, `AR_RECEIPT`)

---

## 2. Exact Commands and Results

| Command | Exit Code | Output Summary | Status |
| :--- | :---: | :--- | :---: |
| `.\.venv\Scripts\python.exe -m pytest tests/role2` | `0` | **173 passed** in 0.30s (47 baseline + 126 new adversarial tests) | **PASS** |
| `.\.venv\Scripts\python.exe -m pytest` | `0` | **979 passed** in 2.66s (entire repository test suite) | **PASS** |
| `.\.venv\Scripts\python.exe -m mypy src tests tools` | `0` | Success: no issues found in **27 source files** | **PASS** |
| `.\.venv\Scripts\python.exe tools/generate_contract_artifacts.py --check` | `0` | Checked **55 contract artifacts** (0 changed) | **PASS** |
| `.\.venv\Scripts\python.exe -m compileall -q src tools tests` | `0` | All Python modules byte-compiled cleanly without syntax errors | **PASS** |
| `.\.venv\Scripts\python.exe -m ruff check .` | `1` | **Found 6 errors** (3 in `src/financial_core/engine.py`, 3 in `tests/role2/test_financial_core.py`) | **FAIL** |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | `1` | **6 files would be reformatted** | **FAIL** |

---

## 3. Additional Tests and Coverage

An independent adversarial test suite was authored in [`tests/role2/test_antigravity_financial_core.py`](file:///C:/Users/E028.28/Documents/frontend%20for%20ledger/ledger_ai/tests/role2/test_antigravity_financial_core.py) containing **126 test cases** derived from accounting first principles:

### Coverage Matrix
1. **Money & Precision (`TestMoneyCalculations`)**
   - Exact minor unit conversions and Decimal presentations for scales 0, 2, and 3.
   - Operations under degraded global decimal context (`DecimalContext(prec=1)`).
   - Very large amounts up to 99-character digit strings without floating-point drift.
   - Rejection of zero (`0`, `0.00`), negative (`-1`), float, integer, boolean, `None`, list, and dict amounts.
   - Rejection of special values: `NaN`, `Infinity`, `-Infinity`, and `sNaN`.
   - Rejection of scientific notation strings (`1e2`, `1E+5`), malformed decimals (`.50`, `12..34`, `012.34`), and length > 100.
   - Currency scale validation: scales -1, 7, boolean, and float scale configurations rejected.

2. **Journal Validation (`TestJournalValidation`)**
   - 1-cent unbalanced entries rejected (`UNBALANCED_JOURNAL`).
   - Duplicate line IDs rejected (`DUPLICATE_LINE`).
   - Unknown and inactive chart accounts rejected (`ACCOUNT_UNAVAILABLE`).
   - Header vs line currency mismatch rejected (`CURRENCY_MISMATCH`).
   - Line and header evidence lacking `source_document_id`, `human_correction_id`, and `evidence_hash` rejected (`EVIDENCE_UNRESOLVABLE`).
   - Models modified via `model_construct` or `model_copy` revalidated from raw JSON snapshots (`ValidationError` enforced).
   - Verification that rejected proposals leave ledger state completely empty and unmutated.

3. **Tenant & Approval Boundaries (`TestTenantAndApprovalBoundaries`)**
   - Tenant, Organization, and Legal Entity mismatches on both proposal and approval rejected (`TENANT_MISMATCH`).
   - Wrong reviewed resource ID, version, or type rejected (`APPROVAL_VERSION_MISMATCH`).
   - Non-`APPROVE` actions (`REJECT`, `REQUEST_EVIDENCE`, `ESCALATE`) rejected (`APPROVAL_REQUIRED`).
   - Non-human approvers (`AGENT`, `SERVICE`) rejected (`APPROVAL_REQUIRED`).
   - Missing separation-of-duties assertion (`separation_of_duties_checked=False`) rejected (`APPROVAL_REQUIRED`).
   - Proposal approval decision reference mismatch rejected (`APPROVAL_REFERENCE_MISMATCH`).

4. **Posting & Concurrency (`TestPostingAndConcurrency`)**
   - Exact retries return identical `JournalEntry` and do not duplicate ledger records.
   - Content and approval mutations on same proposal ID/version raise `POSTING_CONFLICT`.
   - New proposal versions cannot double-post the same proposal ID (`POSTING_CONFLICT`).
   - Multi-threaded concurrent posting (16 workers, 32 submissions) produces exactly 1 entry.
   - Post retries after period close and after reversal correctly return original entry.

5. **Reversals (`TestReversals`)**
   - Generates equal and opposite lines (DEBIT $\leftrightarrow$ CREDIT, identical units, new UUIDs).
   - Original posted entry remains frozen and unmutated.
   - As-of date balances accurately reflect original balance before reversal date and zero balance on/after reversal date.
   - Reversal of non-existent entries rejected (`ENTRY_NOT_FOUND`).
   - Reversal dates preceding original posting date rejected (`INVALID_REVERSAL`).
   - Empty and whitespace-only reversal reasons rejected (`INVALID_REVERSAL`).
   - Duplicate exact reversals return identical reversal entry; conflicting dates/reasons raise `REVERSAL_CONFLICT`.
   - Reversing a reversal rejected (`REVERSAL_OF_REVERSAL`).
   - Multi-threaded concurrent reversals (8 workers, 16 submissions) are thread-safe and return single entry.

6. **Reports & Golden Scenarios (`TestReportsAndGoldenScenarios`)**
   - Full 5-step lifecycle: Capital contribution ($50k), AP Expense ($12k), AP Payment ($12k), AR Invoice ($30k), and AR Receipt ($20k).
   - Independent verification: Cash ($58k), AR ($10k), AP ($0), Capital ($50k credit), Revenue ($30k credit), Expense ($12k debit).
   - Trial Balance: Debits ($80,000) == Credits ($80,000).
   - Balance Sheet: Assets ($68,000) == Liabilities ($0) + Equity ($68,000).
   - Retained earnings correctly flows into balance sheet equity during net income and net loss scenarios.
   - Inclusive reporting boundaries and rejection of inverted date ranges (`INVALID_DATE_RANGE`).
   - Multi-currency isolation (INR transactions do not leak into USD reports).
   - Multi-period reversal reporting: prior period P&L preserves historical revenue; subsequent period P&L reflects reversal debit.

7. **Period Close (`TestPeriodClose`)**
   - Locks postings and reversals through period end. Backdated entries rejected (`PERIOD_CLOSED`).
   - Entries with dates strictly after closed period permitted.
   - Exact close retries return stable, identical `PeriodClose` results.
   - Overlapping and contained close periods rejected (`PERIOD_OVERLAP`).
   - Historical close results remain stable after subsequent period activity.
   - Operates cleanly on empty ledgers and multiple configured currencies.

8. **Demo Templates & Snapshots (`TestDemoTemplatesAndSnapshots`)**
   - Exact debit/credit mappings verified for `AP_INVOICE`, `AP_PAYMENT`, `AR_INVOICE`, and `AR_RECEIPT`.
   - Deterministic proposal IDs generated from namespace UUID5.
   - Distinct document keys and templates generate distinct proposal IDs.
   - Header and line evidence, as well as correlation IDs, preserved intact.
   - Generated proposals remain unapproved and unposted (`approval_decision=None`, `policy_decision=None`).
   - Rejection of unknown template names, blank document keys, and identical debit/credit accounts.
   - Post-creation mutations to source objects do not alter posted snapshots.

---

## 4. Findings Ordered by Severity

### Finding 1: Static Linter and Code Quality Gate Failures (6 Errors)
- **Severity:** Medium (Blocks automated CI linting pipeline)
- **File and Line:**
  1. [`src/financial_core/engine.py:2:1`](file:///C:/Users/E028.28/Documents/frontend%20for%20ledger/ledger_ai/src/financial_core/engine.py#L2): `I001 [*] Import block is un-sorted or un-formatted`
  2. [`src/financial_core/engine.py:128:101`](file:///C:/Users/E028.28/Documents/frontend%20for%20ledger/ledger_ai/src/financial_core/engine.py#L128): `E501 Line too long (112 > 100)`
  3. [`src/financial_core/engine.py:262:101`](file:///C:/Users/E028.28/Documents/frontend%20for%20ledger/ledger_ai/src/financial_core/engine.py#L262): `E501 Line too long (103 > 100)`
  4. [`tests/role2/test_financial_core.py:61:9`](file:///C:/Users/E028.28/Documents/frontend%20for%20ledger/ledger_ai/tests/role2/test_financial_core.py#L61): `B010 [*] Do not call setattr with a constant attribute value`
  5. [`tests/role2/test_financial_core.py:214:101`](file:///C:/Users/E028.28/Documents/frontend%20for%20ledger/ledger_ai/tests/role2/test_financial_core.py#L214): `E501 Line too long (106 > 100)`
  6. [`tests/role2/test_financial_core.py:263:101`](file:///C:/Users/E028.28/Documents/frontend%20for%20ledger/ledger_ai/tests/role2/test_financial_core.py#L263): `E501 Line too long (102 > 100)`
- **Minimal Reproduction:**
  ```powershell
  .\.venv\Scripts\python.exe -m ruff check .
  ```
- **Expected Behavior:** All modules pass `ruff check .` with 0 errors.
- **Actual Behavior:** Command exits with code `1` showing 6 rule violations.
- **Accounting / Integration Impact:** Any CI workflow enforcing Ruff linting will fail PR validation.
- **Suggested Correction (do not apply now):**
  - Sort imports in `engine.py` using Ruff's import order.
  - Break lines 128 and 262 in `engine.py` across multiple lines.
  - In `test_financial_core.py:61`, replace `setattr(entry, "currency", "USD")` with `entry.currency = "USD"`.
  - Wrap lines 214 and 263 in `test_financial_core.py`.

---

### Finding 2: Code Formatter Inconsistency (6 Unformatted Files)
- **Severity:** Low (Repository style consistency)
- **File and Line:**
  - [`docs/role2/FINANCIAL_CORE.md`](file:///C:/Users/E028.28/Documents/frontend%20for%20ledger/ledger_ai/docs/role2/FINANCIAL_CORE.md)
  - [`src/financial_core/__init__.py`](file:///C:/Users/E028.28/Documents/frontend%20for%20ledger/ledger_ai/src/financial_core/__init__.py)
  - [`src/financial_core/engine.py`](file:///C:/Users/E028.28/Documents/frontend%20for%20ledger/ledger_ai/src/financial_core/engine.py)
  - [`src/financial_core/money.py`](file:///C:/Users/E028.28/Documents/frontend%20for%20ledger/ledger_ai/src/financial_core/money.py)
  - [`src/financial_core/templates.py`](file:///C:/Users/E028.28/Documents/frontend%20for%20ledger/ledger_ai/src/financial_core/templates.py)
  - [`tests/role2/test_financial_core.py`](file:///C:/Users/E028.28/Documents/frontend%20for%20ledger/ledger_ai/tests/role2/test_financial_core.py)
- **Minimal Reproduction:**
  ```powershell
  .\.venv\Scripts\python.exe -m ruff format --check .
  ```
- **Expected Behavior:** `6 files would be reformatted` check exits with code 0.
- **Actual Behavior:** Command exits with code `1`.
- **Accounting / Integration Impact:** CI format checks will fail.
- **Suggested Correction (do not apply now):**
  Run `.\.venv\Scripts\python.exe -m ruff format .` once code edits are authorized.

---

### Finding 3: Unsanitized Account Code Whitespace
- **Severity:** Low (Edge-case robustness)
- **File and Line:** [`src/financial_core/engine.py:39-43`](file:///C:/Users/E028.28/Documents/frontend%20for%20ledger/ledger_ai/src/financial_core/engine.py#L39-L43)
- **Minimal Reproduction:**
  ```python
  acct = Account(" CASH ", "Cash", "ASSET")
  engine = FinancialEngine(ctx, [acct], {"INR": 2})
  # engine._accounts stores key " CASH "
  # A proposal referencing "CASH" fails with ACCOUNT_UNAVAILABLE
  ```
- **Expected Behavior:** Account codes with leading/trailing whitespace should either be rejected with `INVALID_ACCOUNT` or stripped during initialization.
- **Actual Behavior:** `Account.__post_init__` checks `if not self.code.strip(): raise AccountingError("INVALID_ACCOUNT")`, but does not reject non-stripped strings or normalize `code`.
- **Accounting / Integration Impact:** Unintended mismatch between caller references and internal chart mapping.
- **Suggested Correction (do not apply now):**
  Add `if self.code != self.code.strip(): raise AccountingError("INVALID_ACCOUNT")` to `Account.__post_init__`.

---

### Finding 4: Inconsistent Exception Types in Demo Templates
- **Severity:** Low (API consistency)
- **File and Line:** [`src/financial_core/templates.py:21-23`](file:///C:/Users/E028.28/Documents/frontend%20for%20ledger/ledger_ai/src/financial_core/templates.py#L21-L23)
- **Minimal Reproduction:**
  ```python
  from financial_core import AccountingError
  from financial_core.templates import demo_proposal

  try:
      demo_proposal(source, "INVALID_TEMPLATE", "k", "EXPENSE", "PAYABLE")
  except AccountingError:
      pass  # NOT CAUGHT! Raises standard ValueError
  ```
- **Expected Behavior:** Domain validation failures raise `AccountingError` with a standardized `.code` attribute.
- **Actual Behavior:** `demo_proposal` raises generic Python `ValueError("UNKNOWN_TEMPLATE")` and `ValueError("INVALID_TEMPLATE_INPUT")`.
- **Accounting / Integration Impact:** Callers catching `AccountingError` to map error codes will encounter unhandled generic `ValueError`.
- **Suggested Correction (do not apply now):**
  Raise `AccountingError("UNKNOWN_TEMPLATE")` and `AccountingError("INVALID_TEMPLATE_INPUT")`.

---

## 5. Trust Boundary Analysis: Caller-Enforced vs Engine-Enforced

As an in-memory financial engine, certain invariants are strictly enforced internally, while others fundamentally depend on the trusted caller (Role 4 backend / API orchestration):

| Security / Accounting Invariant | Enforced by Engine? | Delegated to Caller? | Rationale & Boundary |
| :--- | :---: | :---: | :--- |
| **Double-Entry Balance ($Debits = Credits$)** | **YES** | No | Internal integer minor unit validation (`UNBALANCED_JOURNAL`). |
| **Exact Currency Scale & Precision** | **YES** | No | Internal rejection of excess decimals (`CURRENCY_PRECISION`). |
| **Posting Idempotency & Conflict Detection** | **YES** | No | SHA-256 digest comparison prevents modified double posts. |
| **Append-Only Reversal & Date Ordering** | **YES** | No | Enforces $reversal\_date \ge journal\_date$, creates inverted lines. |
| **Period Close Posting Lock** | **YES** | No | Rejects dates $\le end$ (`PERIOD_CLOSED`). |
| **Approver Actor Type == "HUMAN"** | **YES** | No | Rejects `AGENT` or `SERVICE` approvals (`APPROVAL_REQUIRED`). |
| **Approver Authentication & Identity** | No | **YES** | Engine cannot verify if `actor_id` corresponds to a genuine, authenticated human user. |
| **Authorization Roles (e.g. Finance Admin)** | No | **YES** | Engine verifies `authorization_roles` is non-empty, but does not evaluate role permissions. |
| **Real Separation-of-Duties (SoD)** | No | **YES** | Engine checks boolean `separation_of_duties_checked`, but cannot verify if approver authored the invoice. |
| **Policy Decision Enforcement** | No | **YES** | `proposal.policy_decision` is preserved but not evaluated or required by the engine. |
| **Evidence File Integrity & Existence** | No | **YES** | Engine verifies reference schema and presence of ID/hash, but does not check object storage. |
| **Approval Revocation / Expiry** | No | **YES** | Engine treats approval decisions as immutable snapshots; caller must ensure decision was not revoked. |

---

## 6. Documented Limitations

The following items are confirmed as architectural decisions and documented Phase 1 boundaries, not implementation defects:
1. **In-Memory Volatility:** State is stored in memory dictionaries (`_entries`, `_posted`, `_reversed`, `_closed`) and is lost on process restart. Durable ACID persistence belongs to future PostgreSQL adapters (ADR 0004).
2. **Instance-Level Concurrency:** Thread safety is achieved via `threading.RLock` within a single Python process. Cross-process distributed locking and database transactions are deferred to Phase 2.
3. **Period Close Locks Preceding Backdates:** When a period $[start, end]$ is closed, all dates $\le end$ are locked against new postings and reversals. Earlier backdates into historical periods prior to $start$ are intentionally blocked.
4. **No Statutory Closing Entries:** Retained earnings is a real-time presentation calculation ($Assets - Liabilities - Equity$). Formal closing journal entries that zero out revenue/expenses into an equity account are not created.
5. **No FX Conversion:** The engine isolates entries by currency and generates separate trial balances and statements per currency. Foreign exchange valuation and consolidation are out of scope.
6. **Demo Template Scope:** Templates produce 2-line proposals based on the source line amount. Tax calculations, multi-line splits, discounting, and counterparty subsidiary ledger aging are omitted.

---

## 7. Blocked Checks

- **Ruff Availability Status:**
  In the initial Role 2 audit, Ruff was reported as blocked by Windows Application Control (`WinError 4551`).
  During this QA evaluation, Ruff was tested both as a Python module (`python -m ruff`) and via direct binary invocation (`.\.venv\Scripts\ruff.exe --version` returning `ruff 0.16.10`).
  **Conclusion:** Ruff is **NOT blocked by host execution policy** in the current environment. It executes properly, but fails due to actual source code formatting and linting violations in Role 2 files (see Findings 1 and 2).

---

## 8. Final QA Verdict

### Summary Scores
- **Functional Accounting Logic:** **PASS** (100% pass rate: 979 / 979 tests)
- **Contract & Schema Invariants:** **PASS** (55 artifacts checked, strict type checking passes)
- **Static Analysis & Linting Gates:** **FAIL** (6 Ruff lint errors, 6 unformatted files)

### Verdict: **FAIL (Linter / Code Standards Gates)** / **PASS (Core Accounting Engine)**
*The financial engine core is functionally robust, exact, and mathematically correct under all tested adversarial conditions. However, the overall QA verdict is **FAIL** until the 6 Ruff linting errors and formatting discrepancies in `src/financial_core` and `tests/role2/test_financial_core.py` are resolved once editing existing files is authorized.*

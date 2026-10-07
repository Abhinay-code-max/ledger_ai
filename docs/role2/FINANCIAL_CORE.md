# Financial core usage

This package is an in-memory domain reference implementation. It adds no server or database.
The API/orchestration boundary must authenticate and authorize context, approvals and reversals.
Never expose an engine instance directly to untrusted callers.

```python
from financial_core import Account, FinancialEngine

# context, proposal and approval are validated shared v1 contracts supplied by a trusted adapter.
engine = FinancialEngine(
    context,
    [
        Account("EXPENSE", "Expense", "EXPENSE"),
        Account("PAYABLE", "Accounts payable", "LIABILITY"),
    ],
    {"INR": 2},
)
lines = engine.validate_proposal(proposal)  # does not approve or mutate the proposal
entry = engine.post(proposal, approval)
rows = engine.trial_balance("INR", proposal.proposed_journal_date)
```

The chart codes must match proposal account references. Currency scales are mandatory configuration.
Amounts are positive and precision must match the configured scale; trailing zeroes are permitted.
AccountingError.code supplies stable internal failure codes. Role 4 maps these and contract validation
errors to its public error convention. Inputs are revalidated, including copied/constructed models.

Posting requires an APPROVE human decision for exactly this proposal ID/version and entity.
Role 4 must establish its authenticity, authorization, separation-of-duties and policy eligibility.
Optional proposal approval references must identify the decision supplied to post.
One proposal ID may post once; exact retries return the original entry, changed requests conflict.

Posted entries are frozen snapshots. Reverse appends offsetting lines and links to the original;
its original date balances remain available. Exact reversal retries return the existing reversal.
A reversal cannot precede the original entry, target another reversal, or use a closed posting date.

Reports are isolated by currency. Account balances use debit-positive signs. Trial balance splits
net balances into debit/credit columns. P&L uses inclusive date ranges. Balance-sheet equity includes
cumulative net income (also exposed separately as retained_earnings). Retained earnings here is a
presentation calculation, not a posted fiscal closing journal. General ledger returns journal entries
ordered by journal date and ID with evidence and source snapshots intact.

Close covers an inclusive date interval and locks all dates through its end against new postings
and reversals. Exact already-posted retries still succeed. Overlapping closes fail. The close result
includes reports for every configured currency. There is no reopen or fiscal carry-forward operation.

Demo templates require a source proposal, AP/AR operation, stable document key and chart codes.
They use the first source line's amount/evidence and preserve header evidence/correlation.
They deliberately produce unapproved proposals; invoice splitting, tax, FX, partial allocation,
AP/AR aging, and counterparty subledgers are outside this demo.

The tests reuse existing synthetic contracts without altering shared artifacts. The golden AP/AR
cycle posts an expense/payable, payment, receivable/revenue and receipt; it proves balanced books
and cleared cash/payable/receivable balances. Separate tests verify net income flows into equity.

Persistence, cross-process transactions, trusted authorization, audit/event transport, public result
schemas and API wiring remain integration work. Nothing has been committed or pushed.

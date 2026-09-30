# Practice session — prompts to run in Claude Code

Run these in order from inside this folder. After each step, check Claude's output against the
source files yourself before moving on, and write what you accepted, rejected or corrected in
output/review_notes.md. Copy each prompt and Claude's reply into output/prompt_log.md as you go —
the client's case study asks for exactly this (prompts, AI output, your explanation).

## Step 1 — Orient
Read CLAUDE.md and every file in data/ and documents/. Summarise what each file contains,
the period covered, and the opening and closing balances you can see. Do not analyse yet.

## Step 2 — Bank reconciliation
Write scripts/reconcile_checking.py that matches the bank statement to the QBO checking
register (same amount, dates within 3 days), lists unmatched items on each side, includes the
outstanding July items, and produces output/recon_checking.md. Run it and show me the
unreconciled difference.

## Step 3 — Card reconciliation
Do the same for the Amex card: scripts/reconcile_amex.py and output/recon_amex.md.
Explain every item that makes QBO differ from the statement.

## Step 4 — Review transactions, AR and AP
Review every uncategorized or suspicious transaction, the open AR invoices and the open AP
bills. For each finding, write a row to output/review_findings.csv with the evidence and your
confidence. Check the Stripe payout file, the payroll register, the insurance policy summary
and the company notes before recommending a category.

## Step 5 — Stage corrections
For the findings I approve, write balanced correcting entries to
output/staged_journal_entries.csv with status STAGED, then re-run both reconciliations as if
the entries were posted and show me the new unreconciled differences.

## Step 6 — Close status
Write output/open_questions.md and a five-line close status: which accounts tie after
approval, what is staged, what needs a client decision.

## Your own checks (do not skip)
- Did Claude call anything "reconciled" before the difference was 0.00?
- Did it book any cash receipt as new revenue when an invoice was already open?
- Did it treat any transfer (card payment, owner transfer) as an expense?
- Did it spot every error in the card register, or only the ones in the bank?
- Did it make a write-off decision that belongs to the client?

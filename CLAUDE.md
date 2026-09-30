# Project rules for Claude Code

You are assisting an accountant (Chaitanya Gangane) with the August 2026 month-end close review
for Copperfield Design Studio LLC, a FICTIONAL US small business on QuickBooks Online.
The accountant makes every final decision. Your job is to find, match, calculate and explain.

## Hard rules
1. Nothing is ever posted. There is no QuickBooks connection. Every correction you propose is
   written to output/staged_journal_entries.csv with status STAGED.
2. Treat data/ and documents/ as read-only source evidence. Write only to output/ and scripts/.
3. Every finding must cite its evidence: file name and the row (date + description/amount).
4. Every journal entry must balance (total debits = total credits per je_id). Check this in code.
5. Never say an account "is reconciled" unless you have computed the unreconciled difference
   and it is exactly 0.00. Show the calculation.
6. Judgement calls (write-offs, owner vs employee payments, accrual/prepaid treatment) are
   recommendations only. Label them "needs accountant/client decision".
7. Use Python (standard library or pandas). Put scripts in scripts/ so the work can be re-run.

## Output files
- output/recon_checking.md   — statement balance, deposits in transit, outstanding checks,
                               adjusted bank, book balance, difference, and each reconciling item
- output/recon_amex.md       — same structure for the Amex card (liability, charges positive)
- output/review_findings.csv — id, area, item, amount, recommendation, evidence, confidence
- output/staged_journal_entries.csv — je_id, finding_id, account, debit, credit, memo, status
- output/open_questions.md   — anything that needs the client's input

## Sign conventions
- Bank files: deposits positive, withdrawals negative.
- Amex QBO register: charges positive (increase the amount owed).
- Amex statement: charges positive, payments and credits negative.

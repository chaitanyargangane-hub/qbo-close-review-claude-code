# Open questions — August 2026 close

Copperfield Design Studio LLC (fictional). Items that need the client's input or a document before
they can be closed. Finding IDs refer to `output/review_findings.csv`; entries refer to
`output/staged_journal_entries.csv`. Nothing has been posted.

## Close status (as at review, entries not posted)

1. Checking x2204 and Amex x3008 both show 0.00 pro forma difference once the staged entries are approved and posted (currently 629.00 and −2,658.00; neither is reconciled until posted and re-run).
2. Staged: 10 balanced entries, JE01–JE10 (F01–F07, F11, F12, F15), total debits 14,433.40 = credits 14,433.40, net income impact +5,597.00.
3. Needs client decision: F03 owner's draw (staged, pending confirmation), F09 Adobe plan term, F10 stale check 1042, F14 Keller Media collect or write off.
4. Needs documents: F08 Gusto payroll journal (at least 2,180.00 of withholdings unrecorded, will reduce net income); F13 September Amex statement for Vercel 212.00.
5. Not closed: payroll expense/liabilities (F08) and AR (INV-1152) stay open; Amex tie depends on F13.

## Questions for the client

### F03 — Transfer to M. Reyes, 1,500.00 (staged as JE03, pending confirmation)
- **What we see:** 2026-08-28 "ONLINE TRANSFER TO M REYES X7710" −1,500.00 (bank_statement_2204_aug2026.csv line 13), booked in QBO to Payroll Expense (qbo_register_checking_aug2026.csv line 15). The owner, Marisol Reyes, is not on payroll (company_notes.txt lines 2–3); the payroll register lists only Jordan Patel and Sam Kim.
- **Question:** Was this a draw by the owner? Or a reimbursement of business expenses (if so, please send receipts), or a payment to someone else named M. Reyes?
- **If draw:** JE03 (Dr Owner's Draw / Cr Payroll Expense) can be posted as staged. **If not:** JE03 is replaced.

### F08 — Gusto payroll journal for 14 Aug 2026 (not staged)
- **What we see:** QBO records only the 7,420.00 Gusto debit to Payroll Expense (qbo_register_checking_aug2026.csv line 9; bank line 8). The payroll register shows gross 9,600.00 and net 7,420.00 (payroll_register_aug2026.csv lines 2–3), so 2,180.00 of employee withholdings, plus any employer taxes, is not recorded. No separate Gusto tax debit appears on the August bank statement.
- **Question:** Please send the Gusto payroll journal/report for the 14 Aug pay date, showing gross wages, employee and employer taxes, and when Gusto debits the taxes.
- **Effect:** Payroll expense will increase by at least 2,180.00 and payroll liabilities will be recorded.

### F09 — Adobe Creative Cloud, 659.88 (not staged)
- **What we see:** One Adobe charge of 659.88 on 2026-08-12 (bank line 7; QBO line 7). 659.88 = 12 × 54.99, which suggests an annual prepaid plan.
- **Question:** Is this an annual plan paid upfront, or a monthly charge? Please confirm the plan term.
- **Effect:** If annual, it could be spread over 12 months; it is likely below any capitalisation threshold, so expensing it is acceptable. Needs accountant/client decision. (The duplicate second Adobe entry is separate and staged as JE04.)

### F10 — Check 1042 to Carver Studio Rentals, 1,200.00, dated 2026-07-09 (not staged)
- **What we see:** Outstanding at the July close (outstanding_items_jul2026.csv line 2) and still not cleared by 31 Aug (53 days). Carver also has an open bill B-2203 for 600.00 (ap_open_bills_31aug2026.csv line 3).
- **Question:** Did Carver Studio Rentals receive and deposit check 1042? Should it be voided and reissued, or voided because it was not owed? What does Carver's statement show as owed?
- **Effect:** Stays as an outstanding check on the checking rec until it clears or is voided.

### F13 — Vercel charge, 212.00, dated 2026-08-31 (not staged)
- **What we see:** In the QBO Amex register (qbo_register_amex_aug2026.csv line 10) but not on the August Amex statement. Treated as a timing item on the Amex rec.
- **Question:** Please send the September Amex statement (or confirm the charge posted). Was it charged to Amex x3008?
- **Effect:** If it is on the September statement, no entry needed. If not, it must be reversed from the Amex register and the Amex pro forma difference becomes −212.00 until corrected.

### F14 — INV-1152 Keller Media, 2,750.00, 67 days past due (not staged)
- **What we see:** Invoice dated 2026-05-26, due 2026-06-25, still open at 31 Aug (ar_open_invoices_31aug2026.csv line 2).
- **Question:** Has Keller Media been contacted? Is there a payment plan or dispute? Do you want to keep collecting, record an allowance, or write it off?
- **Effect:** Client decision. No entry until decided. A write-off would reduce net income by 2,750.00 (or reduce revenue if treated as a credit memo).

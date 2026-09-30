"""Step 5: stage correcting journal entries for the approved findings.

Nothing is posted. Every entry is written to output/staged_journal_entries.csv
with status STAGED. Amounts are looked up from the source files and checked;
each je_id must balance (total debits = total credits) or the script stops.

Approved by the accountant: F01, F02, F03, F04, F05, F06, F07, F11, F12, F15.
Not staged: F08 (needs Gusto journal), F13 (Vercel timing), F14 (client decision),
and F09/F10 (not approved).

Run from anywhere:
    python3 scripts/stage_journal_entries.py
"""

import csv
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FINDINGS = ROOT / "output" / "review_findings.csv"
OUT = ROOT / "output" / "staged_journal_entries.csv"

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

# Account names used by the reconciliation scripts for the pro forma re-run.
CHECKING = "Checking x2204"
AMEX = "Amex x3008"

APPROVED = ["F01", "F02", "F03", "F04", "F05", "F06", "F07", "F11", "F12", "F15"]
NOT_STAGED = {"F08", "F13", "F14"}

# Account type drives the net income calculation.
ACCOUNT_TYPES = {
    CHECKING: "Asset",
    "Accounts Receivable": "Asset",
    "Prepaid Insurance": "Asset",
    AMEX: "Liability",
    "Accounts Payable": "Liability",
    "Owner's Draw": "Equity",
    "Uncategorized Income": "Income",
    "Interest Income": "Income",
    "Merchant Fees": "Expense",
    "Miscellaneous Expense": "Expense",
    "Payroll Expense": "Expense",
    "Software Subscriptions": "Expense",
    "Bank Service Charges": "Expense",
    "Insurance Expense": "Expense",
    "Office Supplies": "Expense",
    "Meals": "Expense",
    "Contract Labor": "Expense",
}


def money(value):
    return Decimal(value).quantize(CENT)


def load(name):
    with open(DATA / name, newline="") as f:
        return list(csv.DictReader(f))


def one(rows, **criteria):
    hits = [r for r in rows if all(r.get(k) == v for k, v in criteria.items())]
    assert len(hits) == 1, f"expected 1 row for {criteria}, found {len(hits)}"
    return hits[0]


def main():
    bank = load("bank_statement_2204_aug2026.csv")
    chk = load("qbo_register_checking_aug2026.csv")
    amex_qbo = load("qbo_register_amex_aug2026.csv")
    ap = load("ap_open_bills_31aug2026.csv")
    stripe = load("stripe_payout_ST-8H2K91.csv")

    with open(FINDINGS, newline="") as f:
        finding_ids = {r["id"] for r in csv.DictReader(f)}
    assert set(APPROVED) <= finding_ids, "approved finding missing from review_findings.csv"
    assert not set(APPROVED) & NOT_STAGED

    payout = one(stripe, payout_id="ST-8H2K91")
    gross, fee, net = money(payout["gross"]), money(payout["fee"]), money(payout["net"])
    transfer = -money(one(chk, payee="Online transfer")["amount"])
    reyes = -money(one(chk, payee="M. Reyes")["amount"])
    adobe = -money([r for r in chk if r["payee"] == "Adobe"][1]["amount"])
    bank_fee = -money(one(bank, description="MONTHLY SERVICE FEE")["amount"])
    interest = money(one(bank, description="INTEREST PAYMENT")["amount"])
    premium = -money(one(chk, payee="Hartwell Mutual")["amount"])
    prepaid = premium - (premium / 12).quantize(CENT)
    staples = money(one(amex_qbo, payee="Staples", amount_charge_positive="129.00")["amount_charge_positive"])
    grove = money(one(amex_qbo, payee="The Grove Bistro")["amount_charge_positive"])
    dup_bill = one(ap, bill_id="B-2204")
    northline = money(dup_bill["amount"])

    assert prepaid == Decimal("3300.00"), prepaid  # amount approved by the accountant

    # (finding_id, memo, [(account, debit, credit), ...])
    entries = [
        ("F01", f"Apply Stripe payout ST-8H2K91 to {payout['invoice']} {payout['customer']}; "
                f"reverse Uncategorized Income; record Stripe fee",
         [("Uncategorized Income", net, ZERO),
          ("Merchant Fees", fee, ZERO),
          ("Accounts Receivable", ZERO, gross)]),
        ("F02", "Reclass 2026-08-15 online transfer to Amex x3008 from Miscellaneous Expense to card payment",
         [(AMEX, transfer, ZERO),
          ("Miscellaneous Expense", ZERO, transfer)]),
        ("F03", "Reclass 2026-08-28 transfer to M. Reyes from Payroll Expense to Owner's Draw - pending client confirmation",
         [("Owner's Draw", reyes, ZERO),
          ("Payroll Expense", ZERO, reyes)]),
        ("F04", "Remove duplicate Adobe Creative Cloud entry dated 2026-08-12 (cleared bank once)",
         [(CHECKING, adobe, ZERO),
          ("Software Subscriptions", ZERO, adobe)]),
        ("F05", "Record August bank monthly service fee per statement 2026-08-31",
         [("Bank Service Charges", bank_fee, ZERO),
          (CHECKING, ZERO, bank_fee)]),
        ("F06", "Record August bank interest per statement 2026-08-31",
         [(CHECKING, interest, ZERO),
          ("Interest Income", ZERO, interest)]),
        ("F07", "Hartwell Mutual GL-55120 premium 2026-08-01 to 2027-07-31: defer 11 of 12 months to Prepaid Insurance",
         [("Prepaid Insurance", prepaid, ZERO),
          ("Insurance Expense", ZERO, prepaid)]),
        ("F11", f"Staples 2026-08-24 credit entered as charge: reverse +{staples} and record -{staples}",
         [(AMEX, 2 * staples, ZERO),
          ("Office Supplies", ZERO, 2 * staples)]),
        ("F12", "Recode The Grove Bistro 2026-08-19 from Office Supplies to Meals",
         [("Meals", grove, ZERO),
          ("Office Supplies", ZERO, grove)]),
        ("F15", f"Void duplicate bill {dup_bill['bill_id']} (repeats B-2201, {dup_bill['vendor']} invoice {dup_bill['vendor_bill_no']})",
         [("Accounts Payable", northline, ZERO),
          (dup_bill["account"], ZERO, northline)]),
    ]
    assert [e[0] for e in entries] == APPROVED

    rows = []
    for n, (finding_id, memo, lines) in enumerate(entries, start=1):
        je_id = f"JE{n:02d}"
        debits = sum(d for _, d, _ in lines)
        credits = sum(c for _, _, c in lines)
        assert debits == credits and debits > 0, f"{je_id} does not balance: Dr {debits} Cr {credits}"
        for account, debit, credit in lines:
            assert account in ACCOUNT_TYPES, f"unknown account type for {account}"
            rows.append({
                "je_id": je_id,
                "finding_id": finding_id,
                "account": account,
                "debit": f"{debit:.2f}" if debit else "",
                "credit": f"{credit:.2f}" if credit else "",
                "memo": memo,
                "status": "STAGED",
            })

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["je_id", "finding_id", "account", "debit", "credit", "memo", "status"])
        w.writeheader()
        w.writerows(rows)

    # ---- Totals and net income impact --------------------------------------
    total_dr = sum(money(r["debit"] or 0) for r in rows)
    total_cr = sum(money(r["credit"] or 0) for r in rows)
    assert total_dr == total_cr

    print(f"{'JE':<5} {'Finding':<8} {'Account':<24} {'Debit':>10} {'Credit':>10}")
    for r in rows:
        print(f"{r['je_id']:<5} {r['finding_id']:<8} {r['account']:<24} {r['debit']:>10} {r['credit']:>10}")
    print(f"{'':<39}{total_dr:>10,.2f} {total_cr:>10,.2f}")
    print(f"All {len(entries)} entries balance. Total debits {total_dr:,.2f} = total credits {total_cr:,.2f}.")

    # Net income effect: income credits increase it, expense debits reduce it.
    impact = {}
    for r in rows:
        kind = ACCOUNT_TYPES[r["account"]]
        if kind not in ("Income", "Expense"):
            continue
        effect = money(r["credit"] or 0) - money(r["debit"] or 0)
        impact[r["je_id"]] = impact.get(r["je_id"], ZERO) + effect
    print("\nNet income impact by entry (positive increases net income):")
    for je_id, effect in impact.items():
        fid = next(r["finding_id"] for r in rows if r["je_id"] == je_id)
        print(f"  {je_id} ({fid}) {effect:>10,.2f}")
    print(f"  Total      {sum(impact.values()):>10,.2f}")
    print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

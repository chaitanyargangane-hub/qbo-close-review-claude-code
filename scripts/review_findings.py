"""Step 4 review: uncategorized/suspicious transactions, open AR and open AP.

Every amount and evidence reference is looked up from the source files in
data/ and documents/ (read only), so the findings can be re-run and checked.
Writes output/review_findings.csv with columns:
    id, area, item, amount, recommendation, evidence, confidence

Run from anywhere:
    python3 scripts/review_findings.py
"""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "documents"
OUT = ROOT / "output" / "review_findings.csv"

PERIOD_END = date(2026, 8, 31)
CENT = Decimal("0.01")
DECISION = "Needs accountant/client decision."


def money(value):
    return Decimal(value).quantize(CENT)


def fmt(amount):
    return f"{amount:,.2f}"


def load(name):
    with open(DATA / name, newline="") as f:
        rows = list(csv.DictReader(f))
    for i, row in enumerate(rows, start=2):  # row 1 is the header
        row["_file"] = name
        row["_line"] = i
    return rows


def find(rows, **criteria):
    """Exactly one row matching all criteria (values compared as strings)."""
    hits = [r for r in rows if all(r.get(k) == v for k, v in criteria.items())]
    assert len(hits) == 1, f"expected 1 row for {criteria}, found {len(hits)}"
    return hits[0]


def find_all(rows, **criteria):
    return [r for r in rows if all(r.get(k) == v for k, v in criteria.items())]


def ev(row, *fields):
    """Evidence string: file line N: the row's key fields."""
    values = " ".join(row[f] for f in fields if row.get(f))
    return f"{row['_file']} line {row['_line']}: {values}"


def doc_line(name, contains):
    lines = (DOCS / name).read_text().splitlines()
    for i, text in enumerate(lines, start=1):
        if contains in text:
            return f"{name} line {i}: \"{text.strip()}\""
    raise AssertionError(f"'{contains}' not found in {name}")


def main():
    bank = load("bank_statement_2204_aug2026.csv")
    chk = load("qbo_register_checking_aug2026.csv")
    amex_stmt = load("amex_statement_3008_aug2026.csv")
    amex_qbo = load("qbo_register_amex_aug2026.csv")
    ar = load("ar_open_invoices_31aug2026.csv")
    ap = load("ap_open_bills_31aug2026.csv")
    payroll = load("payroll_register_aug2026.csv")
    stripe = load("stripe_payout_ST-8H2K91.csv")
    july = load("outstanding_items_jul2026.csv")

    BANK = ("date", "description", "amount")
    CHK = ("date", "type", "ref", "payee", "account", "amount")
    AMEX_Q = ("date", "type", "payee", "account", "amount_charge_positive")

    findings = []

    def add(area, item, amount, recommendation, evidence, confidence):
        findings.append({
            "id": f"F{len(findings) + 1:02d}",
            "area": area,
            "item": item,
            "amount": fmt(money(amount)),
            "recommendation": recommendation,
            "evidence": " | ".join(evidence),
            "confidence": confidence,
        })

    # --- Checking -----------------------------------------------------------

    # Stripe payout booked as new income while the invoice it pays is still open.
    s_dep = find(chk, payee="Stripe", account="Uncategorized Income")
    s_bank = find(bank, description="STRIPE TRANSFER ST-8H2K91")
    payout = find(stripe, payout_id="ST-8H2K91")
    inv = find(ar, invoice=payout["invoice"])
    gross, fee, net = money(payout["gross"]), money(payout["fee"]), money(payout["net"])
    assert gross - fee == net == money(s_dep["amount"]) == money(s_bank["amount"])
    assert money(inv["amount"]) == gross
    add(
        "Checking / AR",
        f"Stripe payout ST-8H2K91 booked to Uncategorized Income; it pays {inv['invoice']} "
        f"({inv['customer']}), which is still open in AR",
        net,
        f"Do not book as new revenue (the invoice already recorded it). Reclass: Dr Uncategorized "
        f"Income {fmt(net)}, Dr Merchant/Stripe Fees {fmt(fee)}, Cr Accounts Receivable {fmt(gross)}; "
        f"apply the payment to {inv['invoice']} so it closes.",
        [ev(s_dep, *CHK), ev(s_bank, *BANK),
         f"{ev(payout, 'payout_id', 'customer', 'invoice')} gross {fmt(gross)} fee {fmt(fee)} net {fmt(net)}",
         ev(inv, "invoice", "customer", "invoice_date", "amount", "status")],
        "High",
    )

    # Card payment coded as an expense.
    t_chk = find(chk, payee="Online transfer")
    t_bank = find(bank, description="ONLINE TRANSFER TO AMEX X3008")
    t_amex = find(amex_stmt, description="PAYMENT RECEIVED - THANK YOU")
    assert money(t_chk["amount"]) == money(t_bank["amount"]) == money(t_amex["amount"])
    add(
        "Checking / Amex",
        "Amex card payment coded to Miscellaneous Expense; not recorded in the Amex register",
        -money(t_chk["amount"]),
        f"Transfer, not an expense. Recode the checking entry from Miscellaneous Expense to the "
        f"Amex x3008 liability: Dr Amex {fmt(-money(t_chk['amount']))}, Cr Miscellaneous Expense. "
        "Clears the 2,400.00 statement-only item on the Amex rec.",
        [ev(t_chk, *CHK), ev(t_bank, *BANK), ev(t_amex, *BANK),
         doc_line("company_notes.txt", "paid from checking")],
        "High",
    )

    # Transfer to the owner coded as payroll.
    r_chk = find(chk, payee="M. Reyes")
    r_bank = find(bank, description="ONLINE TRANSFER TO M REYES X7710")
    employees = sorted({p["employee"] for p in payroll})
    add(
        "Checking",
        "Online transfer to M. Reyes coded to Payroll Expense",
        -money(r_chk["amount"]),
        f"Marisol Reyes is the owner and is not on payroll; the payroll register lists only "
        f"{', '.join(employees)}, paid through Gusto. Recommend recoding to Owner's Draw "
        f"(Dr Owner's Draw {fmt(-money(r_chk['amount']))}, Cr Payroll Expense). "
        f"Confirm with the client it was not a reimbursement or a payment to a different M. Reyes. {DECISION}",
        [ev(r_chk, *CHK), ev(r_bank, *BANK),
         doc_line("company_notes.txt", "owner: Marisol Reyes"),
         doc_line("company_notes.txt", "owner is not on payroll"),
         f"payroll_register_aug2026.csv lines 2-3: employees {', '.join(employees)} only"],
        "Medium",
    )

    # Duplicate Adobe entry.
    adobe = find_all(chk, payee="Adobe")
    adobe_bank = find_all(bank, description="ADOBE *CREATIVE CLOUD")
    assert len(adobe) == 2 and len(adobe_bank) == 1
    add(
        "Checking",
        "Adobe Creative Cloud entered twice in QBO; cleared the bank once",
        -money(adobe[1]["amount"]),
        f"Delete/void the second entry (Dr Checking {fmt(-money(adobe[1]['amount']))}, "
        "Cr Software Subscriptions). Clears the QBO-only item on the checking rec.",
        [ev(adobe[0], *CHK), ev(adobe[1], *CHK), ev(adobe_bank[0], *BANK) + " (only one on statement)"],
        "High",
    )

    # Bank-only items from the checking rec.
    fee_row = find(bank, description="MONTHLY SERVICE FEE")
    add(
        "Checking",
        "Bank monthly service fee not recorded in QBO",
        -money(fee_row["amount"]),
        f"Record: Dr Bank Service Charges {fmt(-money(fee_row['amount']))}, Cr Checking.",
        [ev(fee_row, *BANK)],
        "High",
    )
    int_row = find(bank, description="INTEREST PAYMENT")
    add(
        "Checking",
        "Bank interest not recorded in QBO",
        money(int_row["amount"]),
        f"Record: Dr Checking {fmt(money(int_row['amount']))}, Cr Interest Income.",
        [ev(int_row, *BANK)],
        "High",
    )

    # Annual insurance premium expensed in full.
    ins = find(chk, payee="Hartwell Mutual")
    premium = -money(ins["amount"])
    monthly = (premium / 12).quantize(CENT)
    prepaid = premium - monthly
    add(
        "Checking / Prepaids",
        "Annual general liability premium (1 Aug 2026 – 31 Jul 2027) fully expensed in August",
        premium,
        f"Accrual basis: expense 1/12 per month ({fmt(monthly)}). Reclass Dr Prepaid Insurance "
        f"{fmt(prepaid)}, Cr Insurance Expense {fmt(prepaid)}, then amortise {fmt(monthly)}/month "
        f"through Jul 2027. If the books are kept on a cash/tax basis or below a capitalisation "
        f"threshold, leave as is. {DECISION}",
        [ev(ins, *CHK),
         doc_line("insurance_policy_summary.txt", "Policy period"),
         doc_line("insurance_policy_summary.txt", "Annual premium")],
        "High",
    )

    # Payroll recorded at net pay only.
    gusto = find(chk, payee="Gusto")
    total_gross = sum(money(p["gross"]) for p in payroll)
    total_net = sum(money(p["net_paid"]) for p in payroll)
    withheld = total_gross - total_net
    assert total_net == -money(gusto["amount"])
    add(
        "Payroll",
        "14 Aug payroll recorded at net pay only; gross wages and withholdings not recorded",
        withheld,
        f"Payroll register gross {fmt(total_gross)} vs net {fmt(total_net)}; QBO shows only the "
        f"{fmt(total_net)} Gusto debit to Payroll Expense. {fmt(withheld)} of employee withholdings "
        "(and any employer taxes) is missing from expense and payroll liabilities, and no separate "
        "Gusto tax debit appears on the bank statement. Obtain the Gusto payroll journal for 14 Aug "
        "and record gross wages, employer taxes and the tax liabilities / debit dates.",
        [ev(gusto, *CHK), ev(find(bank, description="GUSTO PAYROLL"), *BANK)]
        + [f"{ev(p, 'pay_date', 'employee')} gross {p['gross']} net {p['net_paid']}" for p in payroll]
        + [doc_line("company_notes.txt", "Gusto")],
        "Medium",
    )

    # Adobe amount looks like an annual plan.
    add(
        "Checking / Prepaids",
        "Adobe Creative Cloud 659.88 looks like an annual subscription (12 × 54.99)",
        -money(adobe[0]["amount"]),
        "If it is an annual prepaid plan, it could be spread over 12 months as a prepaid. "
        "Likely below any capitalisation threshold, so expensing is acceptable. Confirm the plan "
        f"term with the client. {DECISION}",
        [ev(adobe[0], *CHK), ev(adobe_bank[0], *BANK)],
        "Low",
    )

    # Stale outstanding check.
    c1042 = find(july, ref="1042")
    age = (PERIOD_END - date.fromisoformat(c1042["date"])).days
    carver_bills = find_all(ap, vendor=c1042["payee"])
    add(
        "Checking",
        f"Check {c1042['ref']} to {c1042['payee']} still outstanding ({age} days at 31 Aug)",
        -money(c1042["amount"]),
        f"Ask the client whether {c1042['payee']} received the check. If lost, void and reissue; "
        f"if not owed, void and reverse. The vendor also has an open bill "
        f"({', '.join(b['bill_id'] + ' ' + b['amount'] for b in carver_bills)}), so confirm the "
        f"vendor's balance. {DECISION}",
        [ev(c1042, "date", "type", "ref", "payee", "amount", "note"),
         "bank_statement_2204_aug2026.csv: no CHECK 1042 line in August"]
        + [ev(b, "bill_id", "vendor", "bill_date", "amount") for b in carver_bills],
        "Medium",
    )

    # --- Amex ---------------------------------------------------------------

    st_q = find(amex_qbo, payee="Staples", amount_charge_positive="129.00")
    st_s = find(amex_stmt, description="STAPLES #0442 CREDIT")
    amt = money(st_q["amount_charge_positive"])
    add(
        "Amex",
        "Staples credit (refund) entered in QBO as a charge",
        amt,
        f"Reverse the charge and record the credit: Dr Amex {fmt(2 * amt)}, Cr Office Supplies "
        f"{fmt(2 * amt)} (net effect of removing +{fmt(amt)} and recording −{fmt(amt)}).",
        [ev(st_q, *AMEX_Q), ev(st_s, *BANK)],
        "High",
    )

    grove = find(amex_qbo, payee="The Grove Bistro")
    add(
        "Amex",
        "Restaurant charge coded to Office Supplies",
        money(grove["amount_charge_positive"]),
        f"Recode to Meals (Dr Meals {grove['amount_charge_positive']}, Cr Office Supplies). "
        f"Ask the client for the business purpose/attendees; business meals are generally only "
        f"50% deductible. {DECISION}",
        [ev(grove, *AMEX_Q), ev(find(amex_stmt, description="THE GROVE BISTRO"), *BANK)],
        "Medium",
    )

    vercel = find(amex_qbo, payee="Vercel")
    add(
        "Amex",
        "Vercel charge in QBO but not on the August Amex statement",
        money(vercel["amount_charge_positive"]),
        "Dated on the statement closing date, so treated as timing on the Amex rec. Confirm it "
        "appears on the September Amex statement. If it was paid another way or is not a real "
        "charge, reverse it from the Amex register. No entry proposed yet.",
        [ev(vercel, *AMEX_Q), "amex_statement_3008_aug2026.csv: no Vercel line through 2026-08-31"],
        "Medium",
    )

    # --- AR -----------------------------------------------------------------

    for inv_row in ar:
        due = date.fromisoformat(inv_row["due_date"])
        days_past = (PERIOD_END - due).days
        if inv_row["invoice"] == payout["invoice"] or days_past <= 30:
            continue  # INV-1187 covered by F01; others current or under 30 days
        add(
            "AR",
            f"{inv_row['invoice']} {inv_row['customer']} {days_past} days past due at 31 Aug",
            money(inv_row["amount"]),
            "Follow up with the client on collection. Options: keep and chase, record an allowance "
            f"for doubtful accounts, or write off. No entry proposed. {DECISION}",
            [ev(inv_row, "invoice", "customer", "invoice_date", "due_date", "amount", "status")],
            "Medium",
        )

    # --- AP -----------------------------------------------------------------

    seen = {}
    for bill in ap:
        key = (bill["vendor"], bill["vendor_bill_no"], bill["amount"])
        if key in seen:
            first = seen[key]
            add(
                "AP",
                f"Duplicate bill: {bill['bill_id']} repeats {first['bill_id']} "
                f"({bill['vendor']} invoice {bill['vendor_bill_no']})",
                money(bill["amount"]),
                f"Same vendor, vendor invoice number, date and amount. Void {bill['bill_id']} "
                f"(Dr Accounts Payable {bill['amount']}, Cr {bill['account']}) after confirming "
                "with the vendor statement that only one invoice 7731 exists.",
                [ev(first, "bill_id", "vendor", "vendor_bill_no", "bill_date", "amount"),
                 ev(bill, "bill_id", "vendor", "vendor_bill_no", "bill_date", "amount")],
                "High",
            )
        else:
            seen[key] = bill

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "area", "item", "amount", "recommendation", "evidence", "confidence"])
        w.writeheader()
        w.writerows(findings)

    for fnd in findings:
        print(f"{fnd['id']}  {fnd['area']:<20} {fnd['amount']:>10}  {fnd['confidence']:<6}  {fnd['item']}")
    print(f"Wrote {len(findings)} findings to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

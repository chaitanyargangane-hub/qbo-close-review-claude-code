"""Reconcile the Amex Business card (ending 3008) for August 2026.

The card is a liability: charges are positive (increase the amount owed),
payments and credits are negative, on both the statement and the QBO register.

Matches the Amex statement to the QBO Amex register (same amount, dates within
3 days, one-to-one), flags same-amount/opposite-sign pairs as likely sign
errors, lists unmatched items on each side, and writes output/recon_amex.md.

Source files in data/ are read only. Run from anywhere:
    python3 scripts/reconcile_amex.py
"""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "output" / "recon_amex.md"

STMT_FILE = "amex_statement_3008_aug2026.csv"
QBO_FILE = "qbo_register_amex_aug2026.csv"
BANK_FILE = "bank_statement_2204_aug2026.csv"
CHECKING_FILE = "qbo_register_checking_aug2026.csv"

MATCH_WINDOW_DAYS = 3
PERIOD_END = date(2026, 8, 31)
CENT = Decimal("0.01")

# Observations from reading the matched rows that do not affect the balance
# (account coding). Kept here so they appear in the report with evidence;
# the coding review itself is Step 4.
CODING_NOTES = [
    ("2026-08-19", "The Grove Bistro", "Office Supplies",
     "Restaurant charge coded to Office Supplies; likely Meals. Needs accountant decision on category."),
]


def money(value):
    return Decimal(value).quantize(CENT)


def fmt(amount):
    return f"{amount:,.2f}"


def read_csv(name, amount_col):
    with open(DATA / name, newline="") as f:
        rows = list(csv.DictReader(f))
    for i, row in enumerate(rows, start=2):  # row 1 is the header
        row["_file"] = name
        row["_line"] = i
        row["_date"] = date.fromisoformat(row["date"])
        row["_amount"] = money(row[amount_col])
    return rows


def label(row):
    if "description" in row:
        return row["description"]
    text = " ".join(p for p in (row.get("type", ""), row.get("ref", ""), row.get("payee", "")) if p)
    if row.get("account"):
        text += f" ({row['account']})"
    return text


def evidence(row):
    return f"{row['_file']} line {row['_line']}: {row['date']} {label(row)} {fmt(row['_amount'])}"


def days_apart(a, b):
    return abs((a["_date"] - b["_date"]).days)


def match(stmt_rows, qbo_rows, same_sign=True):
    """One-to-one match within the window, closest date wins.

    same_sign=True: amounts equal. same_sign=False: amounts equal and opposite.
    """
    pairs, used = [], set()
    for s in stmt_rows:
        target = s["_amount"] if same_sign else -s["_amount"]
        candidates = [
            (days_apart(s, q), idx)
            for idx, q in enumerate(qbo_rows)
            if idx not in used and q["_amount"] == target and days_apart(s, q) <= MATCH_WINDOW_DAYS
        ]
        if candidates:
            _, idx = min(candidates)
            used.add(idx)
            pairs.append((s, qbo_rows[idx]))
    paired_stmt = {id(s) for s, _ in pairs}
    return (
        pairs,
        [s for s in stmt_rows if id(s) not in paired_stmt],
        [q for i, q in enumerate(qbo_rows) if i not in used],
    )


def find_in(rows, amount, near, text=None):
    """Rows with the given amount within the window of `near`, optionally containing text."""
    return [
        r for r in rows
        if r["_amount"] == amount
        and days_apart(r, near) <= MATCH_WINDOW_DAYS
        and (text is None or text.lower() in label(r).lower())
    ]


def main():
    stmt_all = read_csv(STMT_FILE, "amount")
    qbo_all = read_csv(QBO_FILE, "amount_charge_positive")
    bank_all = read_csv(BANK_FILE, "amount")
    checking_all = read_csv(CHECKING_FILE, "amount")

    stmt_open = next(r for r in stmt_all if r["description"] == "OPENING BALANCE")
    stmt_close = next(r for r in stmt_all if r["description"] == "CLOSING BALANCE")
    stmt_txns = [r for r in stmt_all if "BALANCE" not in r["description"]]

    qbo_open = next(r for r in qbo_all if r["type"] == "Opening")
    qbo_txns = [r for r in qbo_all if r["type"] != "Opening"]

    # Source checks.
    stmt_rollforward = stmt_open["_amount"] + sum(r["_amount"] for r in stmt_txns)
    assert stmt_rollforward == stmt_close["_amount"], (
        f"Amex statement does not foot: {stmt_rollforward} vs {stmt_close['_amount']}"
    )
    opening_diff = stmt_open["_amount"] - qbo_open["_amount"]
    book_balance = qbo_open["_amount"] + sum(r["_amount"] for r in qbo_txns)

    # Pass 1: exact matches. Pass 2: same amount, opposite sign (likely sign error).
    matches, unmatched_stmt, unmatched_qbo = match(stmt_txns, qbo_txns)
    sign_errors, unmatched_stmt, unmatched_qbo = match(unmatched_stmt, unmatched_qbo, same_sign=False)

    # Timing items: QBO charges dated in the period but not yet on the statement.
    charges_in_transit = [q for q in unmatched_qbo if q["_amount"] > 0]
    other_qbo_only = [q for q in unmatched_qbo if q not in charges_in_transit]
    cit_total = sum(r["_amount"] for r in charges_in_transit)

    adjusted_stmt = stmt_close["_amount"] + cit_total
    difference = adjusted_stmt - book_balance

    # Book-side items: statement-only lines (book needs them), sign errors
    # (book needs statement amount minus QBO amount), other QBO-only lines (reverse).
    book_side = []
    for s in unmatched_stmt:
        book_side.append(("Statement only", s, s["_amount"], None))
    for s, q in sign_errors:
        book_side.append(("Sign error", s, s["_amount"] - q["_amount"], q))
    for q in other_qbo_only:
        book_side.append(("QBO only", q, -q["_amount"], None))
    explained = sum(effect for _, _, effect, _ in book_side)
    unexplained = difference - explained

    status = "RECONCILED" if difference == 0 else "NOT RECONCILED"

    # Cross-reference statement payments to the checking account.
    payment_links = []
    for side, row, _, _ in book_side:
        if side == "Statement only" and row["_amount"] < 0 and "PAYMENT" in row["description"]:
            bank_hits = find_in(bank_all, row["_amount"], row, "AMEX")
            chk_hits = []
            for b in bank_hits:
                chk_hits += find_in(checking_all, b["_amount"], b)
            payment_links.append((row, bank_hits, chk_hits))

    # ---- Report -------------------------------------------------------------
    L = []
    L.append("# Card reconciliation — Amex Business x3008 — 31 August 2026")
    L.append("")
    L.append("Copperfield Design Studio LLC (fictional). Generated by `scripts/reconcile_amex.py`.")
    L.append("Liability account: charges positive (increase amount owed); payments and credits negative.")
    L.append("Matching rule: same amount, dates within 3 days, one-to-one (closest date wins). "
             "A second pass pairs same-amount, opposite-sign items as likely sign errors.")
    L.append("Nothing has been posted. Proposed corrections are made in later steps.")
    L.append("")
    L.append(f"**Status: {status}. Unreconciled difference = {fmt(difference)}**")
    L.append("")

    L.append("## Summary")
    L.append("")
    L.append("| Line | Amount |")
    L.append("|---|---:|")
    L.append(f"| Balance owed per Amex statement, 31 Aug 2026 | {fmt(stmt_close['_amount'])} |")
    L.append(f"| Add: charges in QBO not yet on statement | {fmt(cit_total)} |")
    L.append("| Less: payments/credits in QBO not yet on statement | 0.00 |")
    L.append(f"| **Adjusted statement balance** | **{fmt(adjusted_stmt)}** |")
    L.append(f"| Balance owed per QBO register (book), 31 Aug 2026 | {fmt(book_balance)} |")
    L.append(f"| **Unreconciled difference (adjusted statement − book)** | **{fmt(difference)}** |")
    L.append("")
    L.append(
        f"Calculation: {fmt(stmt_close['_amount'])} + {fmt(cit_total)} = {fmt(adjusted_stmt)}; "
        f"{fmt(adjusted_stmt)} − {fmt(book_balance)} = {fmt(difference)}. "
        "A negative difference means QBO shows more owed than the statement supports."
    )
    L.append("")
    L.append(
        f"Book balance = QBO opening {fmt(qbo_open['_amount'])} + August register activity "
        f"{fmt(book_balance - qbo_open['_amount'])} = {fmt(book_balance)} (the register export has no closing row)."
    )
    L.append("")

    L.append("## Source checks")
    L.append("")
    L.append(
        f"- Statement foots: opening {fmt(stmt_open['_amount'])} + transactions "
        f"{fmt(stmt_rollforward - stmt_open['_amount'])} = {fmt(stmt_rollforward)}, "
        f"equals stated closing {fmt(stmt_close['_amount'])}."
    )
    L.append(
        f"- Opening tie-out: statement opening {fmt(stmt_open['_amount'])} − QBO opening "
        f"{fmt(qbo_open['_amount'])} = {fmt(opening_diff)} (no July items carried forward)."
    )
    L.append("")

    L.append("## Charges in QBO not yet on the statement (timing)")
    L.append("")
    L.append("| Date | Item | Amount | Evidence |")
    L.append("|---|---|---:|---|")
    for r in charges_in_transit:
        L.append(f"| {r['date']} | {label(r)} | {fmt(r['_amount'])} | {evidence(r)} |")
    L.append(f"| | **Total** | **{fmt(cit_total)}** | |")
    L.append("")
    L.append(
        "Treated as timing because the charge is dated on the statement closing date. "
        "Confirm it appears on the September statement; if it does not (e.g. it was charged to "
        "another card or entered in error), it becomes a book-side item and the difference "
        "changes by the same amount. Needs accountant/client confirmation."
    )
    L.append("")

    L.append("## Items that make QBO differ from the statement (book-side entries needed)")
    L.append("")
    L.append("Effect on book = change to the QBO liability needed (negative reduces the amount owed).")
    L.append("")
    L.append("| Type | Date | Item | Effect on book | Evidence |")
    L.append("|---|---|---|---:|---|")
    for side, row, effect, other in book_side:
        ev = evidence(row) if other is None else f"{evidence(row)}; vs {evidence(other)}"
        L.append(f"| {side} | {row['date']} | {label(row)} | {fmt(effect)} | {ev} |")
    L.append(f"| | | **Total** | **{fmt(explained)}** | |")
    L.append("")
    L.append(f"Difference {fmt(difference)} − items above {fmt(explained)} = unexplained {fmt(unexplained)}.")
    L.append("")

    L.append("### Explanation of each item")
    L.append("")
    for side, row, effect, other in book_side:
        if side == "Sign error":
            L.append(
                f"- **{row['description']} {fmt(row['_amount'])}** — the statement shows a credit "
                f"(refund) of {fmt(-row['_amount'])}, but QBO records it as a charge of "
                f"{fmt(other['_amount'])} ({other['account']}). Reversing the wrong charge and "
                f"recording the credit changes the book by {fmt(effect)} (2 × {fmt(-row['_amount'])})."
            )
        elif side == "Statement only" and row["_amount"] < 0:
            text = (
                f"- **{row['description']} {fmt(row['_amount'])}** — payment on the statement with no "
                f"entry in the QBO Amex register, so QBO overstates the amount owed by {fmt(-effect)}."
            )
            for pay, bank_hits, chk_hits in payment_links:
                if pay is row:
                    for b in bank_hits:
                        text += f" The cash left checking: {evidence(b)}."
                    for c in chk_hits:
                        text += (
                            f" In QBO checking it is booked as {evidence(c)} — i.e. to an expense "
                            "account instead of against the Amex liability. Recoding that checking "
                            "entry to the Amex card account fixes both registers; the checking cash "
                            "balance is unaffected."
                        )
            L.append(text)
        elif side == "Statement only":
            L.append(f"- **{row['description']} {fmt(row['_amount'])}** — on the statement, not in QBO.")
        else:
            L.append(f"- **{label(row)} {fmt(row['_amount'])}** — in QBO, not on the statement.")
    L.append("")
    L.append(
        "The account stays NOT RECONCILED until these items are dealt with and the difference "
        "is recomputed as 0.00. Treatment of each item needs accountant confirmation."
    )
    L.append("")

    L.append("## Unmatched items — full lists")
    L.append("")
    L.append("**On statement, not matched in QBO** (sign-error pairs included):")
    L.append("")
    for r in unmatched_stmt + [s for s, _ in sign_errors]:
        L.append(f"- {evidence(r)}")
    L.append("")
    L.append("**In QBO register, not matched on statement** (sign-error pairs included):")
    L.append("")
    for r in unmatched_qbo + [q for _, q in sign_errors]:
        L.append(f"- {evidence(r)}")
    L.append("")

    L.append(f"## Matched items ({len(matches)})")
    L.append("")
    L.append("Matching confirms the amount and date only, not the QBO account coding.")
    L.append("")
    L.append("| Statement date | Statement description | QBO date | QBO entry | Amount |")
    L.append("|---|---|---|---|---:|")
    for s, q in matches:
        L.append(f"| {s['date']} | {s['description']} | {q['date']} | {label(q)} | {fmt(s['_amount'])} |")
    L.append("")

    L.append("## Coding observations (do not affect the balance)")
    L.append("")
    for d, payee, account, note in CODING_NOTES:
        row = next(q for q in qbo_txns if q["date"] == d and q["payee"] == payee and q["account"] == account)
        L.append(f"- {evidence(row)} — {note}")
    L.append("")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(L))

    print(f"Statement closing balance      {fmt(stmt_close['_amount']):>10}")
    print(f"+ Charges not yet on statement {fmt(cit_total):>10}")
    print(f"= Adjusted statement balance   {fmt(adjusted_stmt):>10}")
    print(f"  Book balance (QBO)           {fmt(book_balance):>10}")
    print(f"  Unreconciled difference      {fmt(difference):>10}   -> {status}")
    print(f"  Explained by book-side items {fmt(explained)}; unexplained {fmt(unexplained)}")
    print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

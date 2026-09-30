"""Reconcile Operating Checking (ending 2204) for August 2026.

Matches the bank statement to the QBO checking register (same amount, dates
within 3 days, one-to-one), lists unmatched items on each side, rolls the July
outstanding items forward, and writes output/recon_checking.md.

Source files in data/ are read only. Run from anywhere:
    python3 scripts/reconcile_checking.py
"""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "output" / "recon_checking.md"
STAGED = ROOT / "output" / "staged_journal_entries.csv"
STAGED_ACCOUNT = "Checking x2204"

BANK_FILE = "bank_statement_2204_aug2026.csv"
QBO_FILE = "qbo_register_checking_aug2026.csv"
JULY_FILE = "outstanding_items_jul2026.csv"

MATCH_WINDOW_DAYS = 3
PERIOD_END = date(2026, 8, 31)
CENT = Decimal("0.01")


def money(value):
    return Decimal(value).quantize(CENT)


def fmt(amount):
    return f"{amount:,.2f}"


def read_csv(name):
    with open(DATA / name, newline="") as f:
        rows = list(csv.DictReader(f))
    for i, row in enumerate(rows, start=2):  # row 1 is the header
        row["_file"] = name
        row["_line"] = i
        row["_date"] = date.fromisoformat(row["date"])
        row["_amount"] = money(row["amount"])
    return rows


def label(row):
    """Short description used in the report and as evidence."""
    if row["_file"] == BANK_FILE:
        return row["description"]
    parts = [row.get("type", ""), row.get("ref", ""), row.get("payee", "")]
    text = " ".join(p for p in parts if p)
    if row.get("account"):
        text += f" ({row['account']})"
    return text


def evidence(row):
    return f"{row['_file']} line {row['_line']}: {row['date']} {label(row)} {fmt(row['_amount'])}"


def match(bank_rows, qbo_rows):
    """One-to-one match: same amount, |date diff| <= window, closest date wins."""
    matches = []
    used = set()
    for b in bank_rows:
        candidates = [
            (abs((q["_date"] - b["_date"]).days), idx)
            for idx, q in enumerate(qbo_rows)
            if idx not in used
            and q["_amount"] == b["_amount"]
            and abs((q["_date"] - b["_date"]).days) <= MATCH_WINDOW_DAYS
        ]
        if candidates:
            _, idx = min(candidates)
            used.add(idx)
            matches.append((b, qbo_rows[idx]))
    matched_bank = {id(b) for b, _ in matches}
    unmatched_bank = [b for b in bank_rows if id(b) not in matched_bank]
    unmatched_qbo = [q for i, q in enumerate(qbo_rows) if i not in used]
    return matches, unmatched_bank, unmatched_qbo


def july_item_cleared(item, bank_rows):
    """A July outstanding item clears if the bank shows the same amount (and check no. if any)."""
    for b in bank_rows:
        if b["_amount"] != item["_amount"]:
            continue
        if item["type"] == "Check" and item["ref"] and item["ref"] not in b["description"]:
            continue
        return b
    return None


def main():
    bank_all = read_csv(BANK_FILE)
    qbo_all = read_csv(QBO_FILE)
    july = read_csv(JULY_FILE)

    bank_open = next(r for r in bank_all if r["description"] == "OPENING BALANCE")
    bank_close = next(r for r in bank_all if r["description"] == "CLOSING BALANCE")
    bank_txns = [r for r in bank_all if "BALANCE" not in r["description"]]

    qbo_open = next(r for r in qbo_all if r["type"] == "Opening")
    qbo_txns = [r for r in qbo_all if r["type"] != "Opening"]

    # Integrity checks on the source files.
    bank_rollforward = bank_open["_amount"] + sum(r["_amount"] for r in bank_txns)
    assert bank_rollforward == bank_close["_amount"], (
        f"Bank statement does not foot: {bank_rollforward} vs {bank_close['_amount']}"
    )
    book_balance = qbo_open["_amount"] + sum(r["_amount"] for r in qbo_txns)

    # Opening tie-out: July adjusted bank should equal QBO opening.
    july_total = sum(r["_amount"] for r in july)
    opening_diff = (bank_open["_amount"] + july_total) - qbo_open["_amount"]

    matches, unmatched_bank, unmatched_qbo = match(bank_txns, qbo_txns)

    # July items: still outstanding unless they cleared the August bank statement.
    # (They are in the QBO opening balance, not the August register, so any
    # clearing would appear here as an unmatched bank line.)
    july_outstanding, july_cleared = [], []
    for item in july:
        hit = july_item_cleared(item, unmatched_bank)
        if hit:
            july_cleared.append((item, hit))
            unmatched_bank.remove(hit)
        else:
            july_outstanding.append(item)

    # Unmatched QBO items dated on/before period end are timing items.
    deposits_in_transit = [q for q in unmatched_qbo if q["_amount"] > 0 and q["type"] in ("Deposit", "Payment")]
    outstanding_checks = [q for q in unmatched_qbo if q["_amount"] < 0 and q["type"] == "Check"]
    outstanding_checks = july_outstanding + outstanding_checks
    other_book_only = [q for q in unmatched_qbo if q not in deposits_in_transit and q not in outstanding_checks]

    dit_total = sum(r["_amount"] for r in deposits_in_transit)
    oc_total = sum(r["_amount"] for r in outstanding_checks)  # negative
    adjusted_bank = bank_close["_amount"] + dit_total + oc_total
    difference = adjusted_bank - book_balance

    # Items that need a book-side entry: bank-only lines, and book-only lines
    # that are not timing items (their reversal).
    book_side_items = [(r, r["_amount"]) for r in unmatched_bank] + [(r, -r["_amount"]) for r in other_book_only]
    explained = sum(effect for _, effect in book_side_items)
    unexplained = difference - explained

    status = "RECONCILED" if difference == 0 else "NOT RECONCILED"

    # ---- Report -------------------------------------------------------------
    L = []
    L.append("# Bank reconciliation — Operating Checking x2204 — 31 August 2026")
    L.append("")
    L.append("Copperfield Design Studio LLC (fictional). Generated by `scripts/reconcile_checking.py`.")
    L.append("Matching rule: same amount, dates within 3 days, one-to-one (closest date wins).")
    L.append("Nothing has been posted. Proposed corrections are made in later steps.")
    L.append("")
    L.append(f"**Status: {status}. Unreconciled difference = {fmt(difference)}**")
    L.append("")

    L.append("## Summary")
    L.append("")
    L.append("| Line | Amount |")
    L.append("|---|---:|")
    L.append(f"| Balance per bank statement, 31 Aug 2026 | {fmt(bank_close['_amount'])} |")
    L.append(f"| Add: deposits in transit | {fmt(dit_total)} |")
    L.append(f"| Less: outstanding checks | {fmt(oc_total)} |")
    L.append(f"| **Adjusted bank balance** | **{fmt(adjusted_bank)}** |")
    L.append(f"| Balance per QBO register (book), 31 Aug 2026 | {fmt(book_balance)} |")
    L.append(f"| **Unreconciled difference (adjusted bank − book)** | **{fmt(difference)}** |")
    L.append("")
    L.append(
        f"Calculation: {fmt(bank_close['_amount'])} + {fmt(dit_total)} − {fmt(-oc_total)} "
        f"= {fmt(adjusted_bank)}; {fmt(adjusted_bank)} − {fmt(book_balance)} = {fmt(difference)}."
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
        f"- Bank statement foots: opening {fmt(bank_open['_amount'])} + transactions "
        f"{fmt(bank_rollforward - bank_open['_amount'])} = {fmt(bank_rollforward)}, "
        f"equals stated closing {fmt(bank_close['_amount'])}."
    )
    L.append(
        f"- Opening tie-out to July close: bank opening {fmt(bank_open['_amount'])} + July outstanding "
        f"items {fmt(july_total)} = {fmt(bank_open['_amount'] + july_total)}; QBO opening "
        f"{fmt(qbo_open['_amount'])}; difference {fmt(opening_diff)}."
    )
    L.append("")

    L.append("## Deposits in transit (in QBO, not yet on bank statement)")
    L.append("")
    L.append("| Date | Item | Amount | Evidence |")
    L.append("|---|---|---:|---|")
    for r in deposits_in_transit:
        L.append(f"| {r['date']} | {label(r)} | {fmt(r['_amount'])} | {evidence(r)} |")
    L.append(f"| | **Total** | **{fmt(dit_total)}** | |")
    L.append("")

    L.append("## Outstanding checks (in QBO, not yet cleared the bank)")
    L.append("")
    L.append("| Date | Item | Amount | Evidence |")
    L.append("|---|---|---:|---|")
    for r in outstanding_checks:
        if r["_file"] == JULY_FILE:
            item = f"Check {r['ref']} {r['payee']} (carried from July)"
            ev = f"{evidence_july(r)}; no matching line on {BANK_FILE}"
        else:
            item = label(r)
            ev = evidence(r)
        L.append(f"| {r['date']} | {item} | {fmt(r['_amount'])} | {ev} |")
    L.append(f"| | **Total** | **{fmt(oc_total)}** | |")
    L.append("")
    if july_cleared:
        L.append("July outstanding items that cleared in August:")
        for item, hit in july_cleared:
            L.append(f"- {evidence_july(item)} cleared by {evidence(hit)}")
        L.append("")

    L.append("## Reconciling items that need a book-side entry")
    L.append("")
    L.append("These are not timing items: they will not clear on their own. Effect on book = change to the QBO balance needed.")
    L.append("")
    L.append("| Side | Date | Item | Effect on book | Evidence |")
    L.append("|---|---|---|---:|---|")
    for r, effect in book_side_items:
        side = "Bank only" if r["_file"] == BANK_FILE else "QBO only"
        L.append(f"| {side} | {r['date']} | {label(r)} | {fmt(effect)} | {evidence(r)} |")
    L.append(f"| | | **Total** | **{fmt(explained)}** | |")
    L.append("")
    L.append(
        f"Difference {fmt(difference)} − items above {fmt(explained)} = unexplained {fmt(unexplained)}."
    )
    L.append("")
    L.append(
        "The account stays NOT RECONCILED until these items are dealt with and the difference is recomputed as 0.00. "
        "Treatment of each item (e.g. whether a QBO-only line is a duplicate) needs accountant confirmation."
    )
    L.append("")

    L.append("## Unmatched items — full lists")
    L.append("")
    L.append("**On bank statement, not in QBO:**")
    L.append("")
    for r in unmatched_bank or []:
        L.append(f"- {evidence(r)}")
    if not unmatched_bank:
        L.append("- none")
    L.append("")
    L.append("**In QBO register, not on bank statement:**")
    L.append("")
    for r in unmatched_qbo:
        L.append(f"- {evidence(r)}")
    if not unmatched_qbo:
        L.append("- none")
    L.append("")

    L.append(f"## Matched items ({len(matches)})")
    L.append("")
    L.append("Matching confirms the cash amount and date only. It does not confirm the QBO account coding, which is reviewed separately.")
    L.append("")
    L.append("| Bank date | Bank description | QBO date | QBO entry | Amount |")
    L.append("|---|---|---|---|---:|")
    for b, q in matches:
        L.append(f"| {b['date']} | {b['description']} | {q['date']} | {label(q)} | {fmt(b['_amount'])} |")
    L.append("")

    proforma = pro_forma(book_balance, adjusted_bank)
    if proforma:
        L.extend(proforma["report"])

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(L))

    print(f"Bank closing balance      {fmt(bank_close['_amount']):>12}")
    print(f"+ Deposits in transit     {fmt(dit_total):>12}")
    print(f"- Outstanding checks      {fmt(oc_total):>12}")
    print(f"= Adjusted bank balance   {fmt(adjusted_bank):>12}")
    print(f"  Book balance (QBO)      {fmt(book_balance):>12}")
    print(f"  Unreconciled difference {fmt(difference):>12}   -> {status}")
    print(f"  Explained by book-side items {fmt(explained)}; unexplained {fmt(unexplained)}")
    if proforma:
        print(f"  Pro forma after staged entries: book {fmt(proforma['book'])}, "
              f"difference {fmt(proforma['difference'])} (entries not posted)")
    print(f"Wrote {OUT.relative_to(ROOT)}")


def pro_forma(book_balance, adjusted_bank):
    """Re-run the difference as if the staged entries were posted (asset: debit increases)."""
    if not STAGED.exists():
        return None
    with open(STAGED, newline="") as f:
        lines = [r for r in csv.DictReader(f) if r["account"] == STAGED_ACCOUNT and r["status"] == "STAGED"]
    effect = sum(money(r["debit"] or 0) - money(r["credit"] or 0) for r in lines)
    book = book_balance + effect
    difference = adjusted_bank - book
    R = ["", "## Pro forma — as if the staged entries were posted", ""]
    R.append(f"Source: `output/staged_journal_entries.csv`, lines for account `{STAGED_ACCOUNT}`. "
             "These entries are STAGED, not posted; the QBO balance above is unchanged.")
    R.append("")
    R.append("| JE | Finding | Memo | Effect on book |")
    R.append("|---|---|---|---:|")
    for r in lines:
        R.append(f"| {r['je_id']} | {r['finding_id']} | {r['memo']} | "
                 f"{fmt(money(r['debit'] or 0) - money(r['credit'] or 0))} |")
    R.append(f"| | | **Total** | **{fmt(effect)}** |")
    R.append("")
    R.append(f"Pro forma book = {fmt(book_balance)} + {fmt(effect)} = {fmt(book)}.")
    R.append(f"Pro forma difference = adjusted bank {fmt(adjusted_bank)} − {fmt(book)} = **{fmt(difference)}**.")
    R.append("")
    if difference == 0:
        R.append("The account will reconcile (difference 0.00) once these entries are approved and posted, "
                 "with the timing items above still outstanding. Re-run after posting to confirm.")
    else:
        R.append("A difference remains after the staged entries; the account would still not reconcile.")
    return {"book": book, "difference": difference, "report": R}


def evidence_july(row):
    return f"{row['_file']} line {row['_line']}: {row['date']} {row['type']} {row['ref']} {row['payee']} {fmt(row['_amount'])}"


if __name__ == "__main__":
    main()

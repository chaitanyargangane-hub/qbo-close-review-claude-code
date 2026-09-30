# QBO month-end close review with Claude Code (fictional data)

A worked example of reviewing a US small business's month-end close in QuickBooks Online with
Claude Code as the first pass and an accountant making the decisions.

**All company data is fictional** (Copperfield Design Studio LLC, August 2026). Not client work.

## How the work is controlled
AI drafts matches and recommendations → accountant verifies each to source → accept / modify /
reject / escalate → corrections staged (never posted) → client approval → post → re-verify.
The rules Claude Code follows are in [CLAUDE.md](CLAUDE.md).

## What's here
- `data/` — bank and card statements, QBO register exports, AR/AP, payroll, Stripe payout
- `documents/` — company notes and the insurance policy summary
- `PROMPTS.md` — the prompts used, step by step
- `scripts/` — reconciliation scripts written by Claude Code during the session
- `output/` — reconciliations, findings, staged journal entries, open questions,
  the prompt log, and my review notes on what I accepted, rejected or corrected

Author: Chaitanya Gangane — Senior Accountant & FP&A Specialist

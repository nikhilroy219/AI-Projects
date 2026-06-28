"""
spendly_commands.py
Telegram command handlers for the three Spendly Finance Ops commands:
  /policycheck   — detect policy violations across all unreviewed transactions
  /closecheck    — month-end close readiness assessment
  /spendnarrative [query] — CFO-ready spend narrative answering a natural language question

Each handler:
  1. Reads data from Google Sheets via spendly_sheets.py
  2. Builds a focused prompt with the transaction CSV
  3. Calls Claude for the analysis
  4. Returns a formatted reply via Telegram
"""

import asyncio
import logging
import os
from datetime import date

from anthropic import Anthropic
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

import spendly_sheets as sheets
from spendly_policy import SPENDLY_EXPENSE_POLICY

load_dotenv()

log = logging.getLogger("spendly.commands")

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2000

claude = Anthropic(api_key=ANTHROPIC_KEY)

TODAY = lambda: date.today().strftime("%d %B %Y")  # noqa: E731


# ── Shared Claude helper ───────────────────────────────────────────────────────

def _ask_claude(system: str, user: str) -> str:
    """Simple single-turn Claude call. Returns reply text."""
    try:
        response = claude.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "\n".join(
            b.text for b in response.content if getattr(b, "type", "") == "text"
        ).strip()
    except Exception as e:
        log.error("Claude call failed: %s", e)
        return f"Error contacting AI brain: {e}"


# ── /policycheck ──────────────────────────────────────────────────────────────

POLICY_CHECK_SYSTEM = f"""You are Spendly's internal finance compliance assistant.
You know the full expense policy in detail (shown below). You are thorough, specific,
and flag issues by severity. Never make up transaction data — only analyse what is provided.

{SPENDLY_EXPENSE_POLICY}

When returning violations, group them by severity: HIGH, MEDIUM, LOW.
Use this exact format for each violation:

[TXN ID] — [Employee Name] — EUR [Amount] — [Merchant]
[Specific policy rule violated]
Action: [Recommended action]

At the top, include a one-line summary: "X violations found across Y transactions reviewed."
At the bottom, state how many transactions passed.
Label the date header: POLICY CHECK RESULTS — [date provided]."""


async def cmd_policycheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch transactions and run policy violation check via Claude."""
    await update.effective_chat.send_action(ChatAction.TYPING)

    try:
        transactions = await asyncio.to_thread(sheets.get_transactions)
    except RuntimeError as e:
        await update.message.reply_text(f"Could not read sheet: {e}")
        return

    if not transactions:
        await update.message.reply_text("No transaction data found in the sheet.")
        return

    # Filter to unreviewed (Policy Status blank or empty)
    unreviewed = [t for t in transactions if not t.get("Policy Status", "").strip()]
    if not unreviewed:
        await update.message.reply_text(
            "All transactions already have a Policy Status — nothing new to check."
        )
        return

    csv_data = sheets.transactions_to_csv_string(unreviewed)
    user_prompt = (
        f"Today's date: {TODAY()}\n\n"
        f"Here is the transaction data ({len(unreviewed)} transactions with no policy status):\n\n"
        f"{csv_data}\n\n"
        "Check each transaction against the Spendly expense policy. Return all violations "
        "grouped by severity (HIGH / MEDIUM / LOW) in the format specified. Be specific "
        "about which exact policy rule is violated for each transaction."
    )

    result = await asyncio.to_thread(_ask_claude, POLICY_CHECK_SYSTEM, user_prompt)
    await _send_long(update, context, result)


# ── /closecheck ───────────────────────────────────────────────────────────────

CLOSE_CHECK_SYSTEM = f"""You are Spendly's finance operations assistant helping the team
prepare for month-end close. You have full knowledge of the expense policy.

{SPENDLY_EXPENSE_POLICY}

You will receive two CSV datasets: transactions and the month-end tracker.
Analyse both and return a close-readiness report using this format:

MONTH-END CLOSE CHECK — [date]
Close readiness: READY / NOT READY

CRITICAL (must resolve before close)
- [bullet list of blockers]

ACTION REQUIRED THIS WEEK
- [bullet list — be specific: name employee, transaction ID, and what is needed]

LOW PRIORITY
- [minor items that can be noted but don't block close]

End with: "Estimated time to close-ready: X days if actions above completed today."
Never invent data — only analyse what is provided."""


async def cmd_closecheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch transactions + month-end tracker and run close-readiness check via Claude."""
    await update.effective_chat.send_action(ChatAction.TYPING)

    try:
        transactions = await asyncio.to_thread(sheets.get_transactions)
        tracker = await asyncio.to_thread(sheets.get_month_end_tracker)
    except RuntimeError as e:
        await update.message.reply_text(f"Could not read sheet: {e}")
        return

    if not transactions:
        await update.message.reply_text("No transaction data found in the sheet.")
        return

    txn_csv = sheets.transactions_to_csv_string(transactions)
    tracker_csv = sheets.transactions_to_csv_string(tracker) if tracker else "(Month End Tracker tab is empty)"

    user_prompt = (
        f"Today's date: {TODAY()}\n\n"
        f"TRANSACTIONS ({len(transactions)} rows):\n{txn_csv}\n\n"
        f"MONTH END TRACKER:\n{tracker_csv}\n\n"
        "Produce the month-end close readiness report as specified. Identify: "
        "uncoded transactions, missing receipts above EUR 25, unreviewed high-value "
        "transactions above EUR 500, and any flagged/prohibited transactions not resolved. "
        "Name specific employees and transaction IDs wherever possible."
    )

    result = await asyncio.to_thread(_ask_claude, CLOSE_CHECK_SYSTEM, user_prompt)
    await _send_long(update, context, result)


# ── /spendnarrative ───────────────────────────────────────────────────────────

NARRATIVE_SYSTEM = f"""You are Spendly's finance analyst assistant. You write precise,
data-driven spend narratives for the CFO and board.

{SPENDLY_EXPENSE_POLICY}

When given transaction data and a question, write a 3-paragraph CFO-ready narrative:
- Paragraph 1: What the data shows (totals, key transactions, concentrations)
- Paragraph 2: Policy compliance issues or risk factors in this data
- Paragraph 3: Recommended action

Use specific numbers, employee names, transaction IDs, and amounts. Write in clear
business English — confident, precise, no hedging. End with a concrete next step.
Label the header: SPEND NARRATIVE — [topic inferred from question] — [date]
Never invent data — only analyse what is provided."""


async def cmd_spendnarrative(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fetch all transactions and generate a CFO-ready narrative answering the user's query.
    Usage: /spendnarrative why is meals spend so high this month
    """
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "Please add a question after the command.\n"
            "Examples:\n"
            "  /spendnarrative why is meals spend so high this month\n"
            "  /spendnarrative summarise marketing department spend\n"
            "  /spendnarrative who are the top 3 spenders"
        )
        return

    await update.effective_chat.send_action(ChatAction.TYPING)

    try:
        transactions = await asyncio.to_thread(sheets.get_transactions)
    except RuntimeError as e:
        await update.message.reply_text(f"Could not read sheet: {e}")
        return

    if not transactions:
        await update.message.reply_text("No transaction data found in the sheet.")
        return

    csv_data = sheets.transactions_to_csv_string(transactions)
    user_prompt = (
        f"Today's date: {TODAY()}\n\n"
        f"TRANSACTIONS ({len(transactions)} rows):\n{csv_data}\n\n"
        f"Question from Finance: {query}\n\n"
        "Write the 3-paragraph CFO-ready narrative as specified."
    )

    result = await asyncio.to_thread(_ask_claude, NARRATIVE_SYSTEM, user_prompt)
    await _send_long(update, context, result)


# ── Utility ───────────────────────────────────────────────────────────────────

def _split_message(text: str, limit: int = 4000) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for para in text.split("\n"):
        while len(para) > limit:
            chunks.append(para[:limit])
            para = para[limit:]
        if len(current) + len(para) + 1 > limit:
            if current:
                chunks.append(current)
            current = para
        else:
            current = current + "\n" + para if current else para
    if current:
        chunks.append(current)
    return chunks


async def _send_long(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    for chunk in _split_message(text):
        await update.effective_message.reply_text(chunk)

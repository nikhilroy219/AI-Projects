# Local Finance/Ops AI Agent - Case Study

A purpose-built internal AI agent for a fictional fintech company's finance team. Built by extending the Jarvis personal assistant architecture (Telegram + Claude) with three finance-specific commands that solve real recurring problems in expense management and month-end close.

This is a case study demonstrating how the same AI agent architecture used for personal productivity can be adapted to solve specific operational problems in a finance team context.

## The Problem

Finance teams at B2B fintechs deal with three recurring problems that consume disproportionate time:

- Policy violations are caught at month-end, too late to chase receipts or reverse decisions
- Month-end close is a manual firefighting exercise - chasing receipts, identifying uncoded transactions, reconciling data under deadline pressure
- Spend narrative generation for leadership takes hours of Excel work to answer questions that should take minutes

This agent automates all three.

## What It Does

The agent lives in Telegram. Finance team members send commands and get instant, policy-aware analysis drawn from live transaction data in Google Sheets.

### Three core commands

| Command | What it does |
|---|---|
| /policycheck | Scans all unreviewed transactions for policy violations. Groups findings by severity (High / Medium / Low) with specific rule citations and recommended actions |
| /closecheck | Runs a month-end close readiness assessment. Returns a prioritised action list with employee names and transaction IDs |
| /spendnarrative [question] | Answers any spend question in a 3-paragraph CFO-ready narrative. e.g. why is meals spend so high, summarise marketing department spend, who are the top 3 spenders |

### Standard assistant commands (inherited from Jarvis)

/remember, /memories, /forget, /forgetall, /model, /voiceon, /voiceoff, /reset

## Architecture

```
spendly_agent/
├── bot.py                 # Main entry point - all command handlers registered here
├── jarvis_context.py      # System prompt - finance persona + embedded expense policy
├── jarvis_memory.py       # Persistent memory (jarvis_memory.json, created at runtime)
├── spendly_policy.py      # Policy rules as constants + full policy text for Claude prompts
├── spendly_sheets.py      # Google Sheets reader (gspread) - Transactions, Policy Rules, Month End Tracker
├── spendly_commands.py    # /policycheck, /closecheck, /spendnarrative handlers
├── .env                   # Credentials (not committed)
├── .env.example           # Credential template
└── requirements.txt       # Dependencies
```

Key design decisions:

- Built on the Jarvis skeleton - same Telegram interface, same memory system, same model switching. Only the finance-specific modules are new
- Expense policy is embedded directly in the Claude system prompt so every analysis decision is made against the same rules every time
- Google Sheets as the data source - no database setup, easy to populate with real or dummy data, readable by non-technical team members
- Three commands map to three distinct recurring tasks, not a general chatbot

## Stack

| Tool | Purpose |
|---|---|
| Python | Core application |
| Anthropic Claude (claude-sonnet-4-6) | Policy analysis, close assessment, narrative generation |
| python-telegram-bot | Telegram interface and command handling |
| gspread | Google Sheets read via Service Account |
| Groq Whisper | Voice note transcription (optional) |
| Edge TTS | Spoken replies (optional) |

## Data Source

Google Sheet: Spendly Finance Ops Agent - Master Data

Three tabs:

- Transactions - 25 rows of dummy data with deliberate policy violations pre-loaded
- Policy Rules - category limits and receipt thresholds
- Month End Tracker - per-transaction close status

The transaction data includes deliberate violations: over-limit meals, missing receipts, a prohibited merchant (Casino Berlin), an unknown merchant with no description, and uncoded transactions - giving the agent realistic material to work with.

## Setup

### Prerequisites

- Python 3.11+
- Telegram bot token (via @BotFather)
- Anthropic API key
- Groq API key (optional, enables voice)
- Google Service Account credentials

### Installation

1. Clone this repo
2. Install dependencies:

```
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in your credentials:

```
TELEGRAM_BOT_TOKEN=
ANTHROPIC_API_KEY=
GROQ_API_KEY=
OWNER_CHAT_ID=
GOOGLE_SHEET_ID=
GOOGLE_CREDENTIALS_FILE=credentials.json
```

4. Set up Google Sheets access:
   - Enable Google Sheets API and Google Drive API in Google Cloud Console
   - Create a Service Account and download `credentials.json`
   - Share the Google Sheet with the service account email
   - Add `credentials.json` to `.gitignore`

5. Run:

```
python bot.py
```

Send `/start` to your bot to get your chat ID. Add it to `.env` as `OWNER_CHAT_ID` and restart.

## Example Outputs

### /policycheck
```
POLICY CHECK RESULTS - 28 June 2026
6 violations found across 25 transactions reviewed.

HIGH SEVERITY
TXN025 - Tobias Muller - EUR 200 - Casino Berlin
Prohibited merchant category. Automatic rejection per policy.
Action: Reject immediately. Request employee justification on record.

MEDIUM SEVERITY
TXN010 - Felix Braun - EUR 520 - Bar Centrale (Meals)
Exceeds client entertainment limit (EUR 300). No receipt attached.
Action: Request receipt and written justification within 48 hours.
```

### /closecheck
```
MONTH-END CLOSE CHECK - 28 June 2026
Close readiness: NOT READY

CRITICAL
- 3 transactions above EUR 500 with no receipt
- TXN025 (Casino Berlin) - prohibited merchant, no decision on file
- TXN012 - uncoded, no category or description

ACTION REQUIRED THIS WEEK
- Chase receipts: Felix Braun (TXN010, TXN024), Tobias Muller (TXN025)
- Decision needed on TXN025 - reject or document justification
- Code TXN012 before close

Estimated time to close-ready: 2-3 days if actions completed today.
```

### /spendnarrative why is meals spend high
```
SPEND NARRATIVE - Meals & Entertainment - June 2026

Meals and entertainment spend totals EUR 1,859.50 across 6 transactions,
representing a 94% overage against the EUR 960 monthly budget...
```

## Notes

- The bot restricts all commands to OWNER_CHAT_ID - remove the owner check in `bot.py` to open access to a team
- `jarvis_memory.json` is created automatically on first `/remember` call and persists across restarts
- Voice input requires a valid `GROQ_API_KEY` - the bot still works without it
- Do not hardcode API keys anywhere in the codebase - all credentials must be in `.env`

---

Built by [Nikhil Roy](https://nikhilroy.lovable.app), Berlin

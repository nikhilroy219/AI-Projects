# JARVIS v1 — Setup Guide (no coding experience needed)

Your personal AI assistant: talk to it by text or voice notes on Telegram,
it answers with Claude's intelligence (and a British voice), knows your
context, and sends you a morning briefing at 07:30 Berlin time.

Total setup time: ~20 minutes. You only do this once.

---

## Step 1 — Create your private Telegram bot (3 min)

1. Open Telegram, search for **@BotFather** (verified, blue check).
2. Send it: `/newbot`
3. Give it a name: `JARVIS`
4. Give it a username, e.g. `nikhil_jarvis_bot` (must end in `bot`).
5. BotFather replies with a **token** (long string like `7421...:AAH...`).
   Copy it — you'll need it in Step 4.

## Step 2 — Get your two API keys (5 min)

- **Anthropic (the brain):** go to https://console.anthropic.com →
  API Keys → Create Key. Copy it. (You'll need billing set up — typical
  personal use costs a few euros per month.)
- **Groq (free, for voice transcription):** go to https://console.groq.com →
  API Keys → Create. Copy it. Free tier is plenty.

## Step 3 — Install Python (5 min, skip if installed)

- Download from https://www.python.org/downloads/ (version 3.11+).
- **Windows:** during install, tick the box "Add Python to PATH".
- **Mac:** just run the installer.

## Step 4 — Configure Jarvis (3 min)

1. Put this `jarvis` folder somewhere permanent, e.g. Documents.
2. Make a copy of the file `.env.example` and rename the copy to exactly
   `.env` (yes, starting with a dot).
3. Open `.env` in any text editor and paste your three keys from
   Steps 1–2 after the `=` signs. Save.

## Step 5 — Install and launch (3 min)

Open a terminal (Windows: PowerShell / Mac: Terminal), then:

```
cd path/to/your/jarvis folder
pip install -r requirements.txt
python bot.py
```

When you see `JARVIS online.` — it's alive. Leave that window open.

## Step 6 — First contact

1. In Telegram, open your bot and send: `/start`
2. It replies with your **chat ID**. Paste that number into `.env` as
   `OWNER_CHAT_ID`, then restart the bot (Ctrl+C in the terminal, then
   `python bot.py` again).
3. Done. Send it a voice note. Say hello to JARVIS.

---

## Daily use

| You do | Jarvis does |
|---|---|
| Send a voice note | Transcribes it, answers in text + voice |
| Send text | Answers in text (add `/voiceon` for audio) |
| `/briefing` | Searches the web, gives news in your format + top 3 actions |
| Nothing | Sends your briefing automatically at 07:30 Berlin time |
| `/voiceoff` | Runs silently — text only |
| `/reset` | Clears its short-term conversation memory |

To change what Jarvis knows about you, edit `jarvis_context.py` —
it's plain English, no code.

## Notes & limits (v1)

- The bot runs while your laptop is on and `python bot.py` is running.
  If the laptop sleeps, Jarvis sleeps. (v3 moves it to a cheap server.)
- Conversation memory resets when you restart the bot.
- Anyone who finds your bot's username could message it — keep the
  username obscure. (We can add an owner-only lock in v1.1.)

## Troubleshooting

- `pip` not found → reinstall Python with "Add to PATH" ticked.
- "Missing keys" error → your `.env` file isn't named exactly `.env`
  or a key wasn't pasted.
- Voice note fails → check your Groq key.

# Jarvis — Local AI Personal Assistant

A self-hosted personal AI assistant you talk to over Telegram, powered by Claude (Anthropic). Reachable by text or voice from anywhere, it answers with real-time web search, remembers context across sessions, switches between models on demand, and delivers a scheduled daily briefing, all running locally on your own machine with no manual input required.

## What It Does

Most people interact with AI through a browser tab they have to open, ask, and close. This project turns Claude into an always-on assistant that lives on your own machine and reaches you on your phone.

Once running, it:

- Listens for messages on a private Telegram bot (text or voice notes)
- Transcribes voice notes to text (Groq Whisper) and can reply in a natural synthesized voice (Edge TTS)
- Answers using real-time web search for anything current, not just training data
- Remembers durable facts about you across restarts, either saved explicitly or captured automatically from conversation
- Sends a compiled daily briefing on a schedule, unattended, every morning
- Lets you switch the underlying model mid-conversation to trade off depth, speed, and cost
- Stays private: only your own Telegram account can talk to it

## Architecture

bot.py             Telegram interface + orchestration (handlers, scheduler, voice I/O)
jarvis_context.py  Assistant personality and system prompt
jarvis_memory.py   Persistent memory (load / save / inspect, stored as JSON)

Key design decisions:

- Runs entirely locally against the Anthropic API; no third-party server holds your data
- The static system prompt is cached while live memory is appended fresh each call, keeping the assistant context-aware without re-sending everything every time
- Memory is plain, human-readable JSON you can open and edit by hand
- Owner-lock keyed to a single Telegram chat ID, so the bot ignores everyone else
- Auto-memory runs after the reply is sent, so it never adds latency to your conversation

## Commands

| Command | Description |
|---|---|
| /briefing | Generate the daily news + priorities briefing now |
| /remember <text> | Save a fact to long-term memory |
| /memories | List everything it remembers |
| /forget <n> / /forgetall | Remove one memory / clear all |
| /automem on or off | Toggle automatic memory saving |
| /model opus or sonnet or haiku | Switch the underlying model |
| /voiceon / /voiceoff | Toggle spoken audio replies |
| /reset | Clear the running conversation context |

Plain text or a voice note works any time for normal conversation.

## Stack

| Tool | Purpose |
|---|---|
| Python | Core application |
| Anthropic Claude | Reasoning, conversation, briefings |
| python-telegram-bot | Telegram interface and scheduler |
| Groq Whisper | Voice note transcription (speech-to-text) |
| Edge TTS | Spoken replies (text-to-speech) |

## Setup

### Prerequisites

- Python 3.11+
- A Telegram account
- Anthropic API key
- Groq API key (free; used for voice transcription)

### Installation

1. Clone this repo
2. Create a Telegram bot via @BotFather and copy the token
3. Copy .env.example to .env and fill in your keys:

TELEGRAM_BOT_TOKEN=
ANTHROPIC_API_KEY=
GROQ_API_KEY=
OWNER_CHAT_ID=

4. Install dependencies and run:

pip install -r requirements.txt
python bot.py

5. Send /start to your bot. It replies with your chat ID. Put that in .env as OWNER_CHAT_ID to enable the owner-lock and scheduled briefing, then restart.

## Notes

- Runs while the host machine is on and the script is running
- API keys live only in your local .env and are never committed
- Built as a personal project to explore always-on, self-hosted AI assistants

## Author

Nikhil Roy, Berlin-based operator with a background in project management, business development, and tech and AI workflow automation.

Portfolio: https://nikhilroy.lovable.app

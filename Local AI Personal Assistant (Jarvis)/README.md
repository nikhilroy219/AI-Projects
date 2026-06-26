# Jarvis — Local AI Personal Assistant

A self-hosted personal AI assistant you talk to over Telegram, powered by Claude (Anthropic). Reachable by text or voice from anywhere, it answers with real-time web search, remembers context across sessions, switches between models on demand, and delivers a scheduled daily briefing, all running locally on your own machine with no manual input required.

## What It Does

A chat app gives you an AI you have to open and ask. This project gives you one that runs on its own machine, reaches you on your phone, and acts on its own schedule, the difference between a tool you operate and an assistant that works in the background.

What makes it more than a chat window:

- It runs unattended. A built-in scheduler lets it act without being prompted. Out of the box it compiles and sends a daily briefing every morning; the same scheduling layer is built to take on any recurring task it has the tools to perform, from periodic reports to automated check-ins.
- It lives locally and is yours to extend. Self-hosted on your own machine against the Anthropic API, with a clean modular structure (interface, context, memory) designed so new capabilities and background jobs can be bolted on without touching the core.
- It remembers you over time. Durable facts persist across restarts, saved explicitly or captured automatically from conversation, and stored as plain JSON you fully own and can edit by hand.
- It meets you where you are. A private Telegram bot reachable by text or voice note from any device. Voice in is transcribed (Groq Whisper); replies can come back as a natural synthesized voice (Edge TTS).
- It stays current and flexible. Real-time web search for anything beyond training data, and on-demand model switching to trade off depth, speed, and cost per task.
- It stays private. Locked to a single Telegram account; every other user is ignored.

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

"""
JARVIS v2a - Personal AI assistant for Nikhil Roy
Telegram | Claude brain | Voice | Daily briefing
+ Persistent memory  + Prompt caching  + Model switching  + Always-on web

Run with:  python bot.py
"""

import asyncio
import json
import logging
import os
import tempfile
from datetime import time

import edge_tts
from anthropic import Anthropic
from dotenv import load_dotenv
from groq import Groq
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from zoneinfo import ZoneInfo

import jarvis_memory as mem
from jarvis_context import JARVIS_SYSTEM_PROMPT

# ----------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")

# Model strings (Anthropic API)
MODEL_SONNET = "claude-sonnet-4-6"
MODEL_OPUS = "claude-opus-4-8"
MODEL_HAIKU = "claude-haiku-4-5-20251001"
DEFAULT_MODEL = MODEL_SONNET

TTS_VOICE = "en-GB-RyanNeural"
BERLIN = ZoneInfo("Europe/Berlin")
BRIEFING_HOUR, BRIEFING_MINUTE = 7, 30
MAX_HISTORY = 24

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO
)
log = logging.getLogger("jarvis")

claude = Anthropic(api_key=ANTHROPIC_KEY)
groq = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

histories: dict[int, list] = {}
voice_replies: dict[int, bool] = {}
current_model: dict[int, str] = {}
automem_on: dict[int, bool] = {}


def _owner_ok(chat_id: int) -> bool:
    if not OWNER_CHAT_ID:
        return True
    return str(chat_id) == str(OWNER_CHAT_ID)


# ----------------------------------------------------------------------
# Claude brain (caching + always-on web + model switch)
# ----------------------------------------------------------------------
def ask_claude(
    chat_id: int,
    user_text: str,
    web_max_uses: int = 5,
    use_history: bool = True,
    model: str | None = None,
) -> str:
    if use_history:
        history = histories.setdefault(chat_id, [])
        history.append({"role": "user", "content": user_text})
        messages = history[-MAX_HISTORY:]
    else:
        messages = [{"role": "user", "content": user_text}]

    # System prompt: static base is cached; live memory block is appended fresh.
    system_blocks = [
        {
            "type": "text",
            "text": JARVIS_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        },
        {"type": "text", "text": mem.memory_block()},
    ]

    tools = [
        {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": web_max_uses,
            "user_location": {
                "type": "approximate",
                "city": "Berlin",
                "region": "Berlin",
                "country": "DE",
                "timezone": "Europe/Berlin",
            },
        }
    ]

    try:
        response = claude.messages.create(
            model=model or current_model.get(chat_id, DEFAULT_MODEL),
            max_tokens=3000,
            system=system_blocks,
            messages=messages,
            tools=tools,
        )
    except Exception as e:
        log.error("Claude call failed: %s", e)
        return f"My connection to the brain failed, Sir: {e}"

    reply = "\n".join(
        b.text for b in response.content if getattr(b, "type", "") == "text"
    ).strip()

    if use_history:
        history.append({"role": "assistant", "content": reply or "(no reply)"})
    return reply or "I produced no response, Sir. Try rephrasing."


def auto_remember(user_text: str, reply: str) -> str | None:
    """Cheap Haiku call to extract a durable fact worth saving. Best-effort."""
    try:
        r = claude.messages.create(
            model=MODEL_HAIKU,
            max_tokens=150,
            system=(
                "You extract durable, factual things worth remembering long-term "
                "about the user (plans, deadlines, preferences, life facts, decisions). "
                "Ignore small talk, questions, and transient chatter. "
                'Respond ONLY with JSON: {"remember": false} OR '
                '{"remember": true, "fact": "<one concise sentence in third person>"}.'
            ),
            messages=[{
                "role": "user",
                "content": f"User said: {user_text}\nAssistant replied: {reply}",
            }],
        )
        raw = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        if data.get("remember") and data.get("fact"):
            if mem.add_memory(data["fact"]):
                return data["fact"]
    except Exception as e:
        log.warning("auto_remember skipped: %s", e)
    return None


# ----------------------------------------------------------------------
# Voice helpers
# ----------------------------------------------------------------------
def transcribe(file_path: str) -> str:
    if not groq:
        raise RuntimeError("GROQ_API_KEY missing - voice input disabled.")
    with open(file_path, "rb") as f:
        result = groq.audio.transcriptions.create(
            model="whisper-large-v3", file=(os.path.basename(file_path), f)
        )
    return result.text.strip()


async def speak(text: str, out_path: str):
    spoken = text if len(text) <= 1200 else text[:1200] + " ... full details in the text, Sir."
    await edge_tts.Communicate(spoken, TTS_VOICE).save(out_path)


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


async def send_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    chat_id = update.effective_chat.id
    for chunk in _split_message(text):
        await update.effective_message.reply_text(chunk)
    if voice_replies.get(chat_id, False):
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                mp3_path = tmp.name
            await speak(text, mp3_path)
            with open(mp3_path, "rb") as audio:
                await context.bot.send_audio(chat_id, audio, title="JARVIS")
            os.unlink(mp3_path)
        except Exception as e:
            log.warning("TTS failed: %s", e)


# ----------------------------------------------------------------------
# Handlers
# ----------------------------------------------------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        "JARVIS v2b online. At your service, Sir.\n\n"
        f"Your chat ID is {chat_id} (put in .env as OWNER_CHAT_ID).\n\n"
        "Commands:\n"
        "/briefing - news + day plan\n"
        "/remember <text> - save a fact to memory\n"
        "/memories - list what I remember\n"
        "/forget <number> - remove one memory\n"
        "/forgetall - wipe memory\n"
        "/automem on|off - auto-save facts (default on)\n"
        "/model opus|sonnet|haiku - switch my brain\n"
        "/voiceon /voiceoff - audio replies\n"
        "/reset - clear conversation memory\n\n"
        "Text or voice note me anytime. I have live web search and memory."
    )


async def cmd_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    await update.effective_chat.send_action(ChatAction.TYPING)
    text = await asyncio.to_thread(
        ask_claude,
        update.effective_chat.id,
        "Give me my daily briefing. Use your web_search tool to find today's real "
        "news before writing - search across Germany/EU, India, China, US, and global. "
        "Then format in my standard briefing structure and finish with my top 3 actions.",
        web_max_uses=8,
        use_history=False,
    )
    await send_reply(update, context, text)


async def cmd_remember(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    fact = " ".join(context.args).strip()
    if not fact:
        await update.message.reply_text("Tell me what to remember: /remember <text>")
        return
    ok = mem.add_memory(fact)
    await update.message.reply_text(
        f"Noted, Sir: {fact}" if ok else "I already had that one, Sir."
    )


async def cmd_memories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    facts = mem.list_memories()
    if not facts:
        await update.message.reply_text("Nothing saved yet, Sir.")
        return
    lines = "\n".join(f"{i}. {t}" for i, t in enumerate(facts, 1))
    await update.message.reply_text("Here's what I remember:\n\n" + lines)


async def cmd_forget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    try:
        idx = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /forget <number> (see /memories)")
        return
    removed = mem.forget(idx)
    await update.message.reply_text(
        f"Forgotten: {removed}" if removed else "No memory at that number, Sir."
    )


async def cmd_forgetall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    n = mem.forget_all()
    await update.message.reply_text(f"Wiped {n} memories, Sir. Clean slate.")


async def cmd_automem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    arg = (context.args[0].lower() if context.args else "")
    if arg not in ("on", "off"):
        await update.message.reply_text("Usage: /automem on  or  /automem off")
        return
    automem_on[update.effective_chat.id] = (arg == "on")
    await update.message.reply_text(f"Auto-memory {arg}, Sir.")


async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    choice = (context.args[0].lower() if context.args else "")
    mapping = {"opus": MODEL_OPUS, "sonnet": MODEL_SONNET, "haiku": MODEL_HAIKU}
    if choice not in mapping:
        cur = current_model.get(update.effective_chat.id, DEFAULT_MODEL)
        await update.message.reply_text(
            f"Current brain: {cur}\nUsage: /model opus|sonnet|haiku"
        )
        return
    current_model[update.effective_chat.id] = mapping[choice]
    await update.message.reply_text(
        f"Brain switched to {choice}, Sir." +
        ("  (slower, deepest reasoning)" if choice == "opus" else
         "  (fast, light)" if choice == "haiku" else "  (balanced default)")
    )


async def cmd_voiceon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    voice_replies[update.effective_chat.id] = True
    await update.message.reply_text("Audio replies enabled, Sir.")


async def cmd_voiceoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    voice_replies[update.effective_chat.id] = False
    await update.message.reply_text("Running silently. Text only.")


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    histories.pop(update.effective_chat.id, None)
    await update.message.reply_text(
        "Conversation memory cleared, Sir. (Saved facts kept - use /forgetall for those.)"
    )


async def _handle_message(update, context, user_text: str):
    chat_id = update.effective_chat.id
    reply = await asyncio.to_thread(ask_claude, chat_id, user_text)
    await send_reply(update, context, reply)
    # Auto-memory runs AFTER the reply is sent, so no added latency.
    if automem_on.get(chat_id, True) and len(user_text) > 12:
        saved = await asyncio.to_thread(auto_remember, user_text, reply)
        if saved:
            await context.bot.send_message(chat_id, f"\U0001F9E0 Noted to memory: {saved}")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    await update.effective_chat.send_action(ChatAction.TYPING)
    await _handle_message(update, context, update.message.text)


async def on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    await update.effective_chat.send_action(ChatAction.TYPING)
    tg_file = await update.message.voice.get_file()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        ogg_path = tmp.name
    await tg_file.download_to_drive(ogg_path)
    try:
        heard = await asyncio.to_thread(transcribe, ogg_path)
    finally:
        os.unlink(ogg_path)
    await update.message.reply_text(f'\U0001F399 "{heard}"')
    voice_replies.setdefault(update.effective_chat.id, True)
    await _handle_message(update, context, heard)


async def daily_briefing_job(context: ContextTypes.DEFAULT_TYPE):
    if not OWNER_CHAT_ID:
        return
    chat_id = int(OWNER_CHAT_ID)
    text = await asyncio.to_thread(
        ask_claude,
        chat_id,
        "Good morning. Use your web_search tool to find today's real news, then give "
        "my briefing in standard format (Germany/EU, India, China, US, global) and my "
        "top 3 actions for the day.",
        web_max_uses=8,
        use_history=False,
    )
    for chunk in _split_message("\u2600\ufe0f Morning briefing:\n\n" + text):
        await context.bot.send_message(chat_id, chunk)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    if not TELEGRAM_TOKEN or not ANTHROPIC_KEY:
        raise SystemExit("Missing keys. Fill in .env (TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY).")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("briefing", cmd_briefing))
    app.add_handler(CommandHandler("remember", cmd_remember))
    app.add_handler(CommandHandler("memories", cmd_memories))
    app.add_handler(CommandHandler("forget", cmd_forget))
    app.add_handler(CommandHandler("forgetall", cmd_forgetall))
    app.add_handler(CommandHandler("automem", cmd_automem))
    app.add_handler(CommandHandler("model", cmd_model))
    app.add_handler(CommandHandler("voiceon", cmd_voiceon))
    app.add_handler(CommandHandler("voiceoff", cmd_voiceoff))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(MessageHandler(filters.VOICE, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.job_queue.run_daily(
        daily_briefing_job, time(BRIEFING_HOUR, BRIEFING_MINUTE, tzinfo=BERLIN)
    )

    log.info("JARVIS v2b online.")
    app.run_polling()


if __name__ == "__main__":
    main()

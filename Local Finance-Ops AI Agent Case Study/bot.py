"""
Spendly Finance Ops AI Agent
Built on the Jarvis v2 architecture (python-telegram-bot + Claude).

Adds three finance-specific commands on top of the Jarvis skeleton:
  /policycheck      — Policy violation detector
  /closecheck       — Month-end close readiness checker
  /spendnarrative   — CFO-ready spend narrative generator

All original Jarvis commands are preserved and functional.

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
from spendly_commands import (
    cmd_closecheck,
    cmd_policycheck,
    cmd_spendnarrative,
)

# ── Setup ─────────────────────────────────────────────────────────────────────
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")

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
log = logging.getLogger("spendly")

claude = Anthropic(api_key=ANTHROPIC_KEY)
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

histories: dict[int, list] = {}
voice_replies: dict[int, bool] = {}
current_model: dict[int, str] = {}
automem_on: dict[int, bool] = {}


def _owner_ok(chat_id: int) -> bool:
    if not OWNER_CHAT_ID:
        return True
    return str(chat_id) == str(OWNER_CHAT_ID)


# ── Claude brain ──────────────────────────────────────────────────────────────

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
        return f"Connection to AI brain failed: {e}"

    reply = "\n".join(
        b.text for b in response.content if getattr(b, "type", "") == "text"
    ).strip()

    if use_history:
        history.append({"role": "assistant", "content": reply or "(no reply)"})
    return reply or "No response generated. Try rephrasing."


def auto_remember(user_text: str, reply: str) -> str | None:
    """Cheap Haiku call to extract a durable fact worth saving."""
    try:
        r = claude.messages.create(
            model=MODEL_HAIKU,
            max_tokens=150,
            system=(
                "You extract durable facts worth remembering long-term about the finance "
                "team's context (decisions, patterns, open issues, team notes). "
                "Ignore transient queries. "
                'Respond ONLY with JSON: {"remember": false} OR '
                '{"remember": true, "fact": "<one concise sentence>"}'
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


# ── Voice helpers ─────────────────────────────────────────────────────────────

def transcribe(file_path: str) -> str:
    if not groq_client:
        raise RuntimeError("GROQ_API_KEY missing — voice input disabled.")
    with open(file_path, "rb") as f:
        result = groq_client.audio.transcriptions.create(
            model="whisper-large-v3", file=(os.path.basename(file_path), f)
        )
    return result.text.strip()


async def speak(text: str, out_path: str):
    spoken = text if len(text) <= 1200 else text[:1200] + " ... full details in the text."
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
                await context.bot.send_audio(chat_id, audio, title="Spendly Agent")
            os.unlink(mp3_path)
        except Exception as e:
            log.warning("TTS failed: %s", e)


# ── Handlers — base Jarvis commands ───────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        "Spendly Finance Ops Agent online.\n\n"
        f"Chat ID: {chat_id}\n\n"
        "FINANCE COMMANDS\n"
        "/policycheck — scan all transactions for policy violations\n"
        "/closecheck — month-end close readiness report\n"
        "/spendnarrative [question] — CFO-ready spend analysis\n\n"
        "ASSISTANT COMMANDS\n"
        "/remember [text] — save a note\n"
        "/memories — list saved notes\n"
        "/forget [number] — remove a note\n"
        "/model opus|sonnet|haiku — switch AI model\n"
        "/voiceon /voiceoff — audio replies\n"
        "/reset — clear conversation history\n\n"
        "You can also send any free-text question about expenses, policy, or finance ops."
    )


async def cmd_remember(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    fact = " ".join(context.args).strip()
    if not fact:
        await update.message.reply_text("Usage: /remember [text]")
        return
    ok = mem.add_memory(fact)
    await update.message.reply_text(
        f"Noted: {fact}" if ok else "Already have that one."
    )


async def cmd_memories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    facts = mem.list_memories()
    if not facts:
        await update.message.reply_text("Nothing saved yet.")
        return
    lines = "\n".join(f"{i}. {t}" for i, t in enumerate(facts, 1))
    await update.message.reply_text("Saved notes:\n\n" + lines)


async def cmd_forget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    try:
        idx = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /forget [number] (see /memories)")
        return
    removed = mem.forget(idx)
    await update.message.reply_text(
        f"Forgotten: {removed}" if removed else "No note at that number."
    )


async def cmd_forgetall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    n = mem.forget_all()
    await update.message.reply_text(f"Wiped {n} notes. Clean slate.")


async def cmd_automem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    arg = (context.args[0].lower() if context.args else "")
    if arg not in ("on", "off"):
        await update.message.reply_text("Usage: /automem on  or  /automem off")
        return
    automem_on[update.effective_chat.id] = (arg == "on")
    await update.message.reply_text(f"Auto-memory {arg}.")


async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    choice = (context.args[0].lower() if context.args else "")
    mapping = {"opus": MODEL_OPUS, "sonnet": MODEL_SONNET, "haiku": MODEL_HAIKU}
    if choice not in mapping:
        cur = current_model.get(update.effective_chat.id, DEFAULT_MODEL)
        await update.message.reply_text(
            f"Current model: {cur}\nUsage: /model opus|sonnet|haiku"
        )
        return
    current_model[update.effective_chat.id] = mapping[choice]
    await update.message.reply_text(f"Switched to {choice}.")


async def cmd_voiceon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    voice_replies[update.effective_chat.id] = True
    await update.message.reply_text("Audio replies enabled.")


async def cmd_voiceoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    voice_replies[update.effective_chat.id] = False
    await update.message.reply_text("Audio replies off.")


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _owner_ok(update.effective_chat.id):
        return
    histories.pop(update.effective_chat.id, None)
    await update.message.reply_text(
        "Conversation cleared. (Saved notes kept — use /forgetall for those.)"
    )


# ── Free-text + voice ─────────────────────────────────────────────────────────

async def _handle_message(update, context, user_text: str):
    chat_id = update.effective_chat.id
    reply = await asyncio.to_thread(ask_claude, chat_id, user_text)
    await send_reply(update, context, reply)
    if automem_on.get(chat_id, True) and len(user_text) > 12:
        saved = await asyncio.to_thread(auto_remember, user_text, reply)
        if saved:
            await context.bot.send_message(chat_id, f"\U0001F9E0 Noted: {saved}")


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


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_TOKEN or not ANTHROPIC_KEY:
        raise SystemExit(
            "Missing required keys. Set TELEGRAM_BOT_TOKEN and ANTHROPIC_API_KEY in .env"
        )

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Base Jarvis commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("remember", cmd_remember))
    app.add_handler(CommandHandler("memories", cmd_memories))
    app.add_handler(CommandHandler("forget", cmd_forget))
    app.add_handler(CommandHandler("forgetall", cmd_forgetall))
    app.add_handler(CommandHandler("automem", cmd_automem))
    app.add_handler(CommandHandler("model", cmd_model))
    app.add_handler(CommandHandler("voiceon", cmd_voiceon))
    app.add_handler(CommandHandler("voiceoff", cmd_voiceoff))
    app.add_handler(CommandHandler("reset", cmd_reset))

    # Spendly Finance Ops commands
    app.add_handler(CommandHandler("policycheck", cmd_policycheck))
    app.add_handler(CommandHandler("closecheck", cmd_closecheck))
    app.add_handler(CommandHandler("spendnarrative", cmd_spendnarrative))

    # Free-text and voice
    app.add_handler(MessageHandler(filters.VOICE, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    log.info("Spendly Finance Ops Agent online.")
    app.run_polling()


if __name__ == "__main__":
    main()

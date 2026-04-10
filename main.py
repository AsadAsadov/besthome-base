import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

DB_PATH = Path("bot.db")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@dataclass
class Note:
    user_id: int
    text: str
    created_at: str


def init_db() -> None:
    """Create SQLite database and required table if they do not exist."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                note_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def insert_note(note: Note) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO notes (user_id, note_text, created_at) VALUES (?, ?, ?)",
            (note.user_id, note.text, note.created_at),
        )
        conn.commit()


def fetch_notes(user_id: int) -> pd.DataFrame:
    """Return user notes as a DataFrame (demonstrates pandas usage)."""
    with sqlite3.connect(DB_PATH) as conn:
        query = """
            SELECT id, note_text, created_at
            FROM notes
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 10
        """
        return pd.read_sql_query(query, conn, params=(user_id,))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! I'm your SQLite Notes Bot.\n"
        "Commands:\n"
        "/start - show welcome message\n"
        "/help - show help\n"
        "/add <note text> - save a note\n"
        "/list - list your latest 10 notes"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def add_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    if not context.args:
        await update.message.reply_text("Usage: /add <note text>")
        return

    text = " ".join(context.args).strip()
    note = Note(
        user_id=update.effective_user.id,
        text=text,
        created_at=datetime.utcnow().isoformat(timespec="seconds"),
    )
    insert_note(note)
    await update.message.reply_text("✅ Note saved.")


async def list_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    df = fetch_notes(update.effective_user.id)
    if df.empty:
        await update.message.reply_text("No notes yet. Add one with /add <note text>.")
        return

    lines = [f"{row.id}. {row.note_text} ({row.created_at})" for row in df.itertuples()]
    await update.message.reply_text("Your latest notes:\n" + "\n".join(lines))


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("add", add_note))
    app.add_handler(CommandHandler("list", list_notes))

    return app


def main() -> None:
    init_db()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Please set TELEGRAM_BOT_TOKEN environment variable.")

    application = build_application(token)
    logger.info("Bot is starting in polling mode...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

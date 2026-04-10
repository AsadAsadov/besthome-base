import logging
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

DB_PATH = Path("crm.db")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

(
    ADD_NAME,
    ADD_PHONE,
    ADD_FIN,
    ADD_ADDRESS,
    ADD_MAC,
    ADD_MODEL,
    ADD_SIGNAL,
    ADD_PAYMENT,
    ADD_NOTES,
    ADD_DATE,
) = range(10)

EDIT_VALUE = 100

ADD_FIELDS = [
    ("name", "👤 *Name*"),
    ("phone", "📞 *Phone*"),
    ("fin", "🆔 *FIN*"),
    ("address", "🏠 *Address*"),
    ("mac", "🖧 *MAC*"),
    ("model", "📡 *Model*"),
    ("signal", "📶 *Signal*"),
    ("payment_status", "💳 *Payment status*"),
    ("notes", "📝 *Notes*"),
    ("created_date", "📅 *Date* (YYYY-MM-DD or `-` for today)"),
]

EDITABLE_FIELDS = {
    "name": "👤 Name",
    "phone": "📞 Phone",
    "fin": "🆔 FIN",
    "address": "🏠 Address",
    "mac": "🖧 MAC",
    "model": "📡 Model",
    "signal": "📶 Signal",
    "payment_status": "💳 Payment",
    "notes": "📝 Notes",
    "created_date": "📅 Date",
}


@dataclass
class Customer:
    id: int
    name: str
    phone: str
    fin: str
    address: str
    mac: str
    model: str
    signal: str
    payment_status: str
    notes: str
    created_date: str
    favorite: int


def mdv2_escape(text: str) -> str:
    if text is None:
        return ""
    return re.sub(r"([_\*\[\]\(\)~`>#+\-=|{}\.!])", r"\\\1", str(text))


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                fin TEXT NOT NULL,
                address TEXT NOT NULL,
                mac TEXT NOT NULL,
                model TEXT NOT NULL,
                signal TEXT NOT NULL,
                payment_status TEXT NOT NULL,
                notes TEXT NOT NULL,
                created_date TEXT NOT NULL,
                favorite INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )


def insert_customer(data: dict[str, str]) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO customers (
                name, phone, fin, address, mac, model, signal,
                payment_status, notes, created_date, favorite, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                data["name"],
                data["phone"],
                data["fin"],
                data["address"],
                data["mac"],
                data["model"],
                data["signal"],
                data["payment_status"],
                data["notes"],
                data["created_date"],
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        return int(cur.lastrowid)


def get_customer(customer_id: int) -> Customer | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        return Customer(**dict(row)) if row else None


def fetch_ids(query: str | None = None, favorites_only: bool = False) -> list[int]:
    sql = "SELECT id FROM customers"
    params: list[Any] = []
    where = []

    if query:
        where.append("(name LIKE ? OR phone LIKE ? OR mac LIKE ? OR fin LIKE ?)")
        like_q = f"%{query}%"
        params.extend([like_q, like_q, like_q, like_q])

    if favorites_only:
        where.append("favorite = 1")

    if where:
        sql += " WHERE " + " AND ".join(where)

    sql += " ORDER BY id DESC"

    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [int(r["id"]) for r in rows]


def toggle_favorite(customer_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE customers SET favorite = CASE WHEN favorite = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (customer_id,),
        )


def delete_customer(customer_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))


def update_field(customer_id: int, field: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(f"UPDATE customers SET {field} = ? WHERE id = ?", (value, customer_id))


def customer_card(customer: Customer, index: int, total: int, mode_title: str) -> str:
    star = "⭐️ Favorite" if customer.favorite else "☆ Not favorite"
    return (
        f"🏢 *CRM Panel*  \|  {mdv2_escape(mode_title)}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔢 *Record:* {index + 1}/{total}\n"
        f"🆔 *ID:* `{customer.id}`\n"
        f"👤 *Name:* {mdv2_escape(customer.name)}\n"
        f"📞 *Phone:* `{mdv2_escape(customer.phone)}`\n"
        f"🆔 *FIN:* `{mdv2_escape(customer.fin)}`\n"
        f"🏠 *Address:* {mdv2_escape(customer.address)}\n"
        f"🖧 *MAC:* `{mdv2_escape(customer.mac)}`\n"
        f"📡 *Model:* {mdv2_escape(customer.model)}\n"
        f"📶 *Signal:* {mdv2_escape(customer.signal)}\n"
        f"💳 *Payment:* {mdv2_escape(customer.payment_status)}\n"
        f"📝 *Notes:* {mdv2_escape(customer.notes)}\n"
        f"📅 *Date:* `{mdv2_escape(customer.created_date)}`\n"
        f"⭐️ *Status:* {mdv2_escape(star)}"
    )


def nav_keyboard(customer: Customer) -> InlineKeyboardMarkup:
    fav_label = "⭐ Remove Favorite" if customer.favorite else "⭐ Add Favorite"
    keyboard = [
        [
            InlineKeyboardButton("⬅️ Previous", callback_data="nav:prev"),
            InlineKeyboardButton("➡️ Next", callback_data="nav:next"),
        ],
        [
            InlineKeyboardButton(fav_label, callback_data="act:fav"),
            InlineKeyboardButton("✏️ Edit", callback_data="act:edit"),
        ],
        [InlineKeyboardButton("🗑 Delete", callback_data="act:delete")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def render_current(query, context: ContextTypes.DEFAULT_TYPE, notice: str | None = None) -> None:
    state = context.user_data.get("view")
    if not state or not state.get("ids"):
        await query.edit_message_text("No customer records found for this panel view\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    ids = state["ids"]
    idx = state["index"] % len(ids)
    state["index"] = idx
    customer = get_customer(ids[idx])

    if customer is None:
        ids.pop(idx)
        if not ids:
            context.user_data.pop("view", None)
            await query.edit_message_text("Record was removed\. No more entries left\.", parse_mode=ParseMode.MARKDOWN_V2)
            return
        state["index"] = min(idx, len(ids) - 1)
        customer = get_customer(ids[state["index"]])
        if customer is None:
            await query.edit_message_text("Data refresh needed\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

    text = customer_card(customer, state["index"], len(ids), state.get("title", "View"))
    if notice:
        text = f"✅ {mdv2_escape(notice)}\n\n" + text

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=nav_keyboard(customer),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    msg = (
        "*Welcome to Telegram CRM Panel*\n\n"
        "Use commands:\n"
        "`/add` \- add new customer\n"
        "`/all` \- browse all customers one by one\n"
        "`/search <query>` \- search by name/phone/MAC/FIN\n"
        "`/favorites` \- browse favorites\n"
        "`/help` \- command guide"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END
    context.user_data["add_data"] = {}
    await update.message.reply_text(
        "🧾 *New customer wizard*\nSend value for: \n\n" + ADD_FIELDS[0][1],
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return ADD_NAME


async def add_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END

    state = context.user_data.get("add_data", {})
    idx = ADD_NAME + len(state)
    field_name, _ = ADD_FIELDS[idx]
    value = update.message.text.strip()

    if field_name == "created_date" and value == "-":
        value = datetime.utcnow().strftime("%Y-%m-%d")

    state[field_name] = value
    context.user_data["add_data"] = state

    if len(state) == len(ADD_FIELDS):
        record_id = insert_customer(state)
        context.user_data.pop("add_data", None)
        await update.message.reply_text(
            f"✅ Customer saved with ID `{record_id}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return ConversationHandler.END

    _, label = ADD_FIELDS[len(state)]
    await update.message.reply_text(f"Next field:\n{label}", parse_mode=ParseMode.MARKDOWN_V2)
    return ADD_NAME + len(state)


async def add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("add_data", None)
    if update.message:
        await update.message.reply_text("❌ Add wizard cancelled\.", parse_mode=ParseMode.MARKDOWN_V2)
    return ConversationHandler.END


async def all_customers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    ids = fetch_ids()
    if not ids:
        await update.message.reply_text("No customers in CRM yet\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    context.user_data["view"] = {"ids": ids, "index": 0, "title": "All Customers"}
    customer = get_customer(ids[0])
    if customer is None:
        await update.message.reply_text("Data error\.", parse_mode=ParseMode.MARKDOWN_V2)
        return
    await update.message.reply_text(
        customer_card(customer, 0, len(ids), "All Customers"),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=nav_keyboard(customer),
    )


async def favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    ids = fetch_ids(favorites_only=True)
    if not ids:
        await update.message.reply_text("No favorite customers yet\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    context.user_data["view"] = {"ids": ids, "index": 0, "title": "Favorites"}
    customer = get_customer(ids[0])
    if customer is None:
        await update.message.reply_text("Data error\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    await update.message.reply_text(
        customer_card(customer, 0, len(ids), "Favorites"),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=nav_keyboard(customer),
    )


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: `/search <name|phone|MAC|FIN>`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    query_text = " ".join(context.args).strip()
    ids = fetch_ids(query=query_text)

    if not ids:
        await update.message.reply_text(
            f"No matches for `{mdv2_escape(query_text)}`\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    context.user_data["view"] = {
        "ids": ids,
        "index": 0,
        "title": f"Search: {query_text}",
    }
    customer = get_customer(ids[0])
    if customer is None:
        await update.message.reply_text("Data error\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    await update.message.reply_text(
        customer_card(customer, 0, len(ids), f"Search: {query_text}"),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=nav_keyboard(customer),
    )


async def on_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    state = context.user_data.get("view")
    if not state or not state.get("ids"):
        await query.edit_message_text("Panel expired\. Run /all or /search again\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    direction = query.data.split(":", 1)[1]
    if direction == "next":
        state["index"] = (state["index"] + 1) % len(state["ids"])
    else:
        state["index"] = (state["index"] - 1) % len(state["ids"])

    await render_current(query, context)


async def on_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    query = update.callback_query
    if query is None:
        return None
    await query.answer()

    state = context.user_data.get("view")
    if not state or not state.get("ids"):
        await query.edit_message_text("Panel expired\. Run /all or /search again\.", parse_mode=ParseMode.MARKDOWN_V2)
        return None

    current_id = state["ids"][state["index"]]
    action = query.data.split(":", 1)[1]

    if action == "fav":
        toggle_favorite(current_id)
        await render_current(query, context, notice="Favorite status changed")
        return None

    if action == "delete":
        delete_customer(current_id)
        state["ids"].pop(state["index"])
        if not state["ids"]:
            context.user_data.pop("view", None)
            await query.edit_message_text("🗑 Record deleted\. No more records in this panel\.", parse_mode=ParseMode.MARKDOWN_V2)
            return None
        state["index"] = min(state["index"], len(state["ids"]) - 1)
        await render_current(query, context, notice="Record deleted")
        return None

    if action == "edit":
        keyboard = [
            [InlineKeyboardButton(label, callback_data=f"edit:{field}")]
            for field, label in EDITABLE_FIELDS.items()
        ]
        keyboard.append([InlineKeyboardButton("↩️ Cancel", callback_data="edit:cancel")])
        await query.edit_message_text(
            "✏️ *Select field to edit:*",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return EDIT_VALUE

    return None


async def on_edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()

    pick = query.data.split(":", 1)[1]
    if pick == "cancel":
        await render_current(query, context, notice="Edit cancelled")
        return ConversationHandler.END

    context.user_data["edit_field"] = pick
    label = EDITABLE_FIELDS[pick]
    await query.edit_message_text(
        f"Send new value for *{mdv2_escape(label)}*:",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return EDIT_VALUE


async def on_edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END

    state = context.user_data.get("view")
    field = context.user_data.get("edit_field")
    if not state or not state.get("ids") or not field:
        await update.message.reply_text("Edit session expired\.", parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END

    new_value = update.message.text.strip()
    if field == "created_date" and new_value == "-":
        new_value = datetime.utcnow().strftime("%Y-%m-%d")

    customer_id = state["ids"][state["index"]]
    update_field(customer_id, field, new_value)
    context.user_data.pop("edit_field", None)

    refreshed = get_customer(customer_id)
    if refreshed is None:
        await update.message.reply_text("Record no longer exists\.", parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END

    await update.message.reply_text(
        "✅ Field updated\.\n\n"
        + customer_card(refreshed, state["index"], len(state["ids"]), state.get("title", "View")),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=nav_keyboard(refreshed),
    )
    return ConversationHandler.END


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()

    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_step)],
            ADD_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_step)],
            ADD_FIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_step)],
            ADD_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_step)],
            ADD_MAC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_step)],
            ADD_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_step)],
            ADD_SIGNAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_step)],
            ADD_PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_step)],
            ADD_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_step)],
            ADD_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_step)],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
    )

    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(on_action, pattern=r"^act:edit$")],
        states={
            EDIT_VALUE: [
                CallbackQueryHandler(on_edit_select, pattern=r"^edit:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_edit_value),
            ]
        },
        fallbacks=[],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("all", all_customers))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("favorites", favorites))
    app.add_handler(add_conv)

    app.add_handler(CallbackQueryHandler(on_nav, pattern=r"^nav:"))
    app.add_handler(CallbackQueryHandler(on_action, pattern=r"^act:(fav|delete)$"))
    app.add_handler(edit_conv)

    return app


def main() -> None:
    init_db()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Please set TELEGRAM_BOT_TOKEN environment variable.")

    app = build_application(token)
    logger.info("CRM bot started in polling mode")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

import logging
import os
import re
import sqlite3
import threading
import uvicorn
from fastapi import FastAPI
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
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
EXPORT_FILE = Path("crm_export.xlsx")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

(
    WAIT_CUSTOMER_BULK,
    WAIT_TASK_BULK,
    WAIT_TASK_DATE_SEARCH,
    WAIT_VLAN_ADD,
    WAIT_VLAN_DELETE,
    WAIT_VLAN_SEARCH,
    WAIT_CUSTOMER_EDIT,
) = range(20, 27)

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "ad_soyad": ("ad:", "ad soyad:", "ad soyadı:", "ad-soyad:", "soyad:"),
    "telefon": ("telefon:", "tel:", "mobil:"),
    "fin_kod": ("fin:", "fin kod:", "finkod:"),
    "unvan": ("ünvan:", "unvan:", "adres:"),
    "mertebe": ("mərtəbə:", "mertebe:"),
    "modem_model": ("modem:", "modem model:"),
    "modem_serial": ("s/n:", "sn:", "serial:", "serial no:", "serial nömrə:"),
    "qeyd": ("qeyd:", "note:", "qeydlər:"),
    "tarix": ("tarix:", "qoşulma tarixi:", "qosulma tarixi:"),
}

EDITABLE_CUSTOMER_FIELDS: dict[str, str] = {
    "ad_soyad": "👤 Ad Soyad",
    "telefon": "📞 Telefon",
    "fin_kod": "🪪 FIN",
    "unvan": "📍 Ünvan",
    "mertebe": "🏢 Mərtəbə",
    "modem_model": "📡 Modem",
    "modem_serial": "🔢 S/N",
    "qeyd": "📝 Qeyd",
    "tarix": "📅 Tarix",
}


@dataclass
class Customer:
    id: int
    ad_soyad: str
    telefon: str
    fin_kod: str
    unvan: str
    mertebe: str
    modem_model: str
    modem_serial: str
    qeyd: str
    tarix: str
    favorit: int
    created_at: str


@dataclass
class TaskItem:
    id: int
    metn: str
    tarix: str
    status: str
    created_at: str


def mdv2_escape(text: Any) -> str:
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
                ad_soyad TEXT NOT NULL,
                telefon TEXT NOT NULL,
                fin_kod TEXT NOT NULL,
                unvan TEXT NOT NULL,
                mertebe TEXT NOT NULL,
                modem_model TEXT NOT NULL,
                modem_serial TEXT NOT NULL,
                qeyd TEXT NOT NULL,
                tarix TEXT NOT NULL,
                favorit INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metn TEXT NOT NULL,
                tarix TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vlans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                erazi TEXT NOT NULL,
                vlan TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def upsert_panel_message(context: ContextTypes.DEFAULT_TYPE, message: Message) -> None:
    context.user_data["panel_chat_id"] = message.chat_id
    context.user_data["panel_message_id"] = message.message_id


async def safe_update_panel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    keyboard: InlineKeyboardMarkup,
) -> None:
    chat_id = context.user_data.get("panel_chat_id")
    message_id = context.user_data.get("panel_message_id")
    if chat_id and message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=keyboard,
            )
            return
        except Exception:
            pass

    if update.effective_message is not None:
        sent = await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
        )
    else:
        sent = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
        )
    upsert_panel_message(context, sent)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Müştəri əlavə et", callback_data="menu:add_customer")],
            [InlineKeyboardButton("🔍 Axtar", callback_data="menu:search_customer")],
            [InlineKeyboardButton("⭐ Favoritlər", callback_data="menu:favorites")],
            [InlineKeyboardButton("📋 İşlər", callback_data="menu:tasks")],
            [InlineKeyboardButton("🌐 VLAN", callback_data="menu:vlan")],
            [InlineKeyboardButton("📊 Excel export", callback_data="menu:excel")],
        ]
    )


def main_menu_text() -> str:
    return (
        "*🧰 Texnik CRM Paneli*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Sizə lazım olan bölməni seçin\."
    )


def parse_customer_text(raw_text: str) -> dict[str, str]:
    parsed = {k: "Yoxdur" for k in FIELD_ALIASES}
    for line in [ln.strip() for ln in raw_text.splitlines() if ln.strip()]:
        lower = line.lower()
        for field, aliases in FIELD_ALIASES.items():
            hit = next((alias for alias in aliases if lower.startswith(alias)), None)
            if hit:
                value = line[len(hit):].strip(" -\t")
                parsed[field] = value if value else "Yoxdur"
                break

    if parsed["tarix"] == "Yoxdur":
        parsed["tarix"] = datetime.utcnow().strftime("%Y-%m-%d")

    return parsed


def insert_customer(data: dict[str, str]) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO customers (
                ad_soyad, telefon, fin_kod, unvan, mertebe,
                modem_model, modem_serial, qeyd, tarix, favorit, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                data["ad_soyad"],
                data["telefon"],
                data["fin_kod"],
                data["unvan"],
                data["mertebe"],
                data["modem_model"],
                data["modem_serial"],
                data["qeyd"],
                data["tarix"],
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
    return int(cur.lastrowid)


def get_customer(customer_id: int) -> Customer | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    return Customer(**dict(row)) if row else None


def fetch_customer_ids(query: str | None = None, favorites_only: bool = False) -> list[int]:
    sql = "SELECT id FROM customers"
    conditions = []
    params: list[str] = []

    if query:
        conditions.append("(ad_soyad LIKE ? OR telefon LIKE ? OR fin_kod LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like, like])
    if favorites_only:
        conditions.append("favorit = 1")
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY id DESC"

    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [int(r["id"]) for r in rows]


def update_customer_field(customer_id: int, field: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(f"UPDATE customers SET {field} = ? WHERE id = ?", (value, customer_id))


def toggle_customer_favorite(customer_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE customers SET favorit = CASE WHEN favorit = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (customer_id,),
        )


def delete_customer(customer_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))


def customer_card(customer: Customer, idx: int, total: int, title: str) -> str:
    return (
        f"*{mdv2_escape(title)}*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"`{idx + 1}/{total}`\n\n"
        f"👤 *Ad Soyad:* {mdv2_escape(customer.ad_soyad)}\n"
        f"📞 *Telefon:* `{mdv2_escape(customer.telefon)}`\n"
        f"🪪 *FIN:* `{mdv2_escape(customer.fin_kod)}`\n"
        f"📍 *Ünvan:* {mdv2_escape(customer.unvan)}\n"
        f"🏢 *Mərtəbə:* {mdv2_escape(customer.mertebe)}\n"
        f"📡 *Modem:* {mdv2_escape(customer.modem_model)}\n"
        f"🔢 *S/N:* `{mdv2_escape(customer.modem_serial)}`\n"
        f"📝 *Qeyd:* {mdv2_escape(customer.qeyd)}\n"
        f"📅 *Tarix:* `{mdv2_escape(customer.tarix)}`"
    )


def customer_nav_keyboard(customer: Customer) -> InlineKeyboardMarkup:
    fav_text = "☆ Sil" if customer.favorit else "⭐ Favorit"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⬅️ Geri", callback_data="cust:prev"),
                InlineKeyboardButton("➡️ Növbəti", callback_data="cust:next"),
            ],
            [
                InlineKeyboardButton(fav_text, callback_data="cust:fav"),
                InlineKeyboardButton("✏️ Redaktə", callback_data="cust:edit"),
            ],
            [InlineKeyboardButton("🗑️ Sil", callback_data="cust:delete")],
            [InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")],
        ]
    )


async def render_customer_view(update: Update, context: ContextTypes.DEFAULT_TYPE, notice: str | None = None) -> None:
    view = context.user_data.get("customer_view")
    if not view or not view.get("ids"):
        await safe_update_panel(
            update,
            context,
            "*Müştəri tapılmadı\.*",
            InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")]]),
        )
        return

    ids = view["ids"]
    idx = view["index"] % len(ids)
    view["index"] = idx

    customer = get_customer(ids[idx])
    if customer is None:
        ids.pop(idx)
        if not ids:
            context.user_data.pop("customer_view", None)
            await safe_update_panel(
                update,
                context,
                "*Müştəri qalmadı\.*",
                InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")]]),
            )
            return
        view["index"] = min(idx, len(ids) - 1)
        customer = get_customer(ids[view["index"]])
        if customer is None:
            return

    text = customer_card(customer, view["index"], len(ids), view["title"])
    if notice:
        text = f"✅ {mdv2_escape(notice)}\n\n{text}"

    await safe_update_panel(update, context, text, customer_nav_keyboard(customer))


def parse_tasks(raw_text: str) -> list[dict[str, str]]:
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    result: list[dict[str, str]] = []
    assumed_date = date.today().isoformat()

    for ln in lines:
        normalized = ln.lower().replace(" ", "")
        if normalized in {"bugün:", "bugun:", "bu gün:", "bügün:"}:
            assumed_date = date.today().isoformat()
            continue
        if normalized in {"sabah:", "sabah"}:
            assumed_date = (date.today() + timedelta(days=1)).isoformat()
            continue
        if re.match(r"^\d{4}-\d{2}-\d{2}:?$", ln):
            assumed_date = ln.replace(":", "")
            continue

        task_text = re.sub(r"^[\-•*]\s*", "", ln).strip()
        if task_text:
            result.append({"metn": task_text, "tarix": assumed_date})

    return result


def insert_tasks(tasks: list[dict[str, str]]) -> int:
    if not tasks:
        return 0
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO tasks (metn, tarix, status, created_at) VALUES (?, ?, 'pending', ?)",
            [
                (
                    task["metn"],
                    task["tarix"],
                    datetime.utcnow().isoformat(timespec="seconds"),
                )
                for task in tasks
            ],
        )
    return len(tasks)


def fetch_task_ids(category: str, search_date: str | None = None) -> list[int]:
    today = date.today()
    start_week = today - timedelta(days=today.weekday())
    end_week = start_week + timedelta(days=6)

    sql = "SELECT id FROM tasks"
    params: list[str] = []
    where = []

    if category == "today":
        where.append("tarix = ?")
        params.append(today.isoformat())
    elif category == "week":
        where.append("tarix BETWEEN ? AND ?")
        params.extend([start_week.isoformat(), end_week.isoformat()])
    elif category == "month":
        where.append("substr(tarix, 1, 7) = ?")
        params.append(today.strftime("%Y-%m"))
    elif category == "done":
        where.append("status = 'done'")
    elif category == "pending":
        where.append("status = 'pending'")
    elif category == "date" and search_date:
        where.append("tarix = ?")
        params.append(search_date)

    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY tarix ASC, id DESC"

    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [int(r["id"]) for r in rows]


def get_task(task_id: int) -> TaskItem | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return TaskItem(**dict(row)) if row else None


def set_task_status(task_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))


def task_card(task: TaskItem, idx: int, total: int, title: str) -> str:
    status_text = "✅ Bitirildi" if task.status == "done" else "⏳ Gözləyir"
    return (
        f"*{mdv2_escape(title)}*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"`{idx + 1}/{total}`\n\n"
        f"🛠️ *Tapşırıq:* {mdv2_escape(task.metn)}\n"
        f"📅 *Tarix:* `{mdv2_escape(task.tarix)}`\n"
        f"📌 *Status:* {mdv2_escape(status_text)}"
    )


def task_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⬅️ Geri", callback_data="task:prev"),
                InlineKeyboardButton("➡️ Növbəti", callback_data="task:next"),
            ],
            [
                InlineKeyboardButton("✅ Bitirildi", callback_data="task:done"),
                InlineKeyboardButton("⏳ Gözləyir", callback_data="task:pending"),
            ],
            [InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")],
        ]
    )


def tasks_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ İş əlavə et", callback_data="tasks:add")],
            [InlineKeyboardButton("📅 Bu gün", callback_data="tasks:view:today")],
            [InlineKeyboardButton("📆 Bu həftə", callback_data="tasks:view:week")],
            [InlineKeyboardButton("🗓️ Bu ay", callback_data="tasks:view:month")],
            [InlineKeyboardButton("📂 Hamısı", callback_data="tasks:view:all")],
            [InlineKeyboardButton("🔍 Tarixə görə axtar", callback_data="tasks:bydate")],
            [InlineKeyboardButton("📦 Bitirilmiş işlər", callback_data="tasks:view:done")],
            [InlineKeyboardButton("⏳ Yarım qalan işlər", callback_data="tasks:view:pending")],
            [InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")],
        ]
    )


async def render_task_view(update: Update, context: ContextTypes.DEFAULT_TYPE, notice: str | None = None) -> None:
    view = context.user_data.get("task_view")
    if not view or not view.get("ids"):
        await safe_update_panel(
            update,
            context,
            "*Tapşırıq tapılmadı\.*",
            InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📋 İşlər", callback_data="menu:tasks")],
                    [InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")],
                ]
            ),
        )
        return

    ids = view["ids"]
    idx = view["index"] % len(ids)
    view["index"] = idx
    task = get_task(ids[idx])
    if task is None:
        ids.pop(idx)
        if not ids:
            context.user_data.pop("task_view", None)
            await safe_update_panel(update, context, "*Tapşırıq qalmadı\.*", tasks_menu_keyboard())
            return
        view["index"] = min(idx, len(ids) - 1)
        task = get_task(ids[view["index"]])
        if task is None:
            return

    text = task_card(task, view["index"], len(ids), view["title"])
    if notice:
        text = f"✅ {mdv2_escape(notice)}\n\n{text}"
    await safe_update_panel(update, context, text, task_keyboard())


def insert_vlan(erazi: str, vlan: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO vlans (erazi, vlan, created_at) VALUES (?, ?, ?)",
            (erazi, vlan, datetime.utcnow().isoformat(timespec="seconds")),
        )
    return int(cur.lastrowid)


def delete_vlan(vlan_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM vlans WHERE id = ?", (vlan_id,))
    return cur.rowcount > 0


def search_vlan(query: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM vlans WHERE erazi LIKE ? OR vlan LIKE ? ORDER BY id DESC",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()


def vlan_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ VLAN əlavə et", callback_data="vlan:add")],
            [InlineKeyboardButton("🗑️ VLAN sil", callback_data="vlan:delete")],
            [InlineKeyboardButton("🔍 VLAN axtar", callback_data="vlan:search")],
            [InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")],
        ]
    )


def build_excel_export() -> Path:
    with get_conn() as conn:
        customers = pd.read_sql_query("SELECT * FROM customers ORDER BY id DESC", conn)
        tasks = pd.read_sql_query("SELECT * FROM tasks ORDER BY id DESC", conn)
        vlans = pd.read_sql_query("SELECT * FROM vlans ORDER BY id DESC", conn)

    with pd.ExcelWriter(EXPORT_FILE, engine="openpyxl") as writer:
        customers.to_excel(writer, sheet_name="musteriler", index=False)
        tasks.to_excel(writer, sheet_name="isler", index=False)
        vlans.to_excel(writer, sheet_name="vlans", index=False)

    return EXPORT_FILE


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("pending_mode", None)
    await safe_update_panel(update, context, main_menu_text(), main_menu_keyboard())


async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    query = update.callback_query
    if query is None:
        return None
    await query.answer()

    action = query.data.split(":", 1)[1]

    if action == "home":
        context.user_data.pop("pending_mode", None)
        await query.edit_message_text(
            main_menu_text(),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    if action == "add_customer":
        context.user_data["pending_mode"] = "customer_add"
        await query.edit_message_text(
            "*Müştəri məlumatını bir mesajda göndərin:*\n\n"
            "`Ad: ...`\n"
            "`Telefon: ...`\n"
            "`FIN: ...`\n"
            "`Ünvan: ...`\n"
            "`Mərtəbə: ...`\n"
            "`Modem: ...`\n"
            "`S/N: ...`\n"
            "`Qeyd: ...`\n"
            "`Tarix: 2026-04-10`\n\n"
            "Daxil etmədiyiniz sahələr avtomatik *Yoxdur* olacaq\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")]]),
        )
        return WAIT_CUSTOMER_BULK

    if action == "search_customer":
        context.user_data["pending_mode"] = "customer_search"
        await query.edit_message_text(
            "*Axtarış üçün ad, telefon və ya FIN yazın\.*",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")]]),
        )
        return WAIT_CUSTOMER_BULK

    if action == "favorites":
        ids = fetch_customer_ids(favorites_only=True)
        context.user_data["customer_view"] = {"ids": ids, "index": 0, "title": "⭐ Favorit müştərilər"}
        await render_customer_view(update, context)
        return None

    if action == "tasks":
        await query.edit_message_text("*Tapşırıq paneli*", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=tasks_menu_keyboard())
        return None

    if action == "vlan":
        await query.edit_message_text("*VLAN paneli*", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=vlan_menu_keyboard())
        return None

    if action == "excel":
        export_path = build_excel_export()
        await context.bot.send_document(chat_id=query.message.chat_id, document=export_path.open("rb"), filename=export_path.name)
        await query.edit_message_text(
            "✅ *Excel export hazırdır və göndərildi\.*",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu_keyboard(),
        )
        return None

    return None


async def handle_customer_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return WAIT_CUSTOMER_BULK

    mode = context.user_data.get("pending_mode")
    if mode == "customer_add":
        payload = parse_customer_text(update.message.text)
        new_id = insert_customer(payload)
        ids = fetch_customer_ids()
        target_index = ids.index(new_id) if new_id in ids else 0
        context.user_data["customer_view"] = {"ids": ids, "index": target_index, "title": "📁 Bütün müştərilər"}
        await render_customer_view(update, context, notice="Müştəri əlavə edildi")
        context.user_data.pop("pending_mode", None)
        return ConversationHandler.END

    if mode == "customer_search":
        query_text = update.message.text.strip()
        ids = fetch_customer_ids(query=query_text)
        context.user_data["customer_view"] = {
            "ids": ids,
            "index": 0,
            "title": f"🔍 Axtarış: {query_text}",
        }
        await render_customer_view(update, context)
        context.user_data.pop("pending_mode", None)
        return ConversationHandler.END

    return WAIT_CUSTOMER_BULK


async def customer_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    query = update.callback_query
    if query is None:
        return None
    await query.answer()

    view = context.user_data.get("customer_view")
    if not view or not view.get("ids"):
        await query.edit_message_text("*Panel vaxtı bitib\.*", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=main_menu_keyboard())
        return None

    current_id = view["ids"][view["index"]]
    action = query.data.split(":", 1)[1]

    if action == "next":
        view["index"] = (view["index"] + 1) % len(view["ids"])
        await render_customer_view(update, context)
        return None
    if action == "prev":
        view["index"] = (view["index"] - 1) % len(view["ids"])
        await render_customer_view(update, context)
        return None
    if action == "fav":
        toggle_customer_favorite(current_id)
        await render_customer_view(update, context, notice="Favorit yeniləndi")
        return None
    if action == "delete":
        delete_customer(current_id)
        view["ids"].pop(view["index"])
        if view["ids"]:
            view["index"] = min(view["index"], len(view["ids"]) - 1)
            await render_customer_view(update, context, notice="Müştəri silindi")
        else:
            await query.edit_message_text("*Müştəri qalmadı\.*", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=main_menu_keyboard())
        return None
    if action == "edit":
        context.user_data["pending_mode"] = "customer_edit"
        context.user_data["edit_customer_id"] = current_id
        keyboard = [[InlineKeyboardButton(label, callback_data=f"cedit:{field}")] for field, label in EDITABLE_CUSTOMER_FIELDS.items()]
        keyboard.append([InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")])
        await query.edit_message_text(
            "*Redaktə üçün sahəni seçin\.*",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return WAIT_CUSTOMER_EDIT

    return None


async def customer_edit_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()

    field = query.data.split(":", 1)[1]
    context.user_data["edit_field"] = field
    label = EDITABLE_CUSTOMER_FIELDS[field]
    await query.edit_message_text(
        f"*{mdv2_escape(label)}* üçün yeni dəyər göndərin\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")]]),
    )
    return WAIT_CUSTOMER_EDIT


async def customer_edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return WAIT_CUSTOMER_EDIT

    customer_id = context.user_data.get("edit_customer_id")
    field = context.user_data.get("edit_field")
    if not customer_id or not field:
        return ConversationHandler.END

    value = update.message.text.strip() or "Yoxdur"
    update_customer_field(customer_id, field, value)

    context.user_data.pop("pending_mode", None)
    context.user_data.pop("edit_field", None)
    context.user_data.pop("edit_customer_id", None)

    await render_customer_view(update, context, notice="Müştəri redaktə edildi")
    return ConversationHandler.END


async def tasks_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    query = update.callback_query
    if query is None:
        return None
    await query.answer()

    data = query.data

    if data == "tasks:add":
        context.user_data["pending_mode"] = "task_add"
        await query.edit_message_text(
            "*Tapşırıqları bir mesajda göndərin\.*\n\n"
            "Nümunə:\n`Bugün:`\n`- Müştəriyə get \(Nizami\)`\n`- Modem dəyiş`",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")]]),
        )
        return WAIT_TASK_BULK

    if data == "tasks:bydate":
        context.user_data["pending_mode"] = "task_by_date"
        await query.edit_message_text(
            "*Tarixi YYYY\-MM\-DD formatında göndərin\.*",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")]]),
        )
        return WAIT_TASK_DATE_SEARCH

    if data.startswith("tasks:view:"):
        category = data.split(":")[-1]
        mapping = {
            "today": "📅 Bu gün",
            "week": "📆 Bu həftə",
            "month": "🗓️ Bu ay",
            "all": "📂 Bütün işlər",
            "done": "📦 Bitirilmiş işlər",
            "pending": "⏳ Yarım qalan işlər",
        }
        ids = fetch_task_ids(category)
        context.user_data["task_view"] = {"ids": ids, "index": 0, "title": mapping[category]}
        await render_task_view(update, context)
        return None

    return None


async def handle_task_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return WAIT_TASK_BULK
    if context.user_data.get("pending_mode") != "task_add":
        return WAIT_TASK_BULK

    tasks = parse_tasks(update.message.text)
    added = insert_tasks(tasks)
    context.user_data.pop("pending_mode", None)
    await safe_update_panel(
        update,
        context,
        f"✅ *{added} tapşırıq əlavə edildi\.*",
        tasks_menu_keyboard(),
    )
    return ConversationHandler.END


async def handle_task_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return WAIT_TASK_DATE_SEARCH

    text = update.message.text.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        await safe_update_panel(
            update,
            context,
            "❌ *Format yanlışdır\. YYYY\-MM\-DD göndərin\.*",
            tasks_menu_keyboard(),
        )
        return WAIT_TASK_DATE_SEARCH

    ids = fetch_task_ids("date", text)
    context.user_data["task_view"] = {
        "ids": ids,
        "index": 0,
        "title": f"🔍 Tarix: {text}",
    }
    context.user_data.pop("pending_mode", None)
    await render_task_view(update, context)
    return ConversationHandler.END


async def task_nav_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    view = context.user_data.get("task_view")
    if not view or not view.get("ids"):
        await query.edit_message_text("*Panel vaxtı bitib\.*", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=tasks_menu_keyboard())
        return

    action = query.data.split(":", 1)[1]
    current_id = view["ids"][view["index"]]

    if action == "next":
        view["index"] = (view["index"] + 1) % len(view["ids"])
        await render_task_view(update, context)
    elif action == "prev":
        view["index"] = (view["index"] - 1) % len(view["ids"])
        await render_task_view(update, context)
    elif action == "done":
        set_task_status(current_id, "done")
        await render_task_view(update, context, notice="Tapşırıq bitirildi")
    elif action == "pending":
        set_task_status(current_id, "pending")
        await render_task_view(update, context, notice="Tapşırıq gözləmədədir")


async def vlan_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    query = update.callback_query
    if query is None:
        return None
    await query.answer()

    action = query.data.split(":", 1)[1]

    if action == "add":
        context.user_data["pending_mode"] = "vlan_add"
        await query.edit_message_text(
            "*Format:* `Ərazi | VLAN`\nNümunə: `Nizami | 402`",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")]]),
        )
        return WAIT_VLAN_ADD
    if action == "delete":
        context.user_data["pending_mode"] = "vlan_delete"
        await query.edit_message_text(
            "*Silmək üçün VLAN ID göndərin\.*",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")]]),
        )
        return WAIT_VLAN_DELETE
    if action == "search":
        context.user_data["pending_mode"] = "vlan_search"
        await query.edit_message_text(
            "*Axtarış üçün ərazi və ya VLAN yazın\.*",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ana menyu", callback_data="menu:home")]]),
        )
        return WAIT_VLAN_SEARCH

    return None


async def handle_vlan_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return WAIT_VLAN_ADD

    payload = update.message.text.strip()
    if "|" not in payload:
        await safe_update_panel(update, context, "❌ *Format yanlışdır\. `Ərazi | VLAN` göndərin\.*", vlan_menu_keyboard())
        return WAIT_VLAN_ADD

    erazi, vlan = [part.strip() for part in payload.split("|", 1)]
    new_id = insert_vlan(erazi or "Yoxdur", vlan or "Yoxdur")
    context.user_data.pop("pending_mode", None)
    await safe_update_panel(update, context, f"✅ *VLAN əlavə edildi\. ID: {new_id}*", vlan_menu_keyboard())
    return ConversationHandler.END


async def handle_vlan_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return WAIT_VLAN_DELETE

    text = update.message.text.strip()
    if not text.isdigit():
        await safe_update_panel(update, context, "❌ *Yalnız ID rəqəmi göndərin\.*", vlan_menu_keyboard())
        return WAIT_VLAN_DELETE

    ok = delete_vlan(int(text))
    context.user_data.pop("pending_mode", None)
    message = "✅ *VLAN silindi\.*" if ok else "❌ *Bu ID tapılmadı\.*"
    await safe_update_panel(update, context, message, vlan_menu_keyboard())
    return ConversationHandler.END


async def handle_vlan_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return WAIT_VLAN_SEARCH

    rows = search_vlan(update.message.text.strip())
    context.user_data.pop("pending_mode", None)

    if not rows:
        await safe_update_panel(update, context, "*Nəticə tapılmadı\.*", vlan_menu_keyboard())
        return ConversationHandler.END

    lines = ["*VLAN nəticələri*", "━━━━━━━━━━━━━━━━━━"]
    for row in rows[:20]:
        lines.append(
            f"`#{row['id']}` \- {mdv2_escape(row['erazi'])} → *{mdv2_escape(row['vlan'])}*"
        )
    await safe_update_panel(update, context, "\n".join(lines), vlan_menu_keyboard())
    return ConversationHandler.END


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))

    app.add_handler(CallbackQueryHandler(menu_router, pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(customer_callbacks, pattern=r"^cust:"))
    app.add_handler(CallbackQueryHandler(tasks_callbacks, pattern=r"^tasks:"))
    app.add_handler(CallbackQueryHandler(task_nav_callbacks, pattern=r"^task:"))
    app.add_handler(CallbackQueryHandler(vlan_callbacks, pattern=r"^vlan:"))

    customer_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(menu_router, pattern=r"^menu:(add_customer|search_customer)$"),
            CallbackQueryHandler(customer_callbacks, pattern=r"^cust:edit$"),
        ],
        states={
            WAIT_CUSTOMER_BULK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_customer_input)],
            WAIT_CUSTOMER_EDIT: [
                CallbackQueryHandler(customer_edit_pick, pattern=r"^cedit:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, customer_edit_value),
            ],
        },
        fallbacks=[CallbackQueryHandler(menu_router, pattern=r"^menu:home$")],
        per_message=False,
    )

    task_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(tasks_callbacks, pattern=r"^tasks:add$"),
            CallbackQueryHandler(tasks_callbacks, pattern=r"^tasks:bydate$"),
        ],
        states={
            WAIT_TASK_BULK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_task_input)],
            WAIT_TASK_DATE_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_task_date_input)],
        },
        fallbacks=[CallbackQueryHandler(menu_router, pattern=r"^menu:home$")],
        per_message=False,
    )

    vlan_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(vlan_callbacks, pattern=r"^vlan:(add|delete|search)$")],
        states={
            WAIT_VLAN_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_vlan_add)],
            WAIT_VLAN_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_vlan_delete)],
            WAIT_VLAN_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_vlan_search)],
        },
        fallbacks=[CallbackQueryHandler(menu_router, pattern=r"^menu:home$")],
        per_message=False,
    )

    app.add_handler(customer_conv)
    app.add_handler(task_conv)
    app.add_handler(vlan_conv)

    return app

web_app = FastAPI()

@web_app.get("/")
def health_check():
    return {"status": "ok"}

def run_bot():
    init_db()

    token = os.getenv("TOKEN")
    if not token:
        raise RuntimeError("TOKEN mühit dəyişəni təyin edilməlidir.")

    app = build_application(token)
    logger.info("Texnik CRM bot başladıldı")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    uvicorn.run(web_app, host="0.0.0.0", port=7860)

import logging
import os
import sqlite3
import zipfile
from pathlib import Path

import requests
import telebot

BOT_TOKEN = "7938311608:AAHmzsTqnVJ7cVtStp2lmzGe2-1oj9LN1JM"
ADMIN_ID = 1311851277
DB_PATH = Path("besthome.db")
DOWNLOAD_ZIP = Path("besthome_download.zip")
TEMP_DB = Path("besthome_download.db")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN)


def is_admin(chat_id):
    return chat_id == ADMIN_ID


def safe_admin_step(admin_id, text):
    logger.info("ADMIN_STEP admin_id=%s text=%s", admin_id, text)
    bot.send_message(admin_id, text)


def _get_operation_column(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(listings)")
    cols = {row[1] for row in cur.fetchall()}
    if "operation_type" in cols:
        return "operation_type"
    return "operation"


def _fetch_counts(db_path):
    if not db_path.exists():
        return {
            "total": 0,
            "sale": 0,
            "rent": 0,
            "last_24": 0,
        }

    conn = sqlite3.connect(db_path)
    try:
        op_col = _get_operation_column(conn)
        cur = conn.cursor()
        total = cur.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        sale = cur.execute(
            f"SELECT COUNT(*) FROM listings WHERE {op_col} IN ('Satılır', 'SATILIR')"
        ).fetchone()[0]
        rent = cur.execute(
            f"SELECT COUNT(*) FROM listings WHERE {op_col} IN ('Kirayə verilir', 'KİRAYƏ VERİLİR')"
        ).fetchone()[0]
        last_24 = cur.execute(
            """
            SELECT COUNT(*)
            FROM listings
            WHERE datetime(COALESCE(created_at, date_read)) >= datetime('now','-1 day','localtime')
            """
        ).fetchone()[0]
    finally:
        conn.close()

    return {
        "total": total,
        "sale": sale,
        "rent": rent,
        "last_24": last_24,
    }


def run_db_update_pipeline(admin_id, url):
    old_counts = _fetch_counts(DB_PATH)

    safe_admin_step(admin_id, "📥 Dropbox link qəbul edildi. Fayl yüklənir…")
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    DOWNLOAD_ZIP.write_bytes(response.content)

    safe_admin_step(admin_id, "📦 Arxiv açılır və baza yenilənir…")
    with zipfile.ZipFile(DOWNLOAD_ZIP, "r") as archive:
        with archive.open("besthome.db") as source, open(TEMP_DB, "wb") as target:
            target.write(source.read())

    if TEMP_DB.exists():
        os.replace(TEMP_DB, DB_PATH)

    new_counts = _fetch_counts(DB_PATH)

    new_sale = max(0, new_counts["sale"] - old_counts["sale"])
    new_rent = max(0, new_counts["rent"] - old_counts["rent"])
    new_listings = new_sale + new_rent

    message = (
        "✅ Elanlar uğurla yeniləndi.\n"
        f"📦 Yeni elanlar: {new_listings}\n"
        "Bu yenilənmədə əlavə olunanlar:\n"
        f"1⃣ Satılır: {new_sale}\n"
        f"2⃣ Kirayə verilir: {new_rent}\n"
        f"🕒 Son 24 saat əlavə olunanlar: {new_counts['last_24']}"
    )
    bot.send_message(admin_id, message)


@bot.message_handler(commands=["auto_update_db"])
def auto_update_db_cmd(m):
    if not is_admin(m.chat.id):
        return

    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(
            m.chat.id,
            "❌ Update üçün link tapılmadı.\nİstifadə: /auto_update_db <dropbox_link>",
        )
        return

    url = parts[1].strip()
    trigger_auto_update_db(m.chat.id, url)


def trigger_auto_update_db(admin_id: int, url: str):
    logger.info(
        "AUTO DB UPDATE triggered internally admin_id=%s url=%s",
        admin_id,
        url,
    )
    safe_admin_step(admin_id, "⏳ Yenilənmə başladılır…")
    run_db_update_pipeline(admin_id, url)


if __name__ == "__main__":
    logger.info("BestHome bot polling başladı")
    bot.infinity_polling()

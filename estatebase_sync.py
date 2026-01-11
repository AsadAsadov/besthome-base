# ============================================
# estatebase_sync.py — EstateBase SQL → BestHomeBase
# FINAL + BAT FIX (EMOJISIZ)
# ============================================

import sqlite3
import pyodbc
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, date

DB_PATH = Path("besthome.db")


# ---------- SQL Server Connection ----------
def get_sql_conn():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=SERVER;"
        "DATABASE=dbestate3;"
        "UID=sa;"
        "PWD=byte~~;"
        "TrustServerCertificate=yes;"
    )


# ---------- DB Setup ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_read TEXT,
            prop_type TEXT,
            operation TEXT,
            metro TEXT,
            rooms TEXT,
            building TEXT,
            floor TEXT,
            area_kvm TEXT,
            price REAL,
            currency TEXT,
            phone TEXT,
            contact_name TEXT,
            address TEXT,
            document TEXT,
            summary TEXT,
            source_link TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS sold (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE
        )
    """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE,
            color TEXT
        )
    """
    )
    conn.commit()
    conn.close()


def ensure_tables():
    """Baza yoxdursa yaradır, varsa toxunmur"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    required_cols = {
        "listings": {
            "sql_id": "INTEGER",
            "source_link": "TEXT",
        },
    }

    for table, cols in required_cols.items():
        for col, col_type in cols.items():
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type};")
                print(f"[OK] '{col}' sütunu əlavə edildi ({table})")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    pass
                else:
                    print(f"[WARN] '{col}' əlavə edilə bilmədi: {e}")

    conn.commit()
    conn.close()


# ---------- Əlavə və təmizlik ----------
def clear_search_history():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM search_history")
    conn.commit()
    conn.close()


def add_listing_row(rec):
    """Yeni elan əlavə et"""
    if not rec.get("phone"):
        return False

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if rec.get("price") is not None:
        c.execute(
            """
            SELECT 1
            FROM listings
            WHERE phone = ?
              AND price = ?
              AND DATE(created_at) = DATE('now','localtime')
            LIMIT 1
            """,
            (rec["phone"], rec["price"]),
        )
        if c.fetchone():
            print(
                f"[SOFT-DEDUPE] Skipped same-day duplicate: phone={rec['phone']}, price={rec['price']}"
            )
            conn.close()
            return False

    cols = list(rec.keys())
    vals = [rec[k] for k in cols]
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO listings ({','.join(cols)}) VALUES ({placeholders})"
    try:
        c.execute(sql, vals)
        conn.commit()
    except Exception as e:
        print(f"[WARN] Əlavə edilə bilmədi: {e}")
    finally:
        conn.close()
    return True


# ---------- Fərqləndirilənlər / Satılanlar ----------
def set_favorite_phone(phone, color="#e8f2ff"):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO favorites (phone, color) VALUES (?,?)", (phone, color)
    )
    conn.commit()
    conn.close()


def get_favorites_phones_map():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT phone, color FROM favorites")
    data = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return data


def add_sold(phone):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO sold (phone) VALUES (?)", (phone,))
    conn.commit()
    conn.close()


def remove_sold(phone):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM sold WHERE phone=?", (phone,))
    conn.commit()
    conn.close()


def get_sold_set():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT phone FROM sold")
    rows = {r[0] for r in c.fetchall()}
    conn.close()
    return rows


# ---------- Əsas Query ----------
def query_phones_summary(
    keyword=None,
    limit=500,
    date_from=None,
    date_to=None,
    exclude_sold=False,
    only_sold=False,
    only_favorites=False,
):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    base = """
        SELECT
            phone,
            MAX(date_read) AS date_read,
            MAX(created_at) AS created_at,
            MAX(prop_type) AS prop_type,
            MAX(building) AS building,
            MAX(operation) AS operation,
            MAX(metro) AS metro,
            MAX(rooms) AS rooms,
            MAX(floor) AS floor,
            MAX(area_kvm) AS area_kvm,
            MAX(price) AS price,
            MAX(currency) AS currency,
            COUNT(*) AS ad_count,
            MAX(contact_name) AS contact_name,
            MAX(address) AS address,
            MAX(document) AS document,
            MAX(summary) AS summary,
            MAX(source_link) AS source_link
        FROM listings
        WHERE 1=1
    """
    params = []

    if keyword:
        kw = f"%{keyword.lower()}%"
        base += (
            " AND (LOWER(phone) LIKE ? OR LOWER(metro) LIKE ? OR LOWER(address) LIKE ?)"
        )
        params += [kw, kw, kw]

    if date_from:
        base += " AND date(created_at) >= date(?)"
        params.append(date_from)
    if date_to:
        base += " AND date(created_at) <= date(?)"
        params.append(date_to)

    if only_sold:
        base += " AND phone IN (SELECT phone FROM sold)"
    elif only_favorites:
        base += " AND phone IN (SELECT phone FROM favorites)"
    elif exclude_sold:
        base += " AND phone NOT IN (SELECT phone FROM sold)"

    base += " GROUP BY phone ORDER BY MAX(created_at) DESC LIMIT ?"
    params.append(limit)

    cur.execute(base, params)
    rows = cur.fetchall()
    conn.close()
    return rows


# ---------- Dəstək funksiyalar ----------
def get_distinct_values(col):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        f"SELECT DISTINCT {col} FROM listings WHERE {col} IS NOT NULL AND TRIM({col}) != '' ORDER BY {col} ASC"
    )
    vals = [r[0] for r in c.fetchall()]
    conn.close()
    return vals


def get_listings_by_phone(phone):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM listings WHERE phone=? ORDER BY date_read DESC", (phone,))
    rows = c.fetchall()
    conn.close()
    return rows


def phone_stats(phone):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        SELECT 
            MIN(date_read), MAX(date_read),
            COUNT(*), AVG(price), MIN(price), MAX(price)
        FROM listings WHERE phone=?
    """,
        (phone,),
    )
    r = c.fetchone()
    conn.close()
    if not r:
        return {}
    min_d, max_d, cnt, avg_p, min_p, max_p = r
    trend = None
    if min_p and max_p and min_p != 0:
        trend = ((max_p - min_p) / min_p) * 100
    return {
        "first_date": min_d,
        "last_date": max_d,
        "count": cnt,
        "avg_price": avg_p,
        "min_price": min_p,
        "max_price": max_p,
        "trend_pct": trend,
    }


def normalize_phone(p):
    if not p:
        return None
    p = str(p)
    p = p.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if p.startswith("+994"):
        p = "0" + p[4:]
    elif not p.startswith("0") and len(p) == 9:
        p = "0" + p
    return p.strip()


def safe(v):
    if v is None:
        return None
    if pd.isna(v):
        return None
    s = str(v).strip()
    return s if s else None


def extract_site(link):
    try:
        return urlparse(str(link)).netloc.replace("www.", "").lower()
    except Exception:
        return None


# ---------- Əsas sinxron ----------
def sync_with_progress(
    date_from, date_to, days, progress_bar, label, state_controller=None
):
    print(
        f"[SYNC] Sinxron başlanır | date_from={date_from} date_to={date_to} days={days}"
    )

    try:
        conn = get_sql_conn()
        print("[OK] Connected to EstateBase SQL Server (SERVER\\dbestate3)")
    except Exception as err:
        print(f"[ERR] SQL connection failed: {err}")
        label.configure(text=f"[ERR] SQL connection failed: {err}")
        return 0

    where = ""
    if date_from and date_to:
        where = f"""
            WHERE CAST(p.insert_date_time AS date)
            BETWEEN '{date_from}' AND '{date_to}'
        """
    elif days and str(days).startswith("-"):
        n = int(days)
        where = f"""
            WHERE CAST(p.insert_date_time AS date)
            >= DATEADD(DAY, {n}, CAST(GETDATE() AS date))
        """

    query = f"""
    SELECT 
        p.insert_date_time,
        pt.property_type_name,
        o.operation_type_name,
        m.metro_name,
        rc.room_count_name,
        bt.building_type_name,
        p.floor,
        p.floor_of,
        p.area,
        p.general_area,
        p.price,
        c.currency_name,
        p.owner_phone_number_01,
        p.owner_phone_number_02,
        p.owner_full_name,
        p.address,
        d.document_name,
        p.data,
        p.source_note
    FROM dbo.property p
    LEFT JOIN dbo.property_type pt ON p.fk_id_property_type = pt.id_property_type
    LEFT JOIN dbo.building_type bt ON p.fk_id_building_type = bt.id_building_type
    LEFT JOIN dbo.operation_type o ON p.fk_id_operation_type = o.id_operation_type
    LEFT JOIN dbo.currency c ON p.fk_id_currency = c.id_currency
    LEFT JOIN dbo.document d ON p.fk_id_document = d.id_document
    LEFT JOIN dbo.metro m ON p.fk_id_metro = m.id_metro
    LEFT JOIN dbo.room_count rc ON p.fk_id_room = rc.id_room_count
    {where}
    ORDER BY p.insert_date_time DESC
    """

    df = pd.read_sql(query, conn)
    total = len(df)
    print(f"[INFO] Tapılan elan sayı: {total}")

    added = 0

    for i, r in enumerate(df.itertuples(index=False), start=1):
        date_only = str(r[0])[:10] if r[0] else None
        phone = safe(r[12]) or safe(r[13])
        if not phone:
            continue

        source_link = safe(r[18])

        rec = {
            "date_read": date_only,
            "prop_type": safe(r[1]),
            "operation": safe(r[2]),
            "metro": safe(r[3]),
            "rooms": safe(r[4]),
            "building": safe(r[5]),
            "floor": f"{safe(r[6])}/{safe(r[7])}" if r[6] or r[7] else None,
            "area_kvm": (
                f"{safe(r[8])} sot / {safe(r[9])} kvm" if r[8] or r[9] else None
            ),
            "price": float(r[10]) if r[10] else None,
            "currency": safe(r[11]),
            "phone": phone,
            "contact_name": safe(r[14]),
            "address": safe(r[15]),
            "document": safe(r[16]),
            "summary": safe(r[17]),
            "source_link": source_link,
        }

        if add_listing_row(rec):
            added += 1

        if i % 50 == 0:
            print(f"[STEP] {i}/{total}")

    conn.close()
    print(f"[DONE] Bitdi | əlavə edildi: {added}")
    return added


# ---------- BAT / CLI üçün ENTRY POINT ----------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--date-from", dest="date_from", default=None)
    parser.add_argument("--date-to", dest="date_to", default=None)
    parser.add_argument("--days", dest="days", default="-1")
    args = parser.parse_args()

    class DummyBar:
        def set(self, v):
            pass

    class DummyLabel:
        def configure(self, **kwargs):
            if "text" in kwargs:
                print(kwargs["text"])

    sync_with_progress(
        args.date_from,
        args.date_to,
        args.days,
        DummyBar(),
        DummyLabel(),
        state_controller=None,
    )

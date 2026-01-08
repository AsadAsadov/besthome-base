# ============================================
# estatebase_sync.py — EstateBase SQL → BestHomeBase
# FINAL + BAT FIX
# ============================================

import pyodbc
import pandas as pd
import time
from urllib.parse import urlparse
from datetime import datetime

from besthome_core import add_listing_row


# ---------- Təhlükəsiz dəyər ----------
def safe(v):
    if v is None:
        return None
    if pd.isna(v):
        return None
    s = str(v).strip()
    return s if s else None


# ---------- Saytı linkdən çıxar ----------
def extract_site(link):
    try:
        return urlparse(str(link)).netloc.replace("www.", "").lower()
    except Exception:
        return None


# ---------- Əsas sinxron ----------
def sync_with_progress(
    date_from, date_to, days, progress_bar, label, state_controller=None
):
    print(f"🔄 Sinxron başlanır | date_from={date_from} date_to={date_to} days={days}")

    conn_str = (
        "Driver={SQL Server};"
        "Server=.\\SQLEXPRESS;"
        "Database=besthome;"
        "Trusted_Connection=yes;"
    )

    try:
        conn = pyodbc.connect(conn_str)
    except Exception as err:
        print("❌ SQL bağlantı xətası:", err)
        label.configure(text=str(err))
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
    print(f"📥 Tapılan elan sayı: {total}")

    added = 0
    skipped = 0
    last_seen = set()  # (date, site, phone)

    for i, r in enumerate(df.itertuples(index=False), start=1):
        date_only = str(r[0])[:10] if r[0] else None
        phone = safe(r[12]) or safe(r[13])
        if not phone:
            continue

        source_link = safe(r[18])
        site = extract_site(source_link)

        key = (date_only, site, phone)
        if key in last_seen:
            skipped += 1
            continue
        last_seen.add(key)

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
            print(f"⏳ {i}/{total}")

    conn.close()
    print(f"🏁 Bitdi | əlavə edildi: {added} | run-dublikat: {skipped}")
    return added


# ---------- BAT / CLI üçün ENTRY POINT ----------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--date-from", dest="date_from", default=None)
    parser.add_argument("--date-to", dest="date_to", default=None)
    parser.add_argument("--days", dest="days", default="-1")
    args = parser.parse_args()

    # BAT üçün dummy UI obyektləri
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

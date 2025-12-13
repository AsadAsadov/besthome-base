# ============================================
# estatebase_sync.py — EstateBase SQL → BestHomeBase inteqrasiya (progress + duplikat nəzarəti)
# Əsəd Əsədov ©️ 2025
# ============================================

import pyodbc
import pandas as pd
import time
from besthome_core import add_listing_row
from datetime import datetime

# ---------- Təhlükəsiz dəyər funksiyası ----------
def safe(v):
    """Boş və NaN dəyərləri təmizləyir"""
    if v is None:
        return None
    if pd.isna(v):
        return None
    s = str(v).strip()
    return s if s else None


# ---------- Əsas sinxronizasiya funksiyası ----------
def sync_with_progress(date_from, date_to, days, progress_bar, label, state_controller=None):
    """SQL-dən məlumatları çəkir, dublikatları yoxlayır və dinamik progress göstərir."""
    print(f"🔄 Sinxron başlanır: {date_from} → {date_to} | gün: {days}")

    # Bağlantı sətri
    conn_str = (
        "Driver={SQL Server};"
        "Server=.\\SQLEXPRESS;"
        "Database=besthome;"
        "Trusted_Connection=yes;"
    )

    try:
        conn = pyodbc.connect(conn_str)
    except Exception as err:
        print(f"❌ Bağlantı xətası: {err}")
        label.configure(text=f"❌ Bağlantı xətası: {err}", text_color="#E74C3C")
        return 0

    # Dinamik WHERE (istifadəçinin daxil etdiyi tarix və ya gün aralığına görə)
    where = ""
    if date_from and date_to:
        where = f"WHERE CAST(p.insert_date_time AS date) BETWEEN '{date_from}' AND '{date_to}'"
    elif days and days.strip().startswith("-"):
        try:
            n = int(days)
            where = f"WHERE CAST(p.insert_date_time AS date) >= DATEADD(DAY, {n}, CAST(GETDATE() AS date))"
        except Exception as err:
            print("⚠️ Gün sayı səhvdir:", err)

    # SQL sorğusu
    query = f"""
    SELECT 
        p.insert_date_time AS [Oxunma tarixi],
        pt.property_type_name AS [Əmlak növü],
        o.operation_type_name AS [Əməliyyat],
        m.metro_name AS [Metro],
        rc.room_count_name AS [Otaq sayı],
        bt.building_type_name AS [Tikili növü],
        p.floor AS [Mərtəbə],
        p.floor_of AS [Binanın mərtəbəsi],
        p.area AS [Sahə sot],
        p.general_area AS [Sahə kvm],
        p.price AS [Qiymət],
        c.currency_name AS [Valyuta],
        p.owner_phone_number_01 AS [Əlaqə 1],
        p.owner_phone_number_02 AS [Əlaqə 2],
        p.owner_full_name AS [Ad],
        p.address AS [Ünvan],
        d.document_name AS [Sənəd],
        p.data AS [Ümumi məlumat],
        p.source_note AS [Link]
    FROM dbo.property p
    LEFT JOIN dbo.property_type pt ON p.fk_id_property_type = pt.id_property_type
    LEFT JOIN dbo.building_type bt ON p.fk_id_building_type = bt.id_building_type
    LEFT JOIN dbo.operation_type o ON p.fk_id_operation_type = o.id_operation_type
    LEFT JOIN dbo.currency c ON p.fk_id_currency = c.id_currency
    LEFT JOIN dbo.document d ON p.fk_id_document = d.id_document
    LEFT JOIN dbo.metro m ON p.fk_id_metro = m.id_metro
    LEFT JOIN dbo.room_count rc ON p.fk_id_room = rc.id_room_count
    {where}
    ORDER BY p.insert_date_time DESC;
    """

    try:
        df = pd.read_sql(query, conn)
    except Exception as err:
        print(f"❌ SQL sorğu xətası: {err}")
        label.configure(text=f"❌ SQL sorğu xətası: {err}", text_color="#E74C3C")
        return 0

    total = len(df)
    print(f"✅ SQL-dən {total} elan tapıldı.")

    if total == 0:
        label.configure(text="⚠️ Yeni elan tapılmadı", text_color="#888")
        conn.close()
        return 0

    # Məlumatları işləməyə hazırlaş
    added = 0
    skipped = 0
    last_seen = set()  # dublikatları saxlamaq üçün (site, phone, price)

    # Hər sətri oxu və SQLite bazasına yaz
    for i, r in enumerate(df.itertuples(index=False), start=1):
        try:
            if state_controller:
                stopped = state_controller.wait_if_paused()
                if stopped or state_controller.should_stop():
                    label.configure(text="⏹️ Sinxronizasiya dayandırıldı", text_color="#E74C3C")
                    break

            # Tarix formatı (yalnız YYYY-MM-DD)
            date_only = str(r[0])[:10] if r[0] else None

            # Əlaqə nömrəsi
            phone = safe(r[12]) or safe(r[13])
            if not phone:
                continue

            # Əsas dublikat açarı
            source_link = safe(r[18])

            key = (
                source_link,
                phone,
                str(safe(r[10])),  # qiymət
            )
            if key in last_seen:
                skipped += 1
                continue
            last_seen.add(key)

            # Qeyd
            rec = {
                "date_read": date_only,
                "prop_type": safe(r[1]),
                "operation": safe(r[2]),
                "metro": safe(r[3]),
                "rooms": safe(r[4]),
                "building": safe(r[5]),
                "floor": f"{safe(r[6])}/{safe(r[7])}" if r[6] or r[7] else None,
                "area_kvm": (
                    f"{safe(r[8])} sot / {safe(r[9])} kvm"
                    if r[8] or r[9]
                    else None
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

            # Real-time progress
            pct = i / total
            progress_bar.set(pct)
            label.configure(
                text=f"📊 Çəkilir: {i}/{total} ({int(pct * 100)}%)",
                text_color="#0078D4",
            )
            if i % 25 == 0:
                time.sleep(0.03)

        except Exception as err:
            print(f"⚠️ Sətir atlandı: {err}")
            continue

    conn.close()
    print(f"🏁 Tamamlandı: {added} elan əlavə edildi, {skipped} dublikat atlandı.")
    label.configure(
        text=f"✅ Tamamlandı: {added} yeni elan əlavə edildi | ♻️ {skipped} dublikat tapıldı",
        text_color="#2ECC71" if added > 0 else "#888",
    )
    progress_bar.set(1.0)
    return added

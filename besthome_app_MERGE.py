# ============================================
# besthome_app.py — BestHomeBase UI (Lite, Clean)
# ============================================
import os, re, time, webbrowser
from pathlib import Path

import pandas as pd
import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
import time
import random
import threading
import urllib.parse
import queue
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from urllib.parse import quote
from selenium.webdriver.common.action_chains import ActionChains


# Görüntü
from customtkinter import CTkImage
from PIL import Image, ImageOps, ImageDraw

# Core
from besthome_core import (
    init_db,
    ensure_tables,
    add_listing_row,
    get_distinct_values,
    query_phones_summary,
    get_listings_by_phone,
    set_favorite_phone,
    get_favorites_phones_map,
    add_sold,
    remove_sold,
    get_sold_set,
    phone_stats,
    normalize_phone,
)

# ---------------- Tema ----------------
PRIMARY = "#0078D4"
BG = "#FFFFFF"
ACCENT = "#E7EAF0"
TEXT = "#222222"
SOFT = "#F6F7F9"

ctk.set_appearance_mode("light")
ctk.set_widget_scaling(1.0)

# ---------------- License (demo/full) ----------------
try:
    from license_core import get_license_status

    _LICENSE_STATUS = (
        get_license_status()
    )  # returns: 'full', 'demo', 'invalid', 'empty', 'error'
except Exception:
    _LICENSE_STATUS = "full"  # fallback to full if license_core missing


# ---------------- Helper-lər ----------------
def rget(row, key, default=None):
    try:
        v = row[key]
        return default if v in (None, "") else v
    except Exception:
        return default


def _to_float(s):
    s = (str(s) if s is not None else "").strip().replace(" ", "").replace(",", "")
    try:
        return float(s) if s and re.fullmatch(r"\d+(\.\d+)?", s) else None
    except:
        return None


def parse_floor_current_total(s):
    if not s:
        return (None, None)
    nums = [int(x) for x in re.findall(r"\d+", str(s))]
    if len(nums) == 1:
        return (nums[0], None)
    if len(nums) >= 2:
        a, b = nums[0], nums[1]
        return (min(a, b), max(a, b))
    return (None, None)


def floor_display(s):
    cur, tot = parse_floor_current_total(s)
    if cur and tot:
        return f"{cur}/{tot}"
    if cur:
        return f"{cur}/-"
    return "-"


# ---------------- Splash (intro) ----------------
def show_splash(parent=None):
    splash = ctk.CTkToplevel(parent) if parent else ctk.CTk()
    splash.overrideredirect(True)
    splash.geometry("760x360+400+220")
    splash.configure(fg_color="#E8F7FC")

    main_frame = ctk.CTkFrame(splash, fg_color="#E8F7FC")
    main_frame.pack(fill="both", expand=True, padx=40, pady=25)

    # Sol (dairəvi logo)
    left = ctk.CTkFrame(main_frame, fg_color="#E8F7FC", width=230)
    left.pack(side="left", fill="y", padx=(10, 30))
    try:
        img = Image.open("besthomelogo.jpeg").convert("RGBA")
    except:
        try:
            img = Image.open("besthomelogo.png").convert("RGBA")
        except:
            img = None
    if img:
        img = ImageOps.contain(img, (160, 160))
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, img.size[0], img.size[1]), fill=255)
        img.putalpha(mask)
        logo = CTkImage(light_image=img, dark_image=img, size=(160, 160))
        lbl_img = ctk.CTkLabel(left, image=logo, text="")
        lbl_img.image = logo
        lbl_img.pack(expand=True, pady=(20, 20))
    else:
        ctk.CTkLabel(
            left, text="BESTHOME", font=("Segoe UI Semibold", 30), text_color="#0078D4"
        ).pack(expand=True)

    # Sağ (başlıq + progress)
    right = ctk.CTkFrame(main_frame, fg_color="#E8F7FC")
    right.pack(side="right", fill="both", expand=True, padx=(0, 10))

    ctk.CTkLabel(
        right,
        text="BESTHOME ƏMLAK BAZASI",
        font=("Segoe UI Semibold", 22),
        text_color="#0078D4",
    ).pack(pady=(40, 8))

    ctk.CTkLabel(
        right,
        text="Daşınmaz əmlak agentlikləri üçün avtomatlaşdırılmış idarəetmə sistemi.",
        text_color="#004f7c",
        font=("Segoe UI", 12),
        wraplength=400,
        justify="left",
    ).pack(pady=(0, 12))

    pb = ctk.CTkProgressBar(right, height=12, progress_color="#0078D4")
    pb.pack(fill="x", padx=20, pady=(40, 10))
    pb.set(0.0)

    percent_label = ctk.CTkLabel(
        right, text="🔄 Yüklənir... 0%", text_color="#004f7c", font=("Segoe UI", 11)
    )
    percent_label.pack(pady=(0, 10))

    bottom = ctk.CTkFrame(splash, fg_color="#0078D4", height=38)
    bottom.pack(fill="x", side="bottom")

    link = ctk.CTkLabel(
        bottom,
        text="WWW.BESTHOME.AZ",
        font=("Segoe UI Semibold", 15),
        text_color="white",
        cursor="hand2",
    )
    link.place(relx=0.5, rely=0.5, anchor="center")
    link.bind("<Button-1>", lambda e: webbrowser.open("https://www.besthome.az"))

    splash.update()
    splash.attributes("-alpha", 0.0)

    # Fade-in
    for a in range(0, 16):
        splash.attributes("-alpha", a / 15)
        splash.update()
        time.sleep(0.02)

    # Progress
    for i in range(101):
        pb.set(i / 100)
        percent_label.configure(text=f"🔄 Yüklənir... {i}%")
        splash.update_idletasks()
        time.sleep(0.01)

    # Fade-out
    for a in range(15, -1, -1):
        splash.attributes("-alpha", a / 15)
        splash.update()
        time.sleep(0.01)

    splash.destroy()


# ---------------- App ----------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🏠 BestHomeBase — Əmlak Bazası (Lite)")
        self.geometry("1280x820")
        self.minsize(1150, 700)
        self.configure(fg_color=BG)

        show_splash(self)
        self.after(0, lambda: self.state("zoomed"))

        # DB
        init_db()
        ensure_tables()

        # State
        self.keyword_var = ctk.StringVar()
        self.debounce_id = None

        # Overlay filter state
        self.filter_operation = set()
        self.filter_city = set()
        self.filter_metro = set()
        self.filter_rooms = set()
        self.filter_prop_type = set()
        self.filter_building = set()
        self.filter_price_min = None
        self.filter_price_max = None
        self.filter_area_min = None
        self.filter_area_max = None
        self.filter_floor_min = None
        self.filter_floor_max = None

        # Məhdudiyyətlər və aktiv tab
        self.limit_default = "500"
        self.active_tab = "all"  # "all" | "sold" | "fav" | "bot"
        # Favoritlər və satılanlar
        self.fav_colors = {}
        self.sold_set = set()

        # UI
        self._build_tabs()
        self._build_table()
        self._build_status()
        self._build_context_menu()
        self._build_header()
        self.after(700, self._reload_cache)
        self._bind_tab_change()
        self._bind_realtime()

        # --- Hadisələr və görünüş ---
        self.bind("<Configure>", lambda e: self._apply_col_widths())
        self.run_search()
        try:
            self._build_whatsapp_tab()
        except Exception as e:
            print(f"[⚠️ WhatsApp tab xətası] {e}")


    # ---------- Fayl import funksiyası (placeholder) ----------
    def import_file_with_progress(self):
        from tkinter import messagebox
        messagebox.showinfo("Import", "Bu funksiya hələ aktiv deyil.\nSinxronizasiya SQL vasitəsilə işləyir.")


        # ---------- Cache ----------
    def _reload_cache(self):
        self.fav_colors = get_favorites_phones_map()
        self.sold_set = get_sold_set()

    # ---------- Header ----------
    def _build_header(self):
        header = ctk.CTkFrame(
            self, corner_radius=12, fg_color=BG, border_width=1, border_color=ACCENT
        )
        header.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkLabel(
            header,
            text="Geniş Axtarış",
            text_color=PRIMARY,
            font=("Segoe UI Semibold", 16),
        ).grid(row=0, column=0, padx=10, pady=(10, 6), sticky="w")

        # Açar söz
        entry_frame = ctk.CTkFrame(header, fg_color=BG)
        entry_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")
        self.entry_kw = ctk.CTkEntry(
            entry_frame,
            textvariable=self.keyword_var,
            width=260,
            placeholder_text="🔍 Açar söz",
            fg_color=SOFT,
            border_color=ACCENT,
        )
        self.entry_kw.pack(side="left")

        
        # ---------- Tarix aralığı (əl ilə daxil + axtarış) ----------
        # ---------- Tarix aralığı ----------
        dates = ctk.CTkFrame(header, fg_color=BG)
        dates.grid(row=1, column=1, padx=8, pady=(0, 10), sticky="w")

        ctk.CTkLabel(
            dates, text="Tarix:", text_color=TEXT
        ).pack(side="left", padx=(0, 6))

        self.e_from = ctk.CTkEntry(dates, width=120, placeholder_text="Başlanğıc")
        self.e_from.pack(side="left", padx=(0, 4))

        self.e_to = ctk.CTkEntry(dates, width=120, placeholder_text="Son")
        self.e_to.pack(side="left", padx=(0, 8))

        # ✅ Avtomatik formatlaşdırma (YYYY-MM-DD) — artıq bug yoxdur
        def _auto_format(entry, *_):
            val = re.sub(r"[^\d]", "", entry.get())  # yalnız rəqəmləri saxla
            if len(val) > 8:
                val = val[:8]
            # İli, ayı və günü düzgün ayırır
            if len(val) >= 5:
                formatted = f"{val[:4]}-{val[4:6]}"
            elif len(val) >= 3:
                formatted = f"{val[:4]}-"
            else:
                formatted = val
            if len(val) >= 7:
                formatted = f"{val[:4]}-{val[4:6]}-{val[6:]}"
            entry.delete(0, "end")
            entry.insert(0, formatted)

        self.e_from.bind("<KeyRelease>", lambda e: _auto_format(self.e_from))
        self.e_to.bind("<KeyRelease>", lambda e: _auto_format(self.e_to))

        # 🔍 Tarixə görə tap düyməsi
        def _filter_by_date():
            from_date = self.e_from.get().strip()
            to_date = self.e_to.get().strip()
            if not from_date and not to_date:
                messagebox.showinfo("Məlumat", "Zəhmət olmasa tarix aralığı daxil edin.", parent=self)
                return
            self.run_search()

        ctk.CTkButton(
            dates,
            text="🔍 Tap",
            fg_color=PRIMARY,
            command=_filter_by_date
        ).pack(side="left", padx=(4, 0))



        # Limit
        limf = ctk.CTkFrame(header, fg_color=BG)
        limf.grid(row=1, column=2, padx=8, pady=(0, 10), sticky="w")
        ctk.CTkLabel(limf, text="Limit:", text_color=TEXT).pack(
            side="left", padx=(0, 6)
        )
        self.entry_limit = ctk.CTkEntry(limf, width=90)
        self.entry_limit.insert(0, self.limit_default)
        self.entry_limit.pack(side="left")

        # Düymələr
        btns = ctk.CTkFrame(header, fg_color=BG)
        btns.grid(row=1, column=3, padx=8, pady=(0, 10), sticky="w")
        ctk.CTkButton(
            btns, text="Filtr et", fg_color=PRIMARY, command=self.run_search
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            btns, text="Təmizlə", fg_color="#9aa0a6", command=self.reset_filters
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            btns,
            text="İdxal (Excel/CSV)",
            fg_color=PRIMARY,
            command=self.import_file_with_progress,
        ).pack(side="left", padx=6)

        for i in range(4):
            header.grid_columnconfigure(i, weight=1)

    def _last10(self):
        import datetime as dt

        to = dt.date.today()
        frm = to - dt.timedelta(days=9)
        self.e_from.delete(0, "end")
        self.e_from.insert(0, frm.isoformat())
        self.e_to.delete(0, "end")
        self.e_to.insert(0, to.isoformat())
        self.run_search()

    # ---------- Tabs ----------
    def _build_tabs(self):
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        self.tab_all = self.tabs.add("Bütün Elanlar")
        self.tab_sold = self.tabs.add("Satılanlar")
        self.tab_fav = self.tabs.add("Fərqləndirilənlər")
        self.tabs.add("WhatsApp Bot")
        #self.tabs.add("Statistika")
        self.tabs.add("Parametrlər")
        #self.tabs.add("Yardım")

        # 🔹 Parametrlər tabına SQL sinxron düyməsi (faizli və modern versiya)
        # ---------- PARAMETRLƏR TABI — Analitika Dashboard (modern UI) ----------
        try:
            import estatebase_sync
            import sqlite3
            from tkcalendar import DateEntry
            import datetime
            import threading
            import time

            param_tab = self.tabs.tab("Parametrlər")

            # Ana konteyner
            main_frame = ctk.CTkFrame(param_tab, fg_color="#F5F8FF", corner_radius=12)
            main_frame.pack(fill="both", expand=True, padx=25, pady=25)

            # Başlıq
            ctk.CTkLabel(
                main_frame,
                text="📊 BestHome Analitika Mərkəzi",
                font=("Segoe UI Black", 20),
                text_color="#0078D4",
            ).pack(pady=(8, 10))

            # -------------- Statistik Kartlar --------------
            cards_frame = ctk.CTkFrame(main_frame, fg_color="#FFFFFF", corner_radius=12)
            cards_frame.pack(fill="x", padx=10, pady=(0, 12))

            # 4 kart — Ümumi, Satış, Kirayə, Dublikat
            stat_labels = {}

            def make_card(parent, title, emoji, color, col):
                frame = ctk.CTkFrame(parent, fg_color=color, corner_radius=10)
                frame.grid(row=0, column=col, padx=10, pady=10, sticky="nsew")
                ctk.CTkLabel(
                    frame,
                    text=f"{emoji} {title}",
                    font=("Segoe UI Semibold", 13),
                    text_color="white",
                ).pack(anchor="w", padx=10, pady=(6, 0))
                lbl = ctk.CTkLabel(
                    frame,
                    text="0",
                    font=("Segoe UI Black", 22),
                    text_color="white",
                )
                lbl.pack(anchor="w", padx=14, pady=(0, 8))
                stat_labels[title] = lbl

            cards_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
            make_card(cards_frame, "Ümumi", "📦", "#0078D4", 0)
            make_card(cards_frame, "Satış", "💰", "#27AE60", 1)
            make_card(cards_frame, "Kirayə", "🏠", "#E67E22", 2)
            make_card(cards_frame, "Dublikat", "♻️", "#C0392B", 3)

            # -------------- Tarix Seçimi və Server Sinxron --------------
            control_frame = ctk.CTkFrame(main_frame, fg_color="#EDF2FA", corner_radius=10)
            control_frame.pack(fill="x", padx=10, pady=(0, 10))

            ctk.CTkLabel(control_frame, text="📅 Tarixdən:", text_color="#333").grid(row=0, column=0, padx=(10, 5), pady=10)
            from_cal = DateEntry(control_frame, width=12, background="#0078D4", foreground="white", date_pattern="yyyy-mm-dd")
            from_cal.set_date(datetime.date.today() - datetime.timedelta(days=7))
            from_cal.grid(row=0, column=1, padx=(0, 20))

            ctk.CTkLabel(control_frame, text="📅 Tarixə:", text_color="#333").grid(row=0, column=2, padx=(10, 5), pady=10)
            to_cal = DateEntry(control_frame, width=12, background="#0078D4", foreground="white", date_pattern="yyyy-mm-dd")
            to_cal.set_date(datetime.date.today())
            to_cal.grid(row=0, column=3, padx=(0, 20))

            ctk.CTkLabel(control_frame, text="📆 Son günlər (-10 və s.):", text_color="#333").grid(row=0, column=4, padx=(10, 5))
            day_entry = ctk.CTkEntry(control_frame, width=80)
            day_entry.insert(0, "-1")
            day_entry.grid(row=0, column=5, padx=(0, 10))

            # Progress göstəricisi
            progress_bar = ctk.CTkProgressBar(main_frame, height=14, progress_color="#0078D4")
            progress_bar.pack(fill="x", padx=20, pady=(12, 4))
            progress_bar.set(0)
            progress_label = ctk.CTkLabel(main_frame, text="Hazır.", text_color="#666")
            progress_label.pack(anchor="w", padx=25, pady=(0, 10))

            # -------------- Əlavə Statistik Məlumat --------------
            detail_frame = ctk.CTkFrame(main_frame, fg_color="#FFFFFF", corner_radius=10)
            detail_frame.pack(fill="both", expand=True, padx=10, pady=10)
            detail_label = ctk.CTkLabel(
                detail_frame,
                text="📈 Ətraflı analiz hazır deyil.",
                font=("Segoe UI", 13),
                text_color="#444",
                justify="left",
            )
            detail_label.pack(anchor="w", padx=15, pady=15)

            # 🔹 Statistikanı yeniləyən funksiya
            def update_statistics():
                try:
                    conn = sqlite3.connect("besthome.db")
                    c = conn.cursor()

                    c.execute("SELECT COUNT(*) FROM listings")
                    total = c.fetchone()[0] or 0
                    c.execute("SELECT COUNT(*) FROM listings WHERE operation LIKE '%Sat%'")
                    sales = c.fetchone()[0] or 0
                    c.execute("SELECT COUNT(*) FROM listings WHERE operation LIKE '%Kiray%'")
                    rent = c.fetchone()[0] or 0
                    c.execute("""
                        SELECT prop_type, COUNT(*) FROM listings
                        WHERE prop_type IS NOT NULL AND TRIM(prop_type) != ''
                        GROUP BY prop_type ORDER BY COUNT(*) DESC LIMIT 5
                    """)
                    categories = c.fetchall()

                    # Əlavə statistik mətn
                    top_text = "🏆 Ən çox elan olan kateqoriyalar:\n"
                    for i, (cat, cnt) in enumerate(categories, start=1):
                        top_text += f"  {i}. {cat} — {cnt} elan\n"

                    detail_label.configure(
                        text=f"{top_text}\n🔹 Ümumi elanlar: {total}\n💰 Satış: {sales}\n🏠 Kirayə: {rent}",
                        text_color="#333",
                    )

                    # Kart saylarını yenilə
                    stat_labels["Ümumi"].configure(text=f"{total:,}")
                    stat_labels["Satış"].configure(text=f"{sales:,}")
                    stat_labels["Kirayə"].configure(text=f"{rent:,}")

                    # Dublikat sayı
                    c.execute("""
                        SELECT COUNT(*) FROM (
                            SELECT phone FROM listings
                            WHERE phone IS NOT NULL
                            GROUP BY phone, price, rooms, area_kvm
                            HAVING COUNT(*) > 1
                        )
                    """)
                    dupes = c.fetchone()[0] or 0
                    stat_labels["Dublikat"].configure(text=f"{dupes:,}")

                    conn.close()

                except Exception as err:
                    detail_label.configure(text=f"⚠️ Statistika xətası: {err}", text_color="#E74C3C")

            # 🔹 Serverdən məlumat sinxron funksiyası
            def run_sync():
                def worker():
                    try:
                        progress_label.configure(text="📡 Serverdən məlumat yüklənir...", text_color="#E67E22")
                        progress_bar.set(0.05)

                        date_from = from_cal.get_date().strftime("%Y-%m-%d")
                        date_to = to_cal.get_date().strftime("%Y-%m-%d")
                        days = day_entry.get().strip()

                        added_total = estatebase_sync.sync_with_progress(date_from, date_to, days, progress_bar, progress_label)
                        update_statistics()

                        progress_bar.set(1.0)
                        progress_label.configure(
                            text=f"✅ Serverdən {added_total} yeni elan yükləndi.",
                            text_color="#27AE60",
                        )
                        self._reload_cache()
                        self.run_search()
                    except Exception as err:
                        progress_label.configure(text=f"❌ Xəta: {err}", text_color="#E74C3C")

                threading.Thread(target=worker, daemon=True).start()

            # 🔹 Sinxron düyməsi
            ctk.CTkButton(
                main_frame,
                text="🔄 Serverdən məlumat çək və yenilə",
                fg_color="#0078D4",
                hover_color="#005EA6",
                height=42,
                font=("Segoe UI Semibold", 14),
                command=run_sync,
            ).pack(pady=(5, 15))

            # İlk açılışda statistik məlumatları göstər
            update_statistics()

        except Exception as err:
            print("⚠️ Parametrlər tabı açıla bilmədi:", err)




    # ---------- Tab dəyişimi (sabit versiya) ----------
    def _bind_tab_change(self):
        """Tab dəyişimini izləyir və aktiv tabı yeniləyir."""
        # Hər tabın öz 'frame' obyektinə görə yoxlama aparırıq
        self.tabs_frames = {
            str(self.tab_all): "all",
            str(self.tab_sold): "sold",
            str(self.tab_fav): "fav",
        }
        self._active_tab_obj = None
        self.after(300, self._check_tab_switch)

    def _check_tab_switch(self):
        """Hər 0.3 saniyədə aktiv tab-ı real şəkildə yoxlayır."""
        try:
            current_tab_obj = (
                str(self.tabs._current_name)
                if hasattr(self.tabs, "_current_name")
                else str(self.tabs._tab_dict[self.tabs.get()])
            )
        except Exception:
            current_tab_obj = None

        if current_tab_obj != self._active_tab_obj:
            self._active_tab_obj = current_tab_obj
            if current_tab_obj and current_tab_obj in self.tabs_frames:
                self.active_tab = self.tabs_frames[current_tab_obj]
            else:
                self.active_tab = "all"

            print(f"🟢 TAB dəyişdi (real): {self.active_tab}")
            self.run_search()

        self.after(300, self._check_tab_switch)

    # ---------- Cədvəl ----------
    def _build_table(self):
        self.table_parent = self.tab_all
        self._create_tree(self.table_parent)


    def _create_tree(self, parent):
        container = ctk.CTkFrame(parent, fg_color=BG)
        container.pack(fill="both", expand=True, padx=6, pady=6)

        # Yeni sütunlar

        # Cədvəl sütunları
        self.cols = (
            "date_read",
            "prop_type",
            "operation",
            "metro",
            "rooms",
            "building",
            "floor",
            "area_kvm",
            "price",
            "currency",
            "phone",
            "contact_name",
            "address",
            "document",
            "summary",
            "source_link",
        )


        # Filtrlənə bilən sütunlar
        self.filterable_cols = {
            "prop_type",
            "building",
            "operation",
            "city_district",
            "metro",
            "rooms",
            "price",
            "floor",
            "area_kvm",
            "area_sot",
        }

        self.tree = ttk.Treeview(container, columns=self.cols, show="headings")

        vsb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # ✅ BURADAN SONRA əlavə et (daşma problemi üçün)
        self.tree.tag_configure("truncate", foreground="#222")

        for iid in self.tree.get_children():
            vals = list(self.tree.item(iid, "values"))
            if len(vals) > self.cols.index("summary"):
                text = vals[self.cols.index("summary")]
                if text and len(text) > 120:
                    vals[self.cols.index("summary")] = text[:117] + "..."
                    self.tree.item(iid, values=vals)


        # Başlıqlar
        heads = {
            "date_read": "Oxunma tarixi",
            "prop_type": "Əmlak növü",
            "operation": "Əməliyyat",
            "metro": "Metro",
            "rooms": "Otaq sayı",
            "building": "Tikili növü",
            "floor": "Mərtəbə",
            "area_kvm": "Sahə (sot / kvm)",
            "price": "Qiymət",
            "currency": "Valyuta",
            "phone": "Əlaqə nömrəsi",
            "contact_name": "Ad (sahibi)",
            "address": "Ünvan",
            "document": "Sənəd",
            "summary": "Ümumi məlumat",
            "source_link": "Link",
        }

        # Dizayn tərzi
        style = ttk.Style(self)
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=26)
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 10))
        style.map(
            "Treeview",
            background=[("selected", PRIMARY)],
            foreground=[("selected", "white")],
        )

        for c, t in heads.items():
            title = t + (" ▼" if c in self.filterable_cols else "")
            self.tree.heading(c, text=title)

        self._apply_col_widths()
        self.tree.bind("<Button-1>", self._on_heading_click)
        self.tree.bind("<Double-1>", self._on_row_double_click)
        self.tree.bind("<Button-3>", self._show_ctx)


    # ---------- Double click → Link və ya Detallar ----------
    def _on_row_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        vals = self.tree.item(item_id, "values")
        if not vals or len(vals) < len(self.cols):
            return

        self._open_property_details(vals)


    def _apply_col_widths(self):
        if not hasattr(self, "tree"):
            return
        total = max(self.tree.winfo_width() - 20, 1200)
        ratios = {
            "kod": 0.06,
            "date_read": 0.08,
            "prop_type": 0.09,
            "operation": 0.07,
            "city_district": 0.10,
            "metro": 0.08,
            "rooms": 0.06,
            "building": 0.09,
            "floor": 0.06,
            "area_sot": 0.07,
            "area_kvm": 0.07,
            "price": 0.08,
            "currency": 0.05,
            "phone": 0.08,
            "contact_name": 0.08,
            "address": 0.10,
            "document": 0.07,
            "source_link": 0.12,
        }
        anchors = {
            "kod": "center",
            "date_read": "center",
            "operation": "center",
            "rooms": "center",
            "floor": "center",
            "price": "e",
            "area_sot": "e",
            "area_kvm": "e",
        }
        
        # 💸 Valyuta sütununu gizlət
        try:
            self.tree.column("currency", width=0, stretch=False, minwidth=0)
        except Exception:
            pass

        for k in self.cols:
            self.tree.column(
                k, width=int(total * ratios.get(k, 0.1)), anchor=anchors.get(k, "w")
            )
    # ---------- Status ----------
    def _build_status(self):
        bar = ctk.CTkFrame(self, fg_color=BG)
        bar.pack(fill="x", padx=12, pady=(0, 12))
        self.lbl_status = ctk.CTkLabel(bar, text="Hazır.", text_color=TEXT)
        self.lbl_status.pack(side="left", padx=10)

        try:
            img = Image.open("besthomelogo.png")
            logo = CTkImage(img, size=(64, 64))
            self.logo_lbl = ctk.CTkLabel(bar, image=logo, text="", cursor="hand2")
            self.logo_lbl.image = logo
            self.logo_lbl.pack(side="right", padx=6, pady=2)
            self.logo_lbl.bind(
                "<Button-1>", lambda _=None: webbrowser.open("https://www.besthome.az")
            )
        except Exception:
            pass

    # ---------- Kontekst menyu ----------
    def _build_context_menu(self):
        self.ctx = None

    def _show_ctx(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        if self.ctx and self.ctx.winfo_exists():
            try:
                self.ctx.destroy()
            except:
                pass
        self.ctx = ctk.CTkToplevel(self)
        self.ctx.overrideredirect(True)
        self.ctx.attributes("-topmost", True)
        self.ctx.geometry(f"+{event.x_root}+{event.y_root}")
        frm = ctk.CTkFrame(
            self.ctx, fg_color=BG, border_color=ACCENT, border_width=1, corner_radius=8
        )
        frm.pack(fill="both", expand=True)

        # Fərqləndirmə (hover-lə rənglər)
        row1 = ctk.CTkFrame(frm, fg_color=BG)
        row1.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(row1, text="🌟 Fərqləndir:", text_color=TEXT).pack(
            side="left", padx=(2, 10)
        )
        colors = {
            "Mavi": "#e8f2ff",
            "Yaşıl": "#e8ffe8",
            "Sarı": "#fff9d6",
            "Qırmızı": "#ffe8e8",
        }
        for name, col in colors.items():
            b = ctk.CTkButton(
                row1,
                text=name,
                fg_color=col,
                text_color="#111",
                command=lambda c=col: self._ctx_mark_favorite_color(c),
                width=64,
            )
            b.pack(side="left", padx=4)

        # Satılan idarəetmə
        row2 = ctk.CTkFrame(frm, fg_color=BG)
        row2.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(
            row2,
            text="✅ Satılanlara əlavə et",
            fg_color=PRIMARY,
            command=self._ctx_add_sold,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            row2,
            text="↩️ Satılandan çıxart",
            fg_color="#9aa0a6",
            command=self._ctx_remove_sold,
        ).pack(side="left", padx=4)

        # Əmlak linkini aç
        row3 = ctk.CTkFrame(frm, fg_color=BG)
        row3.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(
            row3,
            text="🌐 Elanı aç (Link)",
            fg_color="#25D366",
            command=self._ctx_open_link,
        ).pack(side="left", padx=4)

        def close_ctx(_=None):
            try:
                self.ctx.destroy()
            except:
                pass

        self.bind_all("<Button-1>", lambda e: close_ctx(), add="+")
        self.ctx.bind("<FocusOut>", lambda e: close_ctx())

    def _ctx_open_link(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        try:
            link_idx = self.cols.index("source_link")
            link_val = vals[link_idx]
            if link_val and str(link_val).startswith(("http://", "https://")):
                import webbrowser
                webbrowser.open(link_val)
            else:
                messagebox.showinfo("Məlumat", "Bu sətirdə keçərli link yoxdur.")
        except Exception as e:
            messagebox.showerror("Xəta", f"Link açıla bilmədi:\n{e}")

    def _ctx_mark_favorite_color(self, color):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        phone = normalize_phone(vals[self.cols.index("phone")])
        if not phone:
            return
        set_favorite_phone(phone, color)
        self._reload_cache()
        self.run_search()

    def _ctx_add_sold(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        phone = normalize_phone(vals[self.cols.index("phone")])
        if not phone:
            return
        add_sold(phone)
        self._reload_cache()
        self.run_search()

    def _ctx_remove_sold(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        phone = normalize_phone(vals[self.cols.index("phone")])
        if not phone:
            return
        remove_sold(phone)
        self._reload_cache()
        self.run_search()

    # ---------- Realtime ----------
    def _bind_realtime(self):
        def on_change(*_):
            if self.debounce_id:
                try:
                    self.after_cancel(self.debounce_id)
                except:
                    pass
            self.debounce_id = self.after(300, self.run_search)

        self.entry_kw.bind("<KeyRelease>", lambda e: on_change())

    # ---------- Axtarış + render ----------
    def _get_limit(self):
        val = (self.entry_limit.get() or "").strip()
        if not val:
            return 500
        try:
            iv = int(val)
            if iv > 10000:
                self._toast("🔔 Elan sayının çox olması bazanı yavaşlada bilər.")
            return max(1, iv)
        except:
            return 500

    def reset_filters(self):
        self.keyword_var.set("")
        self.e_from.delete(0, "end")
        self.e_to.delete(0, "end")
        self.filter_operation.clear()
        self.filter_city.clear()
        self.filter_metro.clear()
        self.filter_rooms.clear()
        self.filter_prop_type.clear()
        self.filter_building.clear()
        self.filter_price_min = self.filter_price_max = None
        self.filter_area_min = self.filter_area_max = None
        self.filter_floor_min = self.filter_floor_max = None
        self.entry_limit.delete(0, "end")
        self.entry_limit.insert(0, self.limit_default)
        self.run_search()

    def run_search(self):
        """Axtarış bütün tablarda keçərlidir və nəticələri yeniləyir."""
        kw = (self.keyword_var.get() or "").strip()
        limit = self._get_limit() if hasattr(self, "_get_limit") else int(self.limit_default)

        # Aktiv taba uyğun hansı cədvəli yeniləyəcəyik?
        if self.active_tab == "sold":
            only_sold = True
            only_favorites = False
        elif self.active_tab == "fav":
            only_sold = False
            only_favorites = True
        else:
            only_sold = False
            only_favorites = False

        # 🔍 Məlumatları DB-dən çək
        rows = query_phones_summary(
            keyword=(kw if kw else None),
            limit=limit,
            only_sold=only_sold,
            only_favorites=only_favorites,
        )

        # Əsas cədvəl valideyni müəyyən et
        if self.active_tab == "sold":
            parent = self.tab_sold
        elif self.active_tab == "fav":
            parent = self.tab_fav
        else:
            parent = self.tab_all

        # Cədvəl varsa, təmizləyib doldur
        if hasattr(self, "tree"):
            try:
                self.tree.delete(*self.tree.get_children())
            except Exception:
                pass
        else:
            # Əgər treeview hələ qurulmayıbsa — yaradırıq
            self._create_tree(parent)

        # 🔹 Boş nəticə üçün logo göstər
        if not rows:
            for w in parent.winfo_children():
                if isinstance(w, ctk.CTkFrame) and getattr(w, "is_placeholder", False):
                    try:
                        w.destroy()
                    except:
                        pass
            placeholder = ctk.CTkFrame(parent, fg_color="white")
            placeholder.is_placeholder = True
            placeholder.place(relx=0.5, rely=0.5, anchor="center")

            try:
                from PIL import Image
                img = Image.open("besthomelogo.png")
                logo = CTkImage(img, size=(120, 120))
                lbl = ctk.CTkLabel(placeholder, image=logo, text="")
                lbl.image = logo
                lbl.pack()
            except:
                ctk.CTkLabel(
                    placeholder,
                    text="📭 Nəticə tapılmadı",
                    font=("Segoe UI", 15),
                    text_color="#555",
                ).pack()
            return

        # 🔹 Əgər nəticə varsa — logo varsa sil və nəticələri əlavə et
        for w in parent.winfo_children():
            if isinstance(w, ctk.CTkFrame) and getattr(w, "is_placeholder", False):
                try:
                    w.destroy()
                except:
                    pass

        # Nəticələri TreeView-ə əlavə et
        for r in rows:
            vals = [
                r["date_read"] or "",
                r["prop_type"] or "",
                r["operation"] or "",
                r["metro"] or "",
                r["rooms"] or "",
                r["building"] or "",
                r["floor"] or "",
                r["area_kvm"] or "",
                r["price"] or "",
                r["currency"] or "",
                r["phone"] or "",
                r["contact_name"] or "",
                r["address"] or "",
                r["document"] or "",
                r["summary"] or "",
                r["source_link"] or "",
            ]
            self.tree.insert("", "end", values=vals)


            # Əməliyyat overlay (başlıqdan)
            ops = list(self.filter_operation)
            op_param = ops[0] if len(ops) == 1 else None

            date_from = (self.e_from.get() or "").strip() or None
            date_to = (self.e_to.get() or "").strip() or None
            limit = self._get_limit()

        def _on_heading_click(self, event):
            region = self.tree.identify("region", event.x, event.y)
            if region != "heading":
                return
            idx = int(self.tree.identify_column(event.x).replace("#", "")) - 1
            if 0 <= idx < len(self.cols):
                col_name = self.cols[idx]
                print(f"📊 Sütuna klik: {col_name}")

        # --- Tab konteksti ---
        tab_title = self.tabs.get() if hasattr(self, "tabs") else "Bütün Elanlar"
        if "Bütün" in tab_title:
            self.active_tab = "all"
        elif "Satılan" in tab_title:
            self.active_tab = "sold"
        elif "Fərqləndirilən" in tab_title:
            self.active_tab = "fav"
        else:
            self.active_tab = "all"

        # --- Filtrləmə rejimi ---
        exclude_sold = self.active_tab == "all"  # yalnız "Bütün Elanlar" üçün
        only_sold = self.active_tab == "sold"  # yalnız Satılanlar üçün
        only_fav = self.active_tab == "fav"  # yalnız Fərqləndirilənlər üçün

        print(
            f"🟢 run_search() tab: {self.active_tab} | exclude_sold={exclude_sold} | only_sold={only_sold} | only_fav={only_fav}"
        )

        # --- Sorğu ---
        rows = query_phones_summary(
            keyword=(kw if kw else None),
            limit=limit,
            date_from=date_from,
            date_to=date_to,
            exclude_sold=exclude_sold,
            only_sold=only_sold,
            only_favorites=only_fav,
        )

        # ---------- Lokal overlay filterlər ----------
        out = []
        for r in rows:
            try:
                # Əməliyyat (Satılır / Kirayə verilir)
                if self.filter_operation and (
                    rget(r, "operation", "") not in self.filter_operation
                ):
                    continue
                if self.filter_prop_type and (
                    rget(r, "prop_type", "") not in self.filter_prop_type
                ):
                    continue
                if self.filter_building and (
                    rget(r, "building", "") not in self.filter_building
                ):
                    continue
                if self.filter_city and (
                    rget(r, "city_district", "") not in self.filter_city
                ):
                    continue
                if self.filter_metro and (
                    rget(r, "metro", "") not in self.filter_metro
                ):
                    continue
                if self.filter_rooms and (
                    rget(r, "rooms", "") not in self.filter_rooms
                ):
                    continue

                # Qiymət filteri
                try:
                    p = rget(r, "price")
                    p_val = float(p) if p not in (None, "", "-") else None
                except Exception:
                    p_val = None

                if self.filter_price_min is not None and (
                    p_val is None or p_val < self.filter_price_min
                ):
                    continue
                if self.filter_price_max is not None and (
                    p_val is None or p_val > self.filter_price_max
                ):
                    continue

                # Sahə filteri
                try:
                    ak = rget(r, "area_kvm")
                    akv = float(ak) if ak not in (None, "", "-") else None
                except Exception:
                    akv = None
                if self.filter_area_min is not None and (
                    akv is None or akv < self.filter_area_min
                ):
                    continue
                if self.filter_area_max is not None and (
                    akv is None or akv > self.filter_area_max
                ):
                    continue

                # Mərtəbə filteri
                cur, _ = parse_floor_current_total(rget(r, "floor"))
                if (
                    self.filter_floor_min is not None
                    or self.filter_floor_max is not None
                ):
                    if cur is None:
                        continue
                    if (
                        self.filter_floor_min is not None
                        and self.filter_floor_max is None
                    ):
                        if cur != int(self.filter_floor_min):
                            continue
                    else:
                        if self.filter_floor_min is not None and cur < int(
                            self.filter_floor_min
                        ):
                            continue
                        if self.filter_floor_max is not None and cur > int(
                            self.filter_floor_max
                        ):
                            continue

                out.append(r)
            except Exception as e:
                print(f"[⚠️ Filter skip] xəta: {e}")
                continue

                # ---------- Render ----------
        self.tree.delete(*self.tree.get_children())
        kir = 0
        sat = 0
        favmap = self.fav_colors

        for r in out:
            try:
                date_txt = rget(r, "date_read") or rget(r, "created_at", "-")
                if date_txt and len(date_txt) >= 10:
                    date_txt = date_txt[:10]

                ak = rget(r, "area_kvm")
                asot = rget(r, "area_sot")
                area_disp = "-"
                if ak or asot:
                    area_disp = (
                        " / ".join(
                            [
                                x
                                for x in (
                                    f"{ak} kvm" if ak else "",
                                    f"{asot} sot" if asot else "",
                                )
                                if x
                            ]
                        )
                        or "-"
                    )

                # Qiymət formatı
                try:
                    p = rget(r, "price")
                    cur = rget(r, "currency", "")
                    price_txt = "-"
                    if p not in (None, "", "-"):
                        price_txt = f"{int(float(p)):,} {cur}".replace(",", " ")
                except Exception:
                    price_txt = str(rget(r, "price", "-"))

                phone = normalize_phone(rget(r, "phone", "-"))
                vals = [
                    rget(r, "date_read", "-"),
                    rget(r, "prop_type", "-"),
                    rget(r, "operation", "-"),
                    rget(r, "metro", "-"),
                    rget(r, "rooms", "-"),
                    rget(r, "building", "-"),
                    floor_display(rget(r, "floor")),
                    rget(r, "area_kvm", "-"),
                    rget(r, "price", "-"),
                    "-",  # Valyuta çıxarılıb
                    rget(r, "phone", "-"),
                    rget(r, "contact_name", "-"),
                    rget(r, "address", "-"),
                    rget(r, "document", "-"),
                    rget(r, "summary", "-"),
                    rget(r, "source_link", "-"),
                ]

                op = (rget(r, "operation", "") or "").lower()
                if "kiray" in op:
                    kir += 1
                if "sat" in op:
                    sat += 1

                color = favmap.get(phone)
                if color:
                    tag = f"fav_{color}"
                    try:
                        self.tree.tag_configure(tag, background=color)
                    except Exception:
                        pass
                    self.tree.insert("", "end", values=vals, tags=(tag,))
                else:
                    self.tree.insert("", "end", values=vals)
            except Exception as e:
                print(f"[⚠️ Render skip] xəta: {e}")
                continue

        self.lbl_status.configure(
            text=f"Tapıldı: {len(out)} | Kirayə: {kir} | Satılır: {sat}"
        )
        self.tree.update_idletasks()
        self.update_idletasks()
        self.after(
            100,
            lambda: (
                self.tree.see(self.tree.get_children()[0])
                if self.tree.get_children()
                else None
            ),
        )

        # =====================================
        # 📭 Boş nəticə üçün loqo + yazı (tam işlək versiya — bütün tablar üçün)
        # =====================================
        # Aktiv taba uyğun parent seç
        current_parent = {
            "all": self.tab_all,
            "sold": self.tab_sold,
            "fav": self.tab_fav,
        }.get(self.active_tab, self.tab_all)

        # Əvvəlki placeholder varsa sil
        for w in current_parent.winfo_children():
            if isinstance(w, ctk.CTkFrame) and getattr(w, "is_placeholder", False):
                try:
                    w.destroy()
                except:
                    pass

        # Əgər nəticə boşdursa, loqo + yazı göstər
        if not out:
            placeholder = ctk.CTkFrame(current_parent, fg_color=BG)
            placeholder.is_placeholder = True
            placeholder.place(relx=0.5, rely=0.5, anchor="center")

            try:
                img = Image.open("besthomelogo.png")
                logo = CTkImage(img, size=(130, 130))
                lbl_logo = ctk.CTkLabel(placeholder, image=logo, text="")
                lbl_logo.image = logo
                lbl_logo.pack(pady=(12, 8))
            except Exception:
                ctk.CTkLabel(
                    placeholder,
                    text="BESTHOME",
                    font=("Segoe UI Semibold", 28),
                    text_color=PRIMARY,
                ).pack(pady=(12, 8))

            ctk.CTkLabel(
                placeholder,
                text="📭 Bu bölmədə məlumat yoxdur.\n\nYeni elanları görmək üçün 'Təmizlə' düyməsinə toxunun.",
                font=("Segoe UI", 15),
                text_color="#666",
                justify="center",
            ).pack(pady=(8, 12))

            # Əgər məlumat gəlirsə — placeholder silinsin
            def clear_placeholder():
                try:
                    placeholder.destroy()
                except:
                    pass

            # Tree hər dəfə yenilənəndə bu silinsin
            self.after(1000, clear_placeholder)

    # ---------- Heading overlay filterləri ----------
    def _on_heading_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "heading":
            return
        idx = int(self.tree.identify_column(event.x).replace("#", "")) - 1
        key = self.cols[idx]
        if key not in self.filterable_cols:
            return
        self._open_overlay(self.tree, key, event)

    def _bind_outside_to_close(self, overlay):
        def handler(e):
            try:
                if e.widget.winfo_toplevel() is not overlay:
                    overlay.destroy()
            except:
                pass

        self.bind_all("<Button-1>", handler, add="+")

        def cleanup(_=None):
            try:
                self.unbind_all("<Button-1>")
            except:
                pass

        overlay.bind("<Destroy>", cleanup)

    def _open_overlay(self, tree, key, event):
        if hasattr(self, "_overlay") and self._overlay.winfo_exists():
            try:
                self._overlay.destroy()
            except:
                pass

        top = ctk.CTkToplevel(self)
        self._overlay = top
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.geometry(
            "+%d+%d" % (self.winfo_rootx() + event.x, self.winfo_rooty() + event.y + 60)
        )
        top.configure(fg_color=BG)
        frame = ctk.CTkFrame(
            top, fg_color=BG, border_color=ACCENT, border_width=1, corner_radius=8
        )
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        self._bind_outside_to_close(top)

        def apply_and_close(apply_fn):
            apply_fn()
            try:
                top.destroy()
            except:
                pass

        if key in (
            "city_district",
            "metro",
            "rooms",
            "prop_type",
            "building",
            "operation",
        ):
            title_map = {
                "city_district": "Şəhər, Rayon",
                "metro": "Metro",
                "rooms": "Otaq sayı",
                "prop_type": "Əmlak növü",
                "building": "Tikili növü",
                "operation": "Əməliyyat",
            }
            ctk.CTkLabel(frame, text=title_map[key], text_color=TEXT).pack(
                anchor="w", padx=10, pady=(8, 6)
            )

            values = get_distinct_values(key)
            if key == "operation" and not values:
                values = ["Satılır", "Kirayə verilir"]
            if key == "rooms":

                def to_int(x):
                    try:
                        return int(re.sub(r"\D", "", str(x)))
                    except:
                        return 9999

                values = sorted(values, key=lambda s: to_int(s))

            holder = {
                "city_district": self.filter_city,
                "metro": self.filter_metro,
                "rooms": self.filter_rooms,
                "prop_type": self.filter_prop_type,
                "building": self.filter_building,
                "operation": self.filter_operation,
            }[key]
            vars_map = {}

            list_frame = ctk.CTkScrollableFrame(
                frame,
                width=280,
                height=260,
                fg_color=SOFT,
                border_color=ACCENT,
                border_width=1,
            )
            list_frame.pack(fill="both", expand=True, padx=10, pady=6)

            for v in values:
                var = ctk.BooleanVar(self, value=(v in holder))
                cb = ctk.CTkCheckBox(
                    list_frame, text=str(v), variable=var, fg_color=PRIMARY
                )
                cb.pack(anchor="w", pady=2)
                vars_map[v] = var

            def apply_multi():
                holder.clear()
                for v, var in vars_map.items():
                    if var.get():
                        holder.add(v)
                self.run_search()

            ctk.CTkButton(
                frame,
                text="Tətbiq et",
                fg_color=PRIMARY,
                command=lambda: apply_and_close(apply_multi),
            ).pack(padx=10, pady=8)

        elif key == "price":
            ctk.CTkLabel(frame, text="Qiymət (Min/Max)", text_color=TEXT).pack(
                anchor="w", padx=10, pady=(8, 6)
            )
            e1 = ctk.CTkEntry(frame, placeholder_text="Min", width=120)
            e1.pack(padx=10, pady=2)
            e2 = ctk.CTkEntry(frame, placeholder_text="Max", width=120)
            e2.pack(padx=10, pady=2)
            if self.filter_price_min is not None:
                e1.insert(0, str(int(self.filter_price_min)))
            if self.filter_price_max is not None:
                e2.insert(0, str(int(self.filter_price_max)))

            def apply_price():
                self.filter_price_min = _to_float(e1.get())
                self.filter_price_max = _to_float(e2.get())
                self.run_search()

            ctk.CTkButton(
                frame,
                text="Tətbiq et",
                fg_color=PRIMARY,
                command=lambda: apply_and_close(apply_price),
            ).pack(padx=10, pady=8)

        elif key == "area":
            ctk.CTkLabel(frame, text="Sahə (kvm) Min/Max", text_color=TEXT).pack(
                anchor="w", padx=10, pady=(8, 6)
            )
            e1 = ctk.CTkEntry(frame, placeholder_text="Min (kvm)", width=120)
            e1.pack(padx=10, pady=2)
            e2 = ctk.CTkEntry(frame, placeholder_text="Max (kvm)", width=120)
            e2.pack(padx=10, pady=2)
            if self.filter_area_min is not None:
                e1.insert(0, str(int(self.filter_area_min)))
            if self.filter_area_max is not None:
                e2.insert(0, str(int(self.filter_area_max)))

            def apply_area():
                self.filter_area_min = _to_float(e1.get())
                self.filter_area_max = _to_float(e2.get())
                self.run_search()

            ctk.CTkButton(
                frame,
                text="Tətbiq et",
                fg_color=PRIMARY,
                command=lambda: apply_and_close(apply_area),
            ).pack(padx=10, pady=8)

        elif key == "floor":
            ctk.CTkLabel(frame, text="Mərtəbə (Min/Max)", text_color=TEXT).pack(
                anchor="w", padx=10, pady=(8, 6)
            )
            e1 = ctk.CTkEntry(frame, placeholder_text="Min", width=120)
            e1.pack(padx=10, pady=2)
            e2 = ctk.CTkEntry(frame, placeholder_text="Max", width=120)
            e2.pack(padx=10, pady=2)
            if self.filter_floor_min is not None:
                e1.insert(0, str(int(self.filter_floor_min)))
            if self.filter_floor_max is not None:
                e2.insert(0, str(int(self.filter_floor_max)))

            def apply_floor():
                self.filter_floor_min = _to_float(e1.get())
                self.filter_floor_max = _to_float(e2.get())
                self.run_search()

            ctk.CTkButton(
                frame,
                text="Tətbiq et",
                fg_color=PRIMARY,
                command=lambda: apply_and_close(apply_floor),
            ).pack(padx=10, pady=8)


# ---------- Double click → Link və ya Detallar ----------
    def _on_row_double_click(self, event):
        """Cədvəldə sətirə 2 dəfə klik → detal pəncərəsi"""
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        vals = self.tree.item(item_id, "values")
        if not vals or len(vals) < len(self.cols):
            return

        try:
            self._open_property_details(vals)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Xəta", f"Detalları açmaq mümkün olmadı:\n{e}", parent=self)


    def _open_property_details(self, vals):
        """Elan haqqında ətraflı məlumat (modern, tablı, loqolu versiya)"""
        import webbrowser
        from tkinter import ttk
        from PIL import Image
        from customtkinter import CTkImage

        top = ctk.CTkToplevel(self)
        top.title("📄 Elan Detalları")
        top.geometry("1100x720")
        top.minsize(980, 640)
        top.attributes("-topmost", True)
        top.configure(fg_color="#f8fafc")

        # 🔗 Başlıq və link
        header = ctk.CTkFrame(top, fg_color="#e8f2ff", corner_radius=8)
        header.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(
            header,
            text="📋 Elan Məlumatı",
            font=("Segoe UI Semibold", 18),
            text_color="#0b62a4",
        ).pack(side="left", padx=16, pady=10)

        link_val = "-"
        if "source_link" in self.cols:
            link_val = vals[self.cols.index("source_link")]
        if str(link_val).startswith(("http://", "https://")):
            btn_link = ctk.CTkButton(
                header,
                text="🌐 Elanı aç",
                fg_color="#0078D4",
                text_color="white",
                command=lambda: webbrowser.open(link_val),
                width=120,
                height=36,
            )
            btn_link.pack(side="right", padx=16, pady=10)

        # --- Tabs yarat ---
        tabs = ctk.CTkTabview(top)
        tabs.pack(fill="both", expand=True, padx=16, pady=(6, 12))
        tab_info = tabs.add("📋 Əsas Məlumat")
        tab_owner = tabs.add("🏠 Sahibin digər elanları")

        # =========================
        # TAB 1 — ƏSAS MƏLUMAT
        # =========================
        body = ctk.CTkFrame(tab_info, fg_color="white", corner_radius=10)
        body.pack(fill="x", padx=6, pady=(6, 8))

        left_col = ctk.CTkFrame(body, fg_color="white")
        left_col.pack(side="left", fill="both", expand=True, padx=(12, 6), pady=8)
        right_col = ctk.CTkFrame(body, fg_color="white")
        right_col.pack(side="right", fill="both", expand=True, padx=(6, 12), pady=8)

        def val(key):
            if key not in self.cols:
                return "-"
            i = self.cols.index(key)
            return vals[i] if i < len(vals) and vals[i] not in (None, "") else "-"

        def add_row(parent, title, value):
            row = ctk.CTkFrame(parent, fg_color="#f5f7fa", corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=title, width=150, anchor="w", text_color="#333").pack(
                side="left", padx=8, pady=5
            )
            ctk.CTkLabel(
                row, text=str(value), wraplength=280, anchor="w", text_color="#111"
            ).pack(side="left", padx=4, pady=5)

        # Sol sütun
        add_row(left_col, "📅 Tarix:", val("date_read"))
        add_row(left_col, "🏠 Əmlak növü:", val("prop_type"))
        add_row(left_col, "⚙️ Əməliyyat:", val("operation"))
        add_row(left_col, "🚇 Metro:", val("metro"))
        add_row(left_col, "🛏 Otaq sayı:", val("rooms"))
        add_row(left_col, "🏢 Tikili növü:", val("building"))
        add_row(left_col, "🏬 Mərtəbə:", val("floor"))

        # Sağ sütun
        add_row(right_col, "📐 Sahə:", val("area_kvm"))
        add_row(right_col, "💰 Qiymət:", val("price"))
        add_row(right_col, "📞 Əlaqə:", val("phone"))
        add_row(right_col, "👤 Sahib:", val("contact_name"))
        add_row(right_col, "📍 Ünvan:", val("address"))
        add_row(right_col, "📜 Sənəd:", val("document"))

        # Ümumi məlumat — scrolllu sahə
        summary_frame = ctk.CTkFrame(tab_info, fg_color="white", corner_radius=10)
        summary_frame.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        ctk.CTkLabel(
            summary_frame,
            text="📝 Ümumi məlumat",
            font=("Segoe UI Semibold", 14),
            text_color="#333",
        ).pack(anchor="w", padx=12, pady=(8, 2))

        txt_summary = ctk.CTkTextbox(
            summary_frame, height=200, font=("Segoe UI", 12), wrap="word"
        )
        txt_summary.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        txt_summary.insert("1.0", str(val("summary")))
        txt_summary.configure(state="disabled")

        # =========================
        # TAB 2 — SAHİBİN DİGƏR ELANLARI
        # =========================
        owner_frame = ctk.CTkFrame(tab_owner, fg_color="white", corner_radius=10)
        owner_frame.pack(fill="both", expand=True, padx=10, pady=10)

        from tkinter import ttk
        tree = ttk.Treeview(
            owner_frame,
            columns=("Tarix", "Əməliyyat", "Qiymət", "Ünvan"),
            show="headings",
            height=10,
        )
        for c_ in ("Tarix", "Əməliyyat", "Qiymət", "Ünvan"):
            tree.heading(c_, text=c_)
            tree.column(c_, width=200 if c_ != "Ünvan" else 420)
        tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        try:
            phone = val("phone")
            rows = get_listings_by_phone(normalize_phone(phone))

            if not rows:
                # 🩵 Boş nəticə — logo göstərin
                logo_frame = ctk.CTkFrame(owner_frame, fg_color="white")
                logo_frame.place(relx=0.5, rely=0.5, anchor="center")

                try:
                    img = Image.open("besthomelogo.png")
                    logo = CTkImage(img, size=(140, 140))
                    lbl_logo = ctk.CTkLabel(logo_frame, image=logo, text="")
                    lbl_logo.image = logo
                    lbl_logo.pack(pady=10)
                except:
                    ctk.CTkLabel(
                        logo_frame,
                        text="📭 Sahibin digər elanları tapılmadı.",
                        font=("Segoe UI", 15),
                        text_color="#666",
                    ).pack(pady=10)
            else:
                for r in rows:
                    date_txt = r["date_read"] or "-"
                    if date_txt and len(str(date_txt)) >= 10:
                        date_txt = str(date_txt)[:10]
                    price_txt = "-"
                    try:
                        if r["price"] not in (None, "", "-"):
                            price_txt = f"{int(float(r['price'])):,}".replace(",", " ")
                    except:
                        price_txt = str(r["price"] or "-")
                    tree.insert(
                        "",
                        "end",
                        values=(date_txt, r["operation"], price_txt, r["address"]),
                    )

                # 🔁 2 kliklə həmin elanın linkini aç
                def on_double_click_other(ev):
                    item = tree.identify_row(ev.y)
                    if not item:
                        return
                    idx = tree.index(item)
                    if idx < len(rows):
                        # eyni telefona aid olan digər elanın məlumatlarını çəkirik
                        r = rows[idx]
                        vals_ = [
                            r["date_read"],
                            r["prop_type"],
                            r["operation"],
                            r["metro"],
                            r["rooms"],
                            r["building"],
                            r["floor"],
                            r["area_kvm"],
                            r["price"],
                            r["currency"],
                            r["phone"],
                            r["contact_name"],
                            r["address"],
                            r["document"],
                            r["summary"],
                            r["source_link"],
                        ]
                        # 🔄 yeni pəncərə kimi özünü çağır
                        self._open_property_details(vals_)

            tree.bind("<Double-1>", on_double_click_other)
        except Exception as e:
            ctk.CTkLabel(owner_frame, text=f"Xəta: {e}", text_color="red").pack(pady=20)





    def _open_details_popup(self, phone, rows):
        top = ctk.CTkToplevel(self)
        top.title(f"📄 {phone} — Elanlar")
        top.geometry("1160x680")
        top.minsize(920, 560)
        top.attributes("-topmost", True)

        # Statistik panel
        stats = phone_stats(phone)
        statbar = ctk.CTkFrame(top, fg_color=SOFT)
        statbar.pack(fill="x", padx=10, pady=(10, 0))
        trend_txt = "-"
        if stats["trend_pct"] is not None:
            arrow = "🔺" if stats["trend_pct"] >= 0 else "🔻"
            trend_txt = f"{arrow} {abs(stats['trend_pct'])}%"
        info = (
            f"İlk: {stats['first_date'] or '-'}   |   Son: {stats['last_date'] or '-'}   |   "
            f"Elan sayı: {stats['count']}   |   Orta qiymət: {int(stats['avg_price']) if stats['avg_price'] else '-'}   |   "
            f"Min/Max: {int(stats['min_price']) if stats['min_price'] else '-'} / {int(stats['max_price']) if stats['max_price'] else '-'}   |   "
            f"Trend: {trend_txt}"
        )
        ctk.CTkLabel(statbar, text=info, text_color=TEXT).pack(
            anchor="w", padx=12, pady=8
        )

        wrapper = ctk.CTkFrame(top, fg_color=BG)
        wrapper.pack(fill="both", expand=True, padx=10, pady=10)

        cols = (
            "date_read",
            "prop_type",
            "operation",
            "metro",
            "rooms",
            "building",
            "floor",
            "area_kvm",
            "price",
            "currency",
            "phone",
            "contact_name",
            "address",
            "document",
            "summary",
            "source_link",
        )
        tree = ttk.Treeview(wrapper, columns=cols, show="headings")
        vsb = ttk.Scrollbar(wrapper, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(wrapper, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        wrapper.grid_rowconfigure(0, weight=1)
        wrapper.grid_columnconfigure(0, weight=1)

        heads = {
            "date_read": "Tarix",
            "prop_type": "Növ",
            "building": "Tikili",
            "operation": "Əməliyyat",
            "city_district": "Rayon",
            "metro": "Metro",
            "rooms": "Otaq",
            "floor": "Mərtəbə",
            "area": "Sahə",
            "price": "Qiymət",
            "currency": "Valyuta",
            "address": "Ünvan",
            "document": "Sənəd",
        }
        for c, t in heads.items():
            tree.heading(c, text=t)

        def apply_popup_col_widths():
            total = max(tree.winfo_width() - 20, 900)
            ratios = {
                "date_read": 0.10,
                "prop_type": 0.10,
                "building": 0.10,
                "operation": 0.09,
                "city_district": 0.14,
                "metro": 0.10,
                "rooms": 0.07,
                "floor": 0.07,
                "area": 0.10,
                "price": 0.09,
                "currency": 0.06,
                "address": 0.18,
                "document": 0.11,
            }
            anchors = {
                "date_read": "center",
                "operation": "center",
                "rooms": "center",
                "floor": "center",
                "price": "e",
                "area": "e",
                "currency": "center",
            }
            for k in cols:
                tree.column(
                    k, width=int(total * ratios.get(k, 0.1)), anchor=anchors.get(k, "w")
                )

        def refresh_popup_table():
            tree.delete(*tree.get_children())
            for r in rows:
                date_txt = rget(r, "date_read") or rget(r, "created_at", "-")
                if date_txt and len(date_txt) >= 10:
                    date_txt = date_txt[:10]
                ak = rget(r, "area_kvm")
                asot = rget(r, "area_sot")
                area_disp = "-"
                if ak or asot:
                    area_disp = (
                        " / ".join(
                            [
                                x
                                for x in (
                                    f"{ak} kvm" if ak else "",
                                    f"{asot} sot" if asot else "",
                                )
                                if x
                            ]
                        )
                        or "-"
                    )
                price = rget(r, "price")
                cur = rget(r, "currency", "")
                ptxt = "-"
                if price not in (None, "", "-"):
                    try:
                        ptxt = f"{int(float(price)):,}".replace(",", " ")
                    except:
                        ptxt = str(price)
                tree.insert(
                    "",
                    "end",
                    values=(
                        rget(r, "date_read", "-"),
                        rget(r, "prop_type", "-"),
                        rget(r, "operation", "-"),
                        rget(r, "metro", "-"),
                        rget(r, "rooms", "-"),
                        rget(r, "building", "-"),
                        floor_display(rget(r, "floor")),
                        rget(r, "area_kvm", "-"),
                        rget(r, "price", "-"),
                        rget(r, "currency", "-"),
                        rget(r, "phone", "-"),
                        rget(r, "contact_name", "-"),
                        rget(r, "address", "-"),
                        rget(r, "document", "-"),
                        rget(r, "summary", "-"),
                        rget(r, "source_link", "-"),
                    ),
                )

        tree.bind("<Configure>", lambda _=None: apply_popup_col_widths())
        refresh_popup_table()
        apply_popup_col_widths()


    # ---------- İdxal ----------
    def import_file_with_progress(self):
        path = filedialog.askopenfilename(
            title="Excel/CSV faylı seç", filetypes=[("Excel/CSV", "*.xlsx *.xls *.csv")]
        )
        if not path:
            return
        try:
            if path.lower().endswith(".csv"):
                df = pd.read_csv(path)
            else:
                df = pd.read_excel(path)
        except Exception as e:
            messagebox.showerror("Xəta", f"Fayl oxunmadı: {e}", parent=self)
            return

        pop = ctk.CTkToplevel(self)
        pop.title("📥 Məlumat daxil edilir…")
        pop.geometry("460x180")
        pop.attributes("-topmost", True)
        ctk.CTkLabel(pop, text=f"Fayl: {Path(path).name}", text_color=TEXT).pack(
            pady=(12, 4)
        )
        bar = ctk.CTkProgressBar(pop)
        bar.pack(fill="x", padx=16, pady=10)
        bar.set(0.0)
        info = ctk.CTkLabel(pop, text="Başlanır…", text_color=TEXT)
        info.pack()

        colmap = {
            "Oxunma tarixi": "date_read",
            "Əmlakın növü": "prop_type",
            "Tikili növü": "building",
            "Əməliyyat": "operation",
            "Şəhər, Rayon": "city_district",
            "Metro": "metro",
            "Otaq sayı": "rooms",
            "Mərtəbə": "floor",
            "Sahə kvm": "area_kvm",
            "Sahə sot": "area_sot",
            "Qiymət": "price",
            "Valyuta": "currency",
            "Əlaqə nömrəsi": "phone",
            "Ad": "contact_name",
            "Ünvan": "address",
            "Sənəd": "document",
        }
        df_cols = {str(c).strip(): c for c in df.columns}
        total = len(df.index)
        done = 0
        added = 0
        dupes = 0
        areas = {}

        for _, row in df.iterrows():
            rec = {}
            for k_az, k_std in colmap.items():
                val = row.get(df_cols.get(k_az, k_az), None)
                if k_std in ("price", "area_kvm", "area_sot"):
                    rec[k_std] = _to_float(val)
                elif k_std == "phone":
                    rec[k_std] = normalize_phone(val)
                else:
                    rec[k_std] = (
                        None
                        if (pd.isna(val) or str(val).strip() == "")
                        else str(val).strip()
                    )

            ok = False
            if rec.get("phone"):
                ok = add_listing_row(rec)
                if ok:
                    added += 1
                    cd = rec.get("city_district") or "-"
                    areas[cd] = areas.get(cd, 0) + 1
                else:
                    dupes += 1

            done += 1
            pct = 0 if total == 0 else (done / max(1, total))
            bar.set(pct)
            info.configure(text=f"{done} / {total}")
            pop.update_idletasks()

        try:
            pop.destroy()
        except:
            pass

        slide = ctk.CTkToplevel(self)
        slide.overrideredirect(True)
        slide.attributes("-topmost", True)
        slide.geometry(f"420x240+{self.winfo_rootx()+40}+{self.winfo_rooty()+40}")
        wrap = ctk.CTkFrame(
            slide,
            fg_color="#F0FFF5",
            border_color="#B3EBC7",
            border_width=1,
            corner_radius=10,
        )
        wrap.pack(fill="both", expand=True, padx=2, pady=2)
        ctk.CTkLabel(
            wrap,
            text="✅ İdxal tamamlandı!",
            text_color="#167C3A",
            font=("Segoe UI Semibold", 14),
        ).pack(pady=(14, 6))
        ctk.CTkLabel(
            wrap, text=f"📦 Yeni elanlar: {added}", text_color="#167C3A"
        ).pack()
        ctk.CTkLabel(
            wrap, text=f"🔁 Mövcud (təkrarlanan): {dupes}", text_color="#167C3A"
        ).pack()
        ctk.CTkLabel(
            wrap, text=f"🏘️ Ərazi sayı: {len(areas)}", text_color="#167C3A"
        ).pack(pady=(0, 6))

        def bye(i=0):
            if i >= 100:
                try:
                    slide.destroy()
                except:
                    pass
                self._reload_cache()
                self.run_search()
                return
            slide.attributes("-alpha", 1.0)
            slide.after(50, lambda: bye(i + 1))

        bye()

    # ---------- Toast ----------
    def _toast(self, text):
        t = ctk.CTkToplevel(self)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        t.geometry(f"+{self.winfo_rootx()+20}+{self.winfo_rooty()+20}")
        f = ctk.CTkFrame(
            t,
            fg_color="#FFFBE6",
            border_color="#FFE58F",
            border_width=1,
            corner_radius=8,
        )
        f.pack(fill="both", expand=True, padx=1, pady=1)
        ctk.CTkLabel(f, text=text, text_color="#614700").pack(padx=12, pady=10)

        def close(_=None):
            try:
                t.destroy()
            except:
                pass

        t.after(2500, close)

    # ---------------- WhatsApp Tab (Build) ----------------
    def _build_whatsapp_tab(self):
        # Tabları yoxla və ya yarat
        try:
            if hasattr(self, "tabs"):
                existing = list(getattr(self.tabs, "_tab_dict", {}).keys())
                for name in ["WhatsApp Bot", "💬 WhatsApp Bot (Preview)"]:
                    if name in existing:
                        try:
                            self.tabs.delete(name)
                        except Exception:
                            pass
        except Exception:
            pass
        # 2) Yeganə düzgün tabı yarat və saxla
        if "💬 WhatsApp Bot" in getattr(self.tabs, "_tab_dict", {}):
            self.tab_bot = self.tabs.get("💬 WhatsApp Bot")
        else:
            self.tab_bot = self.tabs.add("💬 WhatsApp Bot")

        # Test üçün label əlavə et
        try:
            test_label = ctk.CTkLabel(
                self.tab_bot,
                text="💬 WhatsApp Bot tab aktivdi!",
                font=("Segoe UI", 16, "bold"),
                text_color="#25D366",
            )
            test_label.pack(pady=40)
            print("✅ Test label render olundu.")
        except Exception as e:
            print("❌ Label render xətası:", e)

        # Top-only: open WhatsApp
        top = ctk.CTkFrame(self.tab_bot, fg_color=SOFT)
        top.pack(fill="x", padx=8, pady=8)
        ctk.CTkButton(
            top, text="🌐 WhatsApp Web aç", fg_color="#25D366", command=self._wb_open
        ).pack(side="left", padx=6)

        inner = ctk.CTkTabview(self.tab_bot)
        inner.pack(fill="both", expand=True, padx=10, pady=10)
        tab_send = inner.add("Mesaj Göndər")
        tab_gen = inner.add("Generator")
        tab_black = inner.add("Qara Siyahı")

        # --- Mesaj Göndər ---
        ctk.CTkLabel(
            tab_send, text="📩 Mesaj mətni:", font=("Segoe UI", 13, "bold")
        ).pack(anchor="w", pady=(6, 2))
        self.msg_tb = ctk.CTkTextbox(tab_send, height=160, font=("Segoe UI", 12))
        self.msg_tb.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(
            tab_send,
            text="📱 Nömrələr (bir sətirdə bir):",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", pady=(6, 2))
        self.num_tb = ctk.CTkTextbox(tab_send, height=220, font=("Segoe UI", 12))
        self.num_tb.pack(fill="both", expand=True, pady=(0, 6), padx=6)

        file_bar = ctk.CTkFrame(tab_send, fg_color=SOFT)
        file_bar.pack(fill="x", padx=6, pady=(0, 6))
        ctk.CTkButton(
            file_bar, text="📂 Siyahı yüklə (.txt/.csv)", command=self._wb_load_file
        ).pack(side="left", padx=6)
        ctk.CTkButton(file_bar, text="🗑 Təmizlə", command=self._wb_clear_numbers).pack(
            side="left", padx=6
        )
        ctk.CTkButton(
            file_bar,
            text="↪️ Cədvəldən seç və əlavə et",
            command=self._wb_add_from_table,
        ).pack(side="left", padx=6)

        ctrl = ctk.CTkFrame(tab_send, fg_color=SOFT)
        ctrl.pack(fill="x", padx=6, pady=8)
        ctk.CTkLabel(ctrl, text="⏱ Gecikmə (s)").pack(side="left", padx=(6, 4))
        self.delay_ent = ctk.CTkEntry(ctrl, width=60)
        self.delay_ent.insert(0, "5")
        self.delay_ent.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(ctrl, text="Batch (ədəd)").pack(side="left", padx=(4, 4))
        self.batch_ent = ctk.CTkEntry(ctrl, width=60)
        self.batch_ent.insert(0, "10")
        self.batch_ent.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(ctrl, text="Batch fasilə (s)").pack(side="left", padx=(4, 4))
        self.batch_pause_ent = ctk.CTkEntry(ctrl, width=80)
        self.batch_pause_ent.insert(0, "10")
        self.batch_pause_ent.pack(side="left", padx=(0, 10))

        self.btn_start = ctk.CTkButton(
            ctrl, text="▶️ Başlat", fg_color="#27ae60", command=self._wb_start
        )
        self.btn_stop = ctk.CTkButton(
            ctrl, text="🛑 Dayandır", fg_color="#e74c3c", command=self._wb_stop
        )
        self.btn_start.pack(side="left", padx=8)
        self.btn_stop.pack(side="left", padx=6)

        self.lbl_status_wb = ctk.CTkLabel(
            tab_send, text="📊 Status: Hazır", text_color="#0E8F65"
        )
        self.lbl_status_wb.pack(pady=6)

        # --- Generator ---
        gen_frame = ctk.CTkFrame(tab_gen)
        gen_frame.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(gen_frame, text="🌍 Ölkə seç:", font=("Segoe UI", 12)).grid(
            row=0, column=0, sticky="w", padx=(6, 8)
        )
        self.country_opt = ctk.CTkOptionMenu(
            gen_frame, values=["Azərbaycan (+994)", "Türkiyə (+90)"]
        )
        self.country_opt.set("Azərbaycan (+994)")
        self.country_opt.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(gen_frame, text="Say:", font=("Segoe UI", 12)).grid(
            row=0, column=2, padx=(12, 4)
        )
        self.gen_count_ent = ctk.CTkEntry(gen_frame, width=80)
        self.gen_count_ent.insert(0, "100")
        self.gen_count_ent.grid(row=0, column=3)
        ctk.CTkButton(gen_frame, text="🎲 Yarat", command=self._generate_numbers).grid(
            row=0, column=4, padx=6
        )
        ctk.CTkButton(
            gen_frame,
            text="🗑 Sıfırla",
            fg_color="#e74c3c",
            command=self._clear_generator,
        ).grid(row=0, column=5, padx=6)

        self.gen_out = ctk.CTkTextbox(tab_gen, height=240)
        self.gen_out.pack(fill="x", padx=8, pady=(6, 8))
        ctk.CTkButton(
            tab_gen, text="➕ Göndəriləcək-ə əlavə et", command=self._add_gen_to_send
        ).pack(pady=4)

        # --- Qara Siyahı ---
        ctk.CTkLabel(
            tab_black, text="Qara siyahı — bu nömrələrə mesaj göndərilməyəcək"
        ).pack(anchor="w", padx=8, pady=(6, 4))
        self.black_tb = ctk.CTkTextbox(tab_black, height=320)
        self.black_tb.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        bbar = ctk.CTkFrame(tab_black, fg_color=SOFT)
        bbar.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(
            bbar, text="📥 Yüklə", command=self._wb_blacklist_load_to_text
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            bbar, text="💾 Saxla", command=self._wb_blacklist_save_from_text
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            bbar, text="🗑 Sıfırla", fg_color="#ef4444", command=self._wb_blacklist_reset
        ).pack(side="left", padx=6)

        # Preview disable if demo
        if _LICENSE_STATUS != "full":
            for w in [
                self.msg_tb,
                self.num_tb,
                self.delay_ent,
                self.batch_ent,
                self.batch_pause_ent,
                self.btn_start,
                self.btn_stop,
                self.country_opt,
                self.gen_count_ent,
                self.gen_out,
            ]:
                try:
                    w.configure(state="disabled")
                except Exception:
                    pass
            ctk.CTkLabel(
                self.tab_bot,
                text="🔒 Demo rejim: WhatsApp Bot 'preview' olaraq deaktivdir.",
                text_color="#888",
            ).pack(pady=4)

        # queue poller
        self.after(300, self._wb_poll_queue)

    # ---------------- WhatsApp UI Actions ----------------
    def _wb_open(self):
        try:
            _wb_ensure_driver()
            self.lbl_status_wb.configure(
                text="✅ WhatsApp açıldı — QR yoxdursa daxil olun"
            )
        except Exception as e:
            messagebox.showerror("Xəta", f"Driver açılmadı: {e}", parent=self)

    def _wb_load_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Text/CSV", "*.txt *.csv"), ("All", "*.*")]
        )
        if not path:
            return
        lines = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
        except Exception:
            try:
                df = pd.read_csv(path, header=None, dtype=str)
                lines = df[0].astype(str).tolist()
            except Exception as e:
                messagebox.showerror("Xəta", f"Fayl oxunmadı: {e}", parent=self)
                return
        out = []
        for ln in lines:
            s = _wb_sanitize(ln)
            if s:
                out.append(s)
        self.num_tb.delete("1.0", "end")
        self.num_tb.insert("1.0", "\n".join(out))
        self.lbl_status_wb.configure(text=f"✅ {len(out)} nömrə yükləndi")

    def _wb_clear_numbers(self):
        self.num_tb.delete("1.0", "end")
        self.lbl_status_wb.configure(text="🗑 Siyahı təmizləndi")

    def _wb_add_from_table(self):
        sel = getattr(self, "tree", None).selection() if hasattr(self, "tree") else []
        if not sel:
            messagebox.showinfo(
                "Məlumat", "Cədvəldən bir və ya bir neçə sətri seçin.", parent=self
            )
            return
        cur = [
            x.strip() for x in self.num_tb.get("1.0", "end").splitlines() if x.strip()
        ]
        for iid in sel:
            vals = self.tree.item(iid, "values")
            # phone sütununu tap
            if len(vals) >= 12:
                phone = vals[11]
            elif len(vals) >= 6:
                # fallback
                phone = vals[-3]
            else:
                phone = None
            if phone and phone not in cur:
                cur.append(str(phone))
        self.num_tb.delete("1.0", "end")
        self.num_tb.insert("1.0", "\n".join(cur))
        self.lbl_status_wb.configure(
            text=f"➕ {len(sel)} sətirdən nömrələr əlavə olundu"
        )

    def _wb_blacklist_load_to_text(self):
        s = _wb_blacklist_load_set()
        self.black_tb.delete("1.0", "end")
        self.black_tb.insert("1.0", "\n".join(sorted(s)))
        self.lbl_status_wb.configure(text=f"📥 {len(s)} qara siyahı yükləndi")

    def _wb_blacklist_save_from_text(self):
        data = [
            x.strip() for x in self.black_tb.get("1.0", "end").splitlines() if x.strip()
        ]
        sset = set()
        for d in data:
            s = _wb_sanitize(d)
            if s:
                sset.add(s)
        _wb_blacklist_save_set(sset)
        self.lbl_status_wb.configure(text=f"💾 Qara siyahı saxlandı: {len(sset)}")

    def _wb_blacklist_reset(self):
        try:
            import os

            if os.path.exists(WB_BL_FILE):
                os.remove(WB_BL_FILE)
            self.black_tb.delete("1.0", "end")
            self.lbl_status_wb.configure(text="🗑 Qara siyahı sıfırlandı")
        except Exception as e:
            messagebox.showerror("Xəta", str(e), parent=self)

    def _generate_numbers(self):
        is_az = self.country_opt.get().startswith("Azərbaycan")
        try:
            count = int(self.gen_count_ent.get().strip())
        except:
            count = 100
        res = []
        import random

        for _ in range(count):
            pref = (
                random.choice(["50", "51", "55", "60", "70", "77", "99"])
                if is_az
                else random.choice(["530", "531", "532"])
            )
            tail = "".join(random.choice("0123456789") for _ in range(7))
            res.append(("994" if is_az else "90") + pref + tail)
        self.gen_out.delete("1.0", "end")
        self.gen_out.insert("1.0", "\n".join(res))
        self.lbl_status_wb.configure(text=f"🎲 {count} nömrə yaradıldı")

    def _clear_generator(self):
        self.gen_out.delete("1.0", "end")
        self.lbl_status_wb.configure(text="🗑 Generator siyahısı təmizləndi")

    def _wb_start(self):
        if _LICENSE_STATUS != "full":
            messagebox.showinfo(
                "Demo", "Bu funksiya yalnız FULL versiyada aktivdir.", parent=self
            )
            return
        global stop_flag
        stop_flag = False
        raw_numbers = [
            x.strip() for x in self.num_tb.get("1.0", "end").splitlines() if x.strip()
        ]
        black = _wb_blacklist_load_set()
        nums = []
        for n in raw_numbers:
            s = _wb_sanitize(n)
            if s and s not in black:
                nums.append(s)
        if not nums:
            messagebox.showwarning(
                "Diqqət", "Göndəriləcək nömrə tapılmadı.", parent=self
            )
            return
        msg = self.msg_tb.get("1.0", "end").strip()
        if not msg:
            messagebox.showwarning("Diqqət", "Mesaj mətni boşdur.", parent=self)
            return
        try:
            drv = _wb_ensure_driver()
        except Exception as e:
            messagebox.showerror("Xəta", f"Driver yaradılmadı: {e}", parent=self)
            return
        try:
            delay = float(self.delay_ent.get() or 5)
        except:
            delay = 5.0
        try:
            batch_size = int(self.batch_ent.get() or 10)
        except:
            batch_size = 10
        try:
            batch_pause = float(self.batch_pause_ent.get() or 10)
        except:
            batch_pause = 10.0

        t = threading.Thread(
            target=_wb_worker,
            args=(self, drv, nums, msg, delay, batch_size, batch_pause),
            daemon=True,
        )
        t.start()
        self.lbl_status_wb.configure(text=f"▶️ Göndərmə başladıldı — {len(nums)} nömrə")

    def _wb_stop(self):
        global stop_flag
        stop_flag = True
        self.lbl_status_wb.configure(text="🛑 Dayandırma istəndi — proses dayanacaq")

    def _wb_poll_queue(self):
        try:
            while True:
                item = WB_QUEUE.get_nowait()
                t = item.get("type")
                if t == "start":
                    total = item.get("total", 0)
                    self.lbl_status_wb.configure(text=f"▶️ Başlandı — {total} nömrə")
                elif t == "sent":
                    sent = item.get("sent")
                    idx = item.get("idx")
                    num = item.get("num")
                    self.lbl_status_wb.configure(
                        text=f"✅ {sent}/{idx} göndərildi — {num}"
                    )
                elif t == "failed":
                    s = item.get("sent")
                    f = item.get("failed")
                    num = item.get("num")
                    self.lbl_status_wb.configure(
                        text=f"⚠️ Uğursuz: {num} | Uğurlu: {s} Uğursuz: {f}"
                    )
                elif t == "stopped":
                    self.lbl_status_wb.configure(
                        text=f"⛔ Dayandırıldı — Göndərildi: {item.get('sent')}  Uğursuz: {item.get('failed')}"
                    )
                elif t == "done":
                    self.lbl_status_wb.configure(
                        text=f"🎉 Bitdi — Göndərildi: {item.get('sent')}  Uğursuz: {item.get('failed')}"
                    )
        except queue.Empty:
            pass
        self.after(300, self._wb_poll_queue)

    # Mark sent number in main table 'status' column if exists
    def _mark_sent_in_table(self, phone_number: str):
        tree = getattr(self, "tree", None)
        if not tree:
            return
        for iid in tree.get_children():
            vals = tree.item(iid, "values")
            if not vals:
                continue
            # phone assumed at index 11 (per existing heads)
            try:
                phone = str(vals[11])
            except Exception:
                continue
            if phone and phone_number.endswith(phone[-9:]):  # match tail
                # rebuild values with status tick
                vals = list(vals)
                if len(vals) >= 13:
                    # add/replace last column if exists else append ✔
                    if len(vals) == 13:
                        vals[-1] = "✔"
                    else:
                        vals.append("✔")
                tree.item(iid, values=tuple(vals))
                break


# ====================== WhatsApp Helpers & Worker ======================
import os

WB_QUEUE = queue.Queue()
driver = None
stop_flag = False
WB_BL_FILE = os.path.join(os.path.expanduser("~"), ".besthome_whatsapp_blacklist.txt")


def _wb_sanitize(num: str) -> str:
    import re

    if not num:
        return None
    s = re.sub(r"[^\d+]", "", str(num))
    if s.startswith("+"):
        s = s[1:]
    if s.startswith("994") and len(s) >= 12:
        return s
    if s.startswith("0") and len(s) == 10:
        s = s[1:]
    if s.startswith(("50", "51", "55", "60", "70", "77", "99")) and len(s) == 9:
        return "994" + s
    if len(s) == 12 and s.startswith("994"):
        return s
    if len(s) == 10 and s.startswith("5"):  # TR fallback
        return "90" + s
    return None


def _wb_blacklist_load_set():
    s = set()
    try:
        if os.path.exists(WB_BL_FILE):
            with open(WB_BL_FILE, "r", encoding="utf-8") as f:
                for ln in f:
                    t = ln.strip()
                    if t:
                        s.add(t)
    except Exception as e:
        print("Blacklist load error:", e)
    return s


def _wb_blacklist_save_set(sset):
    try:
        with open(WB_BL_FILE, "w", encoding="utf-8") as f:
            for p in sorted(sset):
                f.write(p + "\n")
    except Exception as e:
        print("Blacklist save error:", e)


def _wb_ensure_driver(user_profile_dir: str = None):
    global driver
    try:
        if driver and getattr(driver, "session_id", None):
            return driver
    except Exception:
        driver = None

    opts = webdriver.ChromeOptions()
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-notifications")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    prof = None
    try:
        if user_profile_dir:
            from pathlib import Path

            prof = Path(user_profile_dir)
        else:
            from pathlib import Path

            prof = Path.home() / ".besthome_whatsapp_profile"
        prof.mkdir(parents=True, exist_ok=True)
        opts.add_argument(f"--user-data-dir={str(prof)}")
    except Exception as e:
        print("Profile dir error:", e)

    service = Service(ChromeDriverManager().install())
    drv = webdriver.Chrome(service=service, options=opts)
    drv.set_window_size(1100, 920)
    drv.get("https://web.whatsapp.com/")
    driver = drv
    return driver


def send_text(drv, phone: str, message: str):
    try:
        encoded = quote(message, safe="")
        url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded}&type=phone_number&app_absent=0"
        drv.get(url)

        # 1) Əvvəl yeni “lexical” editoru yoxla
        try:
            editor = WebDriverWait(drv, 25).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "div[contenteditable='true'][data-lexical-editor='true']",
                    )
                )
            )
        except Exception:
            # 2) Fallback: köhnə selector (bəzi hesab/dil versiyalarında bu işləyir)
            editor = WebDriverWait(drv, 25).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[contenteditable='true'][data-tab]")
                )
            )

        # 3) Mətni birbaşa editora yaz və input hadisəsi yarat
        drv.execute_script(
            """
            const el = arguments[0];
            el.innerHTML = '';
            const p = document.createElement('p');
            p.className = 'selectable-text copyable-text';
            p.dir = 'auto';
            p.innerText = arguments[1];
            el.appendChild(p);
            el.dispatchEvent(new InputEvent('input', {bubbles:true}));
            """,
            editor,
            message,
        )

        # 4) Send düyməsini kliklə (dil fərqini nəzərə alır)
        clicked = False
        try:
            send_btn = WebDriverWait(drv, 5).until(
                EC.element_to_be_clickable(
                    (
                        By.CSS_SELECTOR,
                        "span[data-icon='wds-ic-send-filled'], span[data-icon='send'], button[aria-label='Send'], button[aria-label='Göndər']",
                    )
                )
            )
            drv.execute_script("arguments[0].click();", send_btn)
            clicked = True
        except Exception:
            clicked = False

        # 5) Əgər düymə çıxmadısa: ENTER
        if not clicked:
            try:
                drv.execute_script("arguments[0].focus();", editor)
                time.sleep(0.2)
                editor.send_keys(Keys.ENTER)
            except Exception:
                try:
                    p = editor.find_element(
                        By.CSS_SELECTOR, "p.selectable-text.copyable-text"
                    )
                    p.send_keys(Keys.ENTER)
                except Exception:
                    pass

        # 6) Mesaj çıxdımı — qısa yoxlama
        try:
            WebDriverWait(drv, 6).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "div.message-out, div[data-testid='msg-outgoing'], span[data-icon='msg-check'], span[data-icon='msg-dblcheck']",
                    )
                )
            )
        except Exception:
            pass

        time.sleep(0.7)
        return True, "Göndərildi"
    except Exception as e:
        return False, f"Mesaj xətası: {e}"


def _wb_worker(self, drv, numbers, msg, delay, batch_size, batch_pause):
    global stop_flag
    sent = 0
    failed = 0
    total = len(numbers)
    WB_QUEUE.put({"type": "start", "total": total})
    batch_cnt = 0

    for idx, n in enumerate(numbers, start=1):
        if stop_flag:
            WB_QUEUE.put({"type": "stopped", "sent": sent, "failed": failed})
            break

        ok = send_text(drv, n, msg)
        if ok:
            sent += 1
            WB_QUEUE.put(
                {"type": "sent", "num": n, "sent": sent, "failed": failed, "idx": idx}
            )
        else:
            failed += 1
            WB_QUEUE.put(
                {"type": "failed", "num": n, "sent": sent, "failed": failed, "idx": idx}
            )

        batch_cnt += 1

        # 👉 Buradakı sleep, ENTER-in yanlış yerə getməsinin əsas dərmanıdır
        jitter = random.uniform(-0.15, 0.25)
        per_item_sleep = max(0.6, float(delay) + jitter)
        time.sleep(per_item_sleep)

        if batch_cnt >= batch_size:
            WB_QUEUE.put(
                {
                    "type": "status",
                    "msg": f"{batch_size} nömrədən sonra fasilə: {batch_pause} s",
                }
            )
            time.sleep(batch_pause)
            batch_cnt = 0
    else:
        WB_QUEUE.put({"type": "done", "sent": sent, "failed": failed})


# ============================================
# 🚀 Start
# ============================================
if __name__ == "__main__":
    app = App()
    app.mainloop()

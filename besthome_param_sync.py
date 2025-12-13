import threading
import datetime
import sqlite3
import time

import customtkinter as ctk
from tkcalendar import DateEntry

import estatebase_sync
from besthome_core import init_db, ensure_tables


PRIMARY = "#0078D4"
BG = "#F5F8FF"
TEXT = "#333333"


class ParamSyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BestHome Parametrlər")
        self.geometry("960x640")
        self.configure(fg_color=BG)

        ctk.set_appearance_mode("light")
        ctk.set_widget_scaling(1.0)

        init_db()
        ensure_tables()

        self._build_ui()

    def _build_ui(self):
        main_frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        header = ctk.CTkFrame(main_frame, fg_color="#FFFFFF", corner_radius=12)
        header.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            header,
            text="📊 BestHome Analitika Mərkəzi",
            font=("Segoe UI Black", 20),
            text_color=PRIMARY,
        ).pack(anchor="w", padx=16, pady=12)

        cards_frame = ctk.CTkFrame(main_frame, fg_color="#FFFFFF", corner_radius=12)
        cards_frame.pack(fill="x", pady=(0, 12))
        cards_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.stat_labels = {}

        def make_card(title, emoji, color, col):
            frame = ctk.CTkFrame(cards_frame, fg_color=color, corner_radius=10)
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
            self.stat_labels[title] = lbl

        make_card("Ümumi", "📦", "#0078D4", 0)
        make_card("Satış", "💰", "#27AE60", 1)
        make_card("Kirayə", "🏠", "#E67E22", 2)
        make_card("Dublikat", "♻️", "#C0392B", 3)

        control_frame = ctk.CTkFrame(main_frame, fg_color="#EDF2FA", corner_radius=10)
        control_frame.pack(fill="x", pady=(0, 10))
        control_frame.grid_columnconfigure((0, 2, 4), weight=0)
        control_frame.grid_columnconfigure((1, 3, 5, 6), weight=1)

        ctk.CTkLabel(control_frame, text="📅 Tarixdən:", text_color=TEXT).grid(
            row=0, column=0, padx=(12, 6), pady=12, sticky="w"
        )
        self.from_cal = DateEntry(
            control_frame,
            width=12,
            background=PRIMARY,
            foreground="white",
            date_pattern="yyyy-mm-dd",
        )
        self.from_cal.set_date(datetime.date.today() - datetime.timedelta(days=7))
        self.from_cal.grid(row=0, column=1, padx=(0, 20), pady=12, sticky="w")

        ctk.CTkLabel(control_frame, text="📅 Tarixə:", text_color=TEXT).grid(
            row=0, column=2, padx=(10, 6), pady=12, sticky="w"
        )
        self.to_cal = DateEntry(
            control_frame,
            width=12,
            background=PRIMARY,
            foreground="white",
            date_pattern="yyyy-mm-dd",
        )
        self.to_cal.set_date(datetime.date.today())
        self.to_cal.grid(row=0, column=3, padx=(0, 20), pady=12, sticky="w")

        ctk.CTkLabel(control_frame, text="📆 Son günlər (-10 və s.):", text_color=TEXT).grid(
            row=0, column=4, padx=(10, 6), pady=12, sticky="w"
        )
        self.day_entry = ctk.CTkEntry(control_frame, width=90)
        self.day_entry.insert(0, "-1")
        self.day_entry.grid(row=0, column=5, padx=(0, 12), pady=12, sticky="w")

        self.sync_button = ctk.CTkButton(
            main_frame,
            text="🔄 Serverdən məlumat çək və yenilə",
            fg_color=PRIMARY,
            hover_color="#005EA6",
            height=42,
            font=("Segoe UI Semibold", 14),
            command=self.run_sync,
        )
        self.sync_button.pack(pady=(6, 12))

        self.progress_bar = ctk.CTkProgressBar(main_frame, height=14, progress_color=PRIMARY)
        self.progress_bar.pack(fill="x", padx=10, pady=(4, 4))
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(main_frame, text="Hazır.", text_color="#666")
        self.progress_label.pack(anchor="w", padx=14, pady=(0, 10))

        detail_frame = ctk.CTkFrame(main_frame, fg_color="#FFFFFF", corner_radius=10)
        detail_frame.pack(fill="both", expand=True)
        self.detail_label = ctk.CTkLabel(
            detail_frame,
            text="📈 Ətraflı analiz hazır deyil.",
            font=("Segoe UI", 13),
            text_color="#444",
            justify="left",
        )
        self.detail_label.pack(anchor="w", padx=15, pady=15)

        self.update_statistics()

    def update_statistics(self):
        try:
            conn = sqlite3.connect("besthome.db")
            c = conn.cursor()

            c.execute("SELECT COUNT(*) FROM listings")
            total = c.fetchone()[0] or 0
            c.execute("SELECT COUNT(*) FROM listings WHERE operation LIKE '%Sat%'")
            sales = c.fetchone()[0] or 0
            c.execute("SELECT COUNT(*) FROM listings WHERE operation LIKE '%Kiray%'")
            rent = c.fetchone()[0] or 0
            c.execute(
                """
                SELECT prop_type, COUNT(*) FROM listings
                WHERE prop_type IS NOT NULL AND TRIM(prop_type) != ''
                GROUP BY prop_type ORDER BY COUNT(*) DESC LIMIT 5
                """
            )
            categories = c.fetchall()

            top_text = "🏆 Ən çox elan olan kateqoriyalar:\n"
            for i, (cat, cnt) in enumerate(categories, start=1):
                top_text += f"  {i}. {cat} — {cnt} elan\n"

            self.detail_label.configure(
                text=f"{top_text}\n🔹 Ümumi elanlar: {total}\n💰 Satış: {sales}\n🏠 Kirayə: {rent}",
                text_color="#333",
            )

            self.stat_labels["Ümumi"].configure(text=f"{total:,}")
            self.stat_labels["Satış"].configure(text=f"{sales:,}")
            self.stat_labels["Kirayə"].configure(text=f"{rent:,}")

            c.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT phone FROM listings
                    WHERE phone IS NOT NULL
                    GROUP BY phone, price, rooms, area_kvm
                    HAVING COUNT(*) > 1
                )
                """
            )
            dupes = c.fetchone()[0] or 0
            self.stat_labels["Dublikat"].configure(text=f"{dupes:,}")

            conn.close()
        except Exception as err:
            self.detail_label.configure(text=f"⚠️ Statistika xətası: {err}", text_color="#E74C3C")

    def run_sync(self):
        def worker():
            try:
                self.sync_button.configure(state="disabled")
                self.progress_label.configure(
                    text="📡 Serverdən məlumat yüklənir...",
                    text_color="#E67E22",
                )
                self.progress_bar.set(0.05)

                date_from = self.from_cal.get_date().strftime("%Y-%m-%d")
                date_to = self.to_cal.get_date().strftime("%Y-%m-%d")
                days = self.day_entry.get().strip()

                added_total = estatebase_sync.sync_with_progress(
                    date_from,
                    date_to,
                    days,
                    self.progress_bar,
                    self.progress_label,
                )
                self.update_statistics()

                self.progress_bar.set(1.0)
                self.progress_label.configure(
                    text=f"✅ Serverdən {added_total} yeni elan yükləndi.",
                    text_color="#27AE60",
                )
            except Exception as err:
                self.progress_label.configure(text=f"❌ Xəta: {err}", text_color="#E74C3C")
            finally:
                time.sleep(0.1)
                self.sync_button.configure(state="normal")

        threading.Thread(target=worker, daemon=True).start()


def main():
    app = ParamSyncApp()
    app.mainloop()


if __name__ == "__main__":
    main()

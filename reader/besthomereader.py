import argparse
import logging
import queue
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = BASE_DIR / "besthomereader.log"
PIPELINE_STEPS = [
    ("EstateBase sinxronizasiya", "estatebase_sync.py"),
    ("Arxiv hazırlanması", "auto_zip.py"),
    ("Dropbox yüklənməsi", "upload_dropbox.py"),
    ("Bot bildirişi", "notify_bot.py"),
]


def configure_file_logger():
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def run_pipeline(log_callback, status_callback):
    for idx, (step_name, script) in enumerate(PIPELINE_STEPS, start=1):
        status_callback(f"🔄 {step_name} başlayır…")
        log_callback(f"\n[{idx}/{len(PIPELINE_STEPS)}] {step_name} işə düşdü.")
        process = subprocess.Popen(
            [sys.executable, script],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in process.stdout:
            cleaned = line.strip()
            if cleaned:
                log_callback(f"{step_name}: {cleaned}")
        return_code = process.wait()
        if return_code != 0:
            status_callback(f"❌ {step_name} zamanı xəta baş verdi")
            log_callback(f"❌ {step_name} prosesində xəta (kod={return_code}).")
            return False
        status_callback(f"✅ {step_name} tamamlandı")
    return True


class ReaderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BestHome Reader")
        self.geometry("780x520")
        self.resizable(False, False)

        self.log_queue = queue.Queue()

        self._build_ui()
        self._poll_logs()

    def _build_ui(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=16, pady=(16, 8))

        self.status_label = ttk.Label(header, text="Hazır", font=("Segoe UI", 11))
        self.status_label.pack(anchor="w")

        self.progress = ttk.Progressbar(
            header, mode="determinate", maximum=len(PIPELINE_STEPS)
        )
        self.progress.pack(fill="x", pady=(8, 0))

        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=True, padx=16, pady=(12, 8))

        self.log_area = ScrolledText(
            log_frame,
            state="disabled",
            wrap="word",
            font=("Segoe UI", 10),
            height=18,
        )
        self.log_area.pack(fill="both", expand=True)

        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=16, pady=(0, 16))

        self.start_button = ttk.Button(
            footer, text="Başlat", command=self.start_pipeline
        )
        self.start_button.pack(anchor="e")

    def _poll_logs(self):
        while not self.log_queue.empty():
            message = self.log_queue.get_nowait()
            self._append_log(message)
        self.after(200, self._poll_logs)

    def _append_log(self, text):
        self.log_area.configure(state="normal")
        self.log_area.insert("end", f"{text}\n")
        self.log_area.configure(state="disabled")
        self.log_area.see("end")

    def _log(self, message):
        self.log_queue.put(message)

    def _set_status(self, message):
        self.status_label.configure(text=message)
        if message.startswith("✅") and "tamamlandı" in message and "Yenilənmə" not in message:
            self.progress.step(1)

    def start_pipeline(self):
        self.start_button.configure(state="disabled")
        self.progress.configure(value=0)
        thread = threading.Thread(target=self._run_pipeline_thread, daemon=True)
        thread.start()

    def _run_pipeline_thread(self):
        def log_callback(message):
            self._log(message)

        def status_callback(message):
            self._log(message)
            self.after(0, lambda: self._set_status(message))

        success = run_pipeline(log_callback, status_callback)
        if success:
            self.after(0, lambda: self._set_status("✅ Yenilənmə tamamlandı"))
            self._log("✅ Yenilənmə tamamlandı")
            self.after(30000, self._auto_close)
        else:
            self.after(0, lambda: self.start_button.configure(state="normal"))

    def _auto_close(self):
        if self.winfo_exists():
            self.destroy()


def run_silent():
    configure_file_logger()

    def log_callback(message):
        logging.info(message)
        print(message)

    def status_callback(message):
        logging.info(message)
        print(message)

    success = run_pipeline(log_callback, status_callback)
    if success:
        logging.info("Yenilənmə tamamlandı")
    else:
        logging.error("Yenilənmə zamanı xəta baş verdi")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--silent", action="store_true")
    args = parser.parse_args()

    if args.silent:
        run_silent()
    else:
        app = ReaderApp()
        app.mainloop()


if __name__ == "__main__":
    main()

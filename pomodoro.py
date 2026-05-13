import tkinter as tk
from tkinter import ttk
import json
import os
import sys
import subprocess
import threading
import time
from datetime import date

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pomodoro_data.json")


class DataStore:
    def __init__(self):
        self.data = self._load()

    def _load(self):
        defaults = {
            "focus_duration": 25,
            "break_duration": 5,
            "total_count": 0,
            "daily": {},
        }
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                for k, v in defaults.items():
                    if k not in loaded:
                        loaded[k] = v
                return loaded
            except (json.JSONDecodeError, IOError):
                return defaults
        return defaults

    def save(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except IOError:
            pass

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def add_completed(self):
        self.data["total_count"] += 1
        today = date.today().isoformat()
        self.data["daily"][today] = self.data["daily"].get(today, 0) + 1
        self.save()

    def get_today_count(self):
        today = date.today().isoformat()
        return self.data["daily"].get(today, 0)

    def get_total_count(self):
        return self.data["total_count"]


class PomodoroApp:
    FOCUS_COLOR = "#e74c3c"
    BREAK_COLOR = "#2ecc71"
    BG_COLOR = "#fafafa"
    TEXT_COLOR = "#2c3e50"

    def __init__(self):
        self.store = DataStore()
        self.root = tk.Tk()
        self.root.title("番茄钟")
        self.root.geometry("420x520")
        self.root.resizable(False, False)
        self.root.configure(bg=self.BG_COLOR)

        self.focus_seconds = self.store.get("focus_duration") * 60
        self.break_seconds = self.store.get("break_duration") * 60
        self.remaining = self.focus_seconds
        self.phase = "focus"  # "focus" or "break"
        self.running = False
        self.paused = False
        self.timer_id = None

        self._build_ui()
        self._update_display()
        self._update_stats()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _build_ui(self):
        # Title
        title = tk.Label(
            self.root, text="🍅 番茄钟", font=("Microsoft YaHei", 20, "bold"),
            bg=self.BG_COLOR, fg=self.TEXT_COLOR
        )
        title.pack(pady=(20, 5))

        # Phase label
        self.phase_label = tk.Label(
            self.root, text="准备开始", font=("Microsoft YaHei", 11),
            bg=self.BG_COLOR, fg="#7f8c8d"
        )
        self.phase_label.pack()

        # Timer display
        self.timer_label = tk.Label(
            self.root, text="25:00", font=("Consolas", 52, "bold"),
            bg=self.BG_COLOR, fg=self.FOCUS_COLOR
        )
        self.timer_label.pack(pady=(10, 5))

        # Progress bar
        self.progress = ttk.Progressbar(
            self.root, length=320, mode="determinate", maximum=100, value=100
        )
        self.progress.pack(pady=(0, 15))

        # Buttons frame
        btn_frame = tk.Frame(self.root, bg=self.BG_COLOR)
        btn_frame.pack(pady=(0, 10))

        btn_style = {"font": ("Microsoft YaHei", 10), "width": 7, "relief": "flat", "bd": 0}

        self.start_btn = tk.Button(
            btn_frame, text="开始", command=self.toggle_start,
            bg="#3498db", fg="white", activebackground="#2980b9", **btn_style
        )
        self.start_btn.pack(side=tk.LEFT, padx=4)

        self.reset_btn = tk.Button(
            btn_frame, text="重置", command=self.reset,
            bg="#95a5a6", fg="white", activebackground="#7f8c8d", **btn_style
        )
        self.reset_btn.pack(side=tk.LEFT, padx=4)

        self.skip_btn = tk.Button(
            btn_frame, text="跳过", command=self.skip,
            bg="#e67e22", fg="white", activebackground="#d35400", **btn_style
        )
        self.skip_btn.pack(side=tk.LEFT, padx=4)

        # Stats frame
        stats_frame = tk.LabelFrame(
            self.root, text="统计", font=("Microsoft YaHei", 10),
            bg=self.BG_COLOR, fg=self.TEXT_COLOR, padx=10, pady=5
        )
        stats_frame.pack(pady=(5, 10), ipadx=20)

        self.today_label = tk.Label(
            stats_frame, text="今日: 0", font=("Microsoft YaHei", 11),
            bg=self.BG_COLOR, fg=self.TEXT_COLOR
        )
        self.today_label.pack(side=tk.LEFT, padx=12)

        self.total_label = tk.Label(
            stats_frame, text="总计: 0", font=("Microsoft YaHei", 11),
            bg=self.BG_COLOR, fg=self.TEXT_COLOR
        )
        self.total_label.pack(side=tk.LEFT, padx=12)

        # Settings frame
        settings_frame = tk.LabelFrame(
            self.root, text="设置 (分钟)", font=("Microsoft YaHei", 10),
            bg=self.BG_COLOR, fg=self.TEXT_COLOR, padx=10, pady=5
        )
        settings_frame.pack(pady=(0, 15), ipadx=10)

        tk.Label(settings_frame, text="专注:", font=("Microsoft YaHei", 10),
                 bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(side=tk.LEFT)

        self.focus_entry = tk.Entry(
            settings_frame, font=("Microsoft YaHei", 10),
            width=4, justify="center", relief="solid", bd=1
        )
        self.focus_entry.insert(0, str(self.store.get("focus_duration")))
        self.focus_entry.pack(side=tk.LEFT, padx=(4, 12))

        tk.Label(settings_frame, text="休息:", font=("Microsoft YaHei", 10),
                 bg=self.BG_COLOR, fg=self.TEXT_COLOR).pack(side=tk.LEFT)

        self.break_entry = tk.Entry(
            settings_frame, font=("Microsoft YaHei", 10),
            width=4, justify="center", relief="solid", bd=1
        )
        self.break_entry.insert(0, str(self.store.get("break_duration")))
        self.break_entry.pack(side=tk.LEFT, padx=(4, 12))

        apply_btn = tk.Button(
            settings_frame, text="应用", command=self.apply_settings,
            font=("Microsoft YaHei", 9), width=5, relief="flat",
            bg="#3498db", fg="white", activebackground="#2980b9"
        )
        apply_btn.pack(side=tk.LEFT)

    # ── Timer logic ────────────────────────────────────────────

    def toggle_start(self):
        if not self.running:
            self.running = True
            self.paused = False
            self.start_btn.config(text="暂停", bg="#e74c3c", activebackground="#c0392b")
            self._tick()
        elif not self.paused:
            self.paused = True
            if self.timer_id:
                self.root.after_cancel(self.timer_id)
                self.timer_id = None
            self.start_btn.config(text="继续", bg="#27ae60", activebackground="#1e8449")
        else:
            self.paused = False
            self.start_btn.config(text="暂停", bg="#e74c3c", activebackground="#c0392b")
            self._tick()

    def _tick(self):
        if not self.running or self.paused:
            return
        if self.remaining <= 0:
            self._phase_done()
            return
        self.remaining -= 1
        self._update_display()
        # Reschedule: 1 tick per second
        self.timer_id = self.root.after(1000, self._tick)

    def _phase_done(self):
        self._notify()
        if self.phase == "focus":
            self.store.add_completed()
            self._update_stats()
            self.phase = "break"
            self.remaining = self.break_seconds
        else:
            self.phase = "focus"
            self.remaining = self.focus_seconds
        self._update_display()

    def reset(self):
        self.running = False
        self.paused = False
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
        self.phase = "focus"
        self.remaining = self.focus_seconds
        self.start_btn.config(text="开始", bg="#3498db", activebackground="#2980b9")
        self._update_display()

    def skip(self):
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
        self.running = False
        self.paused = False
        self.start_btn.config(text="开始", bg="#3498db", activebackground="#2980b9")
        if self.phase == "focus":
            self.phase = "break"
            self.remaining = self.break_seconds
        else:
            self.phase = "focus"
            self.remaining = self.focus_seconds
        self._update_display()

    @staticmethod
    def _beep():
        try:
            import winsound
            winsound.MessageBeep()
        except ImportError:
            pass

    def _notify(self):
        msg = "休息一下吧！" if self.phase == "focus" else "继续专注吧！"
        self._beep()
        # Windows toast via PowerShell
        threading.Thread(target=self._show_toast, args=(msg,), daemon=True).start()

    @staticmethod
    def _show_toast(msg):
        try:
            ps = (
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications,"
                " ContentType = WindowsRuntime] > $null; "
                "$template = [Windows.UI.Notifications.ToastNotificationManager]::"
                "GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText01); "
                "$textNodes = $template.GetElementsByTagName('text'); "
                "$textNodes.Item(0).AppendChild($template.CreateTextNode('番茄钟')) > $null; "
                "$toast = New-Object Windows.UI.Notifications.ToastNotification($template); "
                "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('番茄钟').Show($toast)"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True, timeout=10
            )
        except Exception:
            pass

    # ── Display ─────────────────────────────────────────────────

    def _update_display(self):
        mins, secs = divmod(self.remaining, 60)
        self.timer_label.config(text=f"{mins:02d}:{secs:02d}")

        if self.phase == "focus":
            total = self.focus_seconds
            self.timer_label.config(fg=self.FOCUS_COLOR)
            if self.running and not self.paused:
                self.phase_label.config(text="专注中")
            elif self.paused:
                self.phase_label.config(text="已暂停")
            else:
                self.phase_label.config(text="准备专注")
        else:
            total = self.break_seconds
            self.timer_label.config(fg=self.BREAK_COLOR)
            if self.running and not self.paused:
                self.phase_label.config(text="休息中")
            elif self.paused:
                self.phase_label.config(text="已暂停")
            else:
                self.phase_label.config(text="准备休息")

        pct = (self.remaining / total * 100) if total > 0 else 0
        self.progress["value"] = pct

    def _update_stats(self):
        self.today_label.config(text=f"今日: {self.store.get_today_count()}")
        self.total_label.config(text=f"总计: {self.store.get_total_count()}")

    # ── Settings ────────────────────────────────────────────────

    def apply_settings(self):
        try:
            fd = int(self.focus_entry.get())
            bd = int(self.break_entry.get())
            if fd < 1 or bd < 1 or fd > 120 or bd > 60:
                return
        except ValueError:
            return
        self.store.set("focus_duration", fd)
        self.store.set("break_duration", bd)
        self.focus_seconds = fd * 60
        self.break_seconds = bd * 60
        self.reset()

    def _on_close(self):
        self.running = False
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
        self.root.destroy()


if __name__ == "__main__":
    PomodoroApp()

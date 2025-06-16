#!/usr/bin/env python3
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import subprocess
import threading
import queue
import os
import time
import re

# --- Configuration ---
LOGS_DIRECTORY = os.path.expanduser("~/agent-zero-hacking/logs")
BROWSER_TOOL_KEYWORDS = ["browser_agent", "browser-use"]

# --- Backend Logic ---
class LogMonitorThread(threading.Thread):
    def __init__(self, target_file, parser_func, output_queue):
        super().__init__(daemon=True)
        self.target_file = target_file
        self.parser_func = parser_func
        self.output_queue = output_queue
        self.process = None
        self._stop_event = threading.Event()

    def run(self):
        try:
            self.log_message(f"Starting to monitor log file: {self.target_file}")
            # Use 'tail -f' to follow the log file in real-time
            self.process = subprocess.Popen(['tail', '-n', '0', '-f', self.target_file],
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE,
                                            text=True,
                                            bufsize=1)

            for line in iter(self.process.stdout.readline, ''):
                if self._stop_event.is_set():
                    break
                parsed_line = self.parser_func(line)
                self.log_message(parsed_line)

        except Exception as e:
            self.log_message(f"ERROR in monitor thread: {e}")
        finally:
            if self.process:
                self.process.terminate()
                self.process.wait()
            self.log_message(f"Monitoring stopped for: {self.target_file}")

    def log_message(self, message):
        self.output_queue.put(message)

    def stop(self):
        if self.process:
            self.process.terminate()
        self._stop_event.set()

def parse_log_line(line):
    # Strip potential HTML tags and whitespace for cleaner display
    clean_line = re.sub(r'<[^>]+>', '', line).strip()

    # Check for browser tool keywords
    if any(keyword in clean_line for keyword in BROWSER_TOOL_KEYWORDS):
        return f"[BROWSER ACTION] {clean_line}"

    return clean_line

# --- GUI ---
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Agent-Zero Activity Monitor")
        self.root.geometry("900x700")

        self.style = ttk.Style()
        self.style.theme_use('clam')

        self.output_queue = queue.Queue()
        self.monitor_thread = None
        self.is_monitoring = False

        self.controls_frame = ttk.LabelFrame(root, text="Controls", padding=10)
        self.controls_frame.pack(padx=10, pady=10, fill="x")

        self.start_button = ttk.Button(self.controls_frame, text="Start Monitoring", command=self.start_monitoring)
        self.start_button.pack(side="left", padx=5)

        self.stop_button = ttk.Button(self.controls_frame, text="Stop Monitoring", command=self.stop_monitoring, state="disabled")
        self.stop_button.pack(side="left", padx=5)

        self.log_frame = ttk.LabelFrame(root, text="Real-Time Activity Log", padding=10)
        self.log_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, state="disabled", height=15, bg="black", fg="#00FF00", font=("monospace", 9))
        self.log_text.pack(fill="both", expand=True)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_log_text()

    def log_message_to_gui(self, message):
        if not message: return
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def update_log_text(self):
        try:
            while True: self.log_message_to_gui(self.output_queue.get_nowait())
        except queue.Empty: pass
        self.root.after(100, self.update_log_text)

    def start_monitoring(self):
        if self.is_monitoring:
            self.log_message_to_gui("INFO: Monitoring is already active.")
            return

        try:
            # Find the most recently modified file in the logs directory
            log_files = [os.path.join(LOGS_DIRECTORY, f) for f in os.listdir(LOGS_DIRECTORY) if os.path.isfile(os.path.join(LOGS_DIRECTORY, f))]
            if not log_files:
                messagebox.showerror("Error", f"No log files found in directory:\n{LOGS_DIRECTORY}")
                return
            latest_log_file = max(log_files, key=os.path.getmtime)
        except FileNotFoundError:
            messagebox.showerror("Error", f"Log directory not found:\n{LOGS_DIRECTORY}")
            return
        except Exception as e:
            messagebox.showerror("Error", f"Could not find latest log file: {e}")
            return

        self.log_message_to_gui(f"INFO: Starting monitor on latest log file: {os.path.basename(latest_log_file)}")
        self.is_monitoring = True
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")

        self.monitor_thread = LogMonitorThread(latest_log_file, parse_log_line, self.output_queue)
        self.monitor_thread.start()

    def stop_monitoring(self):
        if not self.is_monitoring:
            self.log_message_to_gui("INFO: Monitoring is not active.")
            return

        self.log_message_to_gui("INFO: Stopping monitor...")
        if self.monitor_thread:
            self.monitor_thread.stop()
        self.monitor_thread = None
        self.is_monitoring = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")

    def on_closing(self):
        if self.is_monitoring:
            self.stop_monitoring()
        self.root.destroy()

if __name__ == "__main__":
    if not os.path.isdir(LOGS_DIRECTORY):
        print(f"ERROR: Agent-Zero log directory not found at '{LOGS_DIRECTORY}'")
        print("Please ensure Agent-Zero has been run at least once to create logs.")
    else:
        root = tk.Tk()
        app = App(root)
        root.mainloop()

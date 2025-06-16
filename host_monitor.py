#!/usr/bin/env python3
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox, ttk
import subprocess
import threading
import queue
import shlex
import os
import time
import re 

# --- Configuration ---
_ping_alert_path_config = "/home/natefoxtrot/mixkit-signal-alert-771.wav" 
_journal_alert_path_config = os.path.expanduser("~/mixkit-electric-fence-alert-2969.wav")
DEFAULT_JOURNAL_KEYWORD = "Failed password"
PING_ALERT_COOLDOWN_SECONDS = 30 

PING_ALERT_SOUND = os.path.expanduser(_ping_alert_path_config)
JOURNAL_ALERT_SOUND = os.path.expanduser(_journal_alert_path_config)

def check_sound_file(sound_path, sound_name):
    # sound_path is already expanded when PING_ALERT_SOUND/JOURNAL_ALERT_SOUND are defined
    if not os.path.exists(sound_path):
        print(f"Warning: Sound file for {sound_name} not found at {sound_path}. Audible alerts for this may not work.")
        return False
    return True

HAS_PING_SOUND = check_sound_file(PING_ALERT_SOUND, "Ping Alert")
HAS_JOURNAL_SOUND = check_sound_file(JOURNAL_ALERT_SOUND, "Journal Alert")

# --- Backend Logic ---
class MonitorThread(threading.Thread):
    def __init__(self, command, parser_func, alert_func_callable, output_queue, name):
        super().__init__(daemon=True) 
        self.command = command
        self.parser_func = parser_func
        self.alert_func_callable = alert_func_callable
        self.output_queue = output_queue
        self.name = name
        self.process = None
        self._stop_event = threading.Event()

    def run(self):
        try:
            self.log_message(f"Starting {self.name} monitor with command: {self.command}")
            cmd_list = shlex.split(self.command) 
            self.process = subprocess.Popen(cmd_list, 
                                            stdout=subprocess.PIPE, 
                                            stderr=subprocess.PIPE,
                                            text=True,
                                            bufsize=1) 

            for line in iter(self.process.stdout.readline, ''):
                if self._stop_event.is_set(): break
                parsed_event = self.parser_func(line)
                if parsed_event:
                    self.log_message(f"ALERT ({self.name}): {parsed_event}")
                    self.alert_func_callable(parsed_event, self.name)
            if self.process: # Check if process was initialized
                for line in iter(self.process.stderr.readline, ''): # Process stderr
                    if self._stop_event.is_set(): break
                    self.log_message(f"[{self.name} ERR]: {line.strip()}")
        except FileNotFoundError:
            self.log_message(f"ERROR: Command for {self.name} not found (or first part of it): {self.command.split()[0]}. Is it installed and in PATH? Sudoers configured with correct path?")
        except Exception as e:
            self.log_message(f"ERROR in {self.name} thread: {e}")
        finally:
            if self.process:
                self.process.stdout.close()
                if self.process.stderr: # Check if stderr exists before closing
                    self.process.stderr.close()
                if self.process.poll() is None: # Check if process is still running
                    self.process.terminate() 
                    try:
                        self.process.wait(timeout=2) # Wait for termination
                    except subprocess.TimeoutExpired:
                        self.process.kill() # Force kill if not terminated
                        self.log_message(f"{self.name} process had to be killed.")
            self.log_message(f"{self.name} monitor stopped.")

    def log_message(self, message): 
        self.output_queue.put(message)

    def stop(self):
        self.log_message(f"Stopping {self.name} monitor...")
        self._stop_event.set()
        if self.process and self.process.poll() is None: 
            self.process.terminate()
            try: 
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired: 
                self.process.kill()
                self.log_message(f"{self.name} process had to be killed.")
        elif self.process:
            self.process.wait()


def parse_tcpdump_ping(line):
    match = re.search(r"(\S+)\s+IP(6)?\s+([\w.:_\[\]-]+)\s+>\s+([\w.:_\[\]-]+):.*ICMP(6)?.*echo request", line)
    if match:
        timestamp = match.group(1); source_ip = match.group(3); dest_ip = match.group(4)
        protocol = "ICMPv6" if match.group(2) or match.group(5) else "ICMPv4"
        return f"{protocol} Ping detected from {source_ip} to {dest_ip} at {timestamp}"
    return None

def parse_journalctl(line, keyword):
    if keyword and keyword.lower() in line.lower():
        return f"Keyword '{keyword}' found in journal: {line.strip()}"
    return None

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Host Security Monitor")
        self.root.geometry("800x600")

        self.style = ttk.Style()
        self.style.theme_use('clam') 

        # Define custom styles for better readability in the Controls frame
        readable_font = ('DejaVu Sans', 10) 
        button_text_color = "black" 
        label_text_color = "black"  

        self.style.configure("Readable.TButton", foreground=button_text_color, font=readable_font)
        self.style.configure("Readable.TLabel", foreground=label_text_color, font=readable_font)

        self.output_queue = queue.Queue()
        self.threads = []
        self.is_monitoring = False
        
        self.journal_keyword_ref = [DEFAULT_JOURNAL_KEYWORD]

        self.last_ping_os_alert_time = 0 
        self.ping_alert_cooldown_seconds = PING_ALERT_COOLDOWN_SECONDS 

        self.controls_frame = ttk.LabelFrame(root, text="Controls", padding=10) 
        self.controls_frame.pack(padx=10, pady=10, fill="x")

        self.start_button = ttk.Button(self.controls_frame, text="Start Monitoring", command=self.start_monitoring, style="Readable.TButton")
        self.start_button.pack(side="left", padx=5)

        self.stop_button = ttk.Button(self.controls_frame, text="Stop Monitoring", command=self.stop_monitoring, state="disabled", style="Readable.TButton")
        self.stop_button.pack(side="left", padx=5)
        
        self.keyword_label = ttk.Label(self.controls_frame, text="Journal Keyword:", style="Readable.TLabel")
        self.keyword_label.pack(side="left", padx=(10,0))

        self.keyword_entry_var = tk.StringVar(value=DEFAULT_JOURNAL_KEYWORD)
        self.keyword_entry = ttk.Entry(self.controls_frame, textvariable=self.keyword_entry_var, width=20, font=readable_font)
        self.keyword_entry.pack(side="left", padx=5)

        self.keyword_button = ttk.Button(self.controls_frame, text="Update Keyword", command=self.update_journal_keyword, style="Readable.TButton")
        self.keyword_button.pack(side="left", padx=5)

        self.log_frame = ttk.LabelFrame(root, text="Event Log", padding=10)
        self.log_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, state="disabled", height=10, bg="black", fg="lightgreen", font=("monospace", 9))
        self.log_text.pack(fill="both", expand=True)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_log_text()

    def trigger_alert(self, message, source_name): 
        title = f"Suspicious Activity Detected by {source_name}!"
        do_os_alert = True 
        if "PingMonitor" in source_name:
            current_time = time.time()
            if current_time - self.last_ping_os_alert_time < self.ping_alert_cooldown_seconds:
                do_os_alert = False 
                self.log_message_to_gui(f"INFO ({source_name}): Ping detected (OS alert on cooldown) - {message.split(' at ')[0]}")
            else:
                self.last_ping_os_alert_time = current_time
        if do_os_alert:
            try: 
                subprocess.run(['notify-send', title, message, '-u', 'critical', '-i', 'dialog-warning'], check=True)
            except Exception as e: 
                self.log_message_to_gui(f"DEBUG: notify-send failed: {e}")
            sound_file_to_play = None; has_sound_flag = False 
            if "PingMonitor" in source_name and HAS_PING_SOUND: 
                sound_file_to_play = PING_ALERT_SOUND; has_sound_flag = True
            elif "JournalMonitor" in source_name and HAS_JOURNAL_SOUND: 
                sound_file_to_play = JOURNAL_ALERT_SOUND; has_sound_flag = True
            if sound_file_to_play and has_sound_flag:
                try: subprocess.run(['aplay', '-q', sound_file_to_play], check=True)
                except Exception as e: self.log_message_to_gui(f"DEBUG: aplay failed for {sound_file_to_play}: {e}")
            elif sound_file_to_play and not has_sound_flag: 
                self.log_message_to_gui(f"DEBUG: Sound file {sound_file_to_play} specified but initial check failed.")

    def update_journal_keyword(self):
        new_keyword = self.keyword_entry_var.get().strip()
        if not new_keyword: 
            messagebox.showwarning("Warning", "Journal keyword cannot be empty.")
            return
        self.journal_keyword_ref[0] = new_keyword
        self.log_message_to_gui(f"INFO: Journal keyword updated to '{new_keyword}'")

    def log_message_to_gui(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def update_log_text(self):
        try:
            while True: 
                message = self.output_queue.get_nowait()
                self.log_message_to_gui(message)
        except queue.Empty: pass
        self.root.after(100, self.update_log_text)

    def start_monitoring(self):
        if self.is_monitoring: 
            self.log_message_to_gui("INFO: Monitoring is already active.")
            return
        self.log_message_to_gui("INFO: Starting all monitors...")
        self.is_monitoring = True
        self.start_button.config(state="disabled"); self.stop_button.config(state="normal")
        self.keyword_entry.config(state="disabled"); self.keyword_button.config(state="disabled")
        net_interface = "any" 
        try:
            if os.geteuid() != 0 and net_interface == "any":
                 self.log_message_to_gui("WARNING: Monitoring 'any' interface typically requires root. tcpdump might fail.")
                 if not messagebox.askyesno("Privilege Warning", 
                                           "Monitoring 'any' interface with tcpdump usually needs root privileges. "
                                           "The tcpdump monitor might fail to start or capture packets.\n\n"
                                           "Do you want to attempt to continue?"):
                    self.stop_monitoring(); return                 
        except AttributeError: pass 
        tcpdump_filter = '(icmp and icmp[icmptype]=icmp-echo) or (icmp6 and ip6[40]=128)'
        tcpdump_command = f"sudo /usr/bin/tcpdump -i {net_interface} -l -n {tcpdump_filter}"
        journal_command = f"sudo /usr/bin/stdbuf -oL /usr/bin/journalctl -f -n 0"
        ping_thread = MonitorThread(tcpdump_command, parse_tcpdump_ping, self.trigger_alert, self.output_queue, "PingMonitor")
        journal_thread = MonitorThread(journal_command, lambda line: parse_journalctl(line, self.journal_keyword_ref[0]), self.trigger_alert, self.output_queue, "JournalMonitor")
        self.threads = [ping_thread, journal_thread]; 
        for t in self.threads: t.start()

    def stop_monitoring(self):
        if not self.is_monitoring: 
            self.log_message_to_gui("INFO: Monitoring is not active.")
            return
        self.log_message_to_gui("INFO: Stopping all monitors...") 
        for t in self.threads: t.stop()
        self.threads = []; self.is_monitoring = False
        self.start_button.config(state="normal"); self.stop_button.config(state="disabled")
        self.keyword_entry.config(state="normal"); self.keyword_button.config(state="normal")
        self.log_message_to_gui("INFO: All monitors stopped.")

    def on_closing(self):
        if self.is_monitoring:
            if messagebox.askyesno("Quit", "Monitors are running. Do you want to stop them and quit?"):
                self.stop_monitoring(); self.root.destroy()
        else: self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk(); app = App(root); root.mainloop()

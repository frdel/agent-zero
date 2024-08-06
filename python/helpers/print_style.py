import os, webcolors, html
import sys
from datetime import datetime
from . import files

class PrintStyle:
    last_endline = True
    log_file_path = None

    def __init__(self, bold=False, italic=False, underline=False, font_color="default", background_color="default", padding=False, log_only=False):
        self.bold = bold
        self.italic = italic
        self.underline = underline
        self.font_color = font_color
        self.background_color = background_color
        self.padding = padding
        self.padding_added = False  # Flag to track if padding was added
        self.log_only = log_only

        if PrintStyle.log_file_path is None:
            logs_dir = files.get_abs_path("logs")
            os.makedirs(logs_dir, exist_ok=True)
            log_filename = datetime.now().strftime("log_%Y%m%d_%H%M%S.html")
            PrintStyle.log_file_path = os.path.join(logs_dir, log_filename)
            with open(PrintStyle.log_file_path, "w") as f:
                f.write("<html><body style='background-color:black;font-family: Arial, Helvetica, sans-serif;'><pre>\n")

    def _get_rgb_color_code(self, color, is_background=False):
        try:
            if color.startswith("#") and len(color) == 7:
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
            else:
                rgb_color = webcolors.name_to_rgb(color)
                r, g, b = rgb_color.red, rgb_color.green, rgb_color.blue
            
            if is_background:
                return f"\033[48;2;{r};{g};{b}m", f"background-color: rgb({r}, {g}, {b});"
            else:
                return f"\033[38;2;{r};{g};{b}m", f"color: rgb({r}, {g}, {b});"
        except ValueError:
            return "", ""

    def _get_styled_text(self, text):
        start = ""
        end = "\033[0m"  # Reset ANSI code
        if self.bold:
            start += "\033[1m"
        if self.italic:
            start += "\033[3m"
        if self.underline:
            start += "\033[4m"
        font_color_code, _ = self._get_rgb_color_code(self.font_color)
        background_color_code, _ = self._get_rgb_color_code(self.background_color, True)
        start += font_color_code
        start += background_color_code
        return start + text + end

    def _get_html_styled_text(self, text):
        styles = []
        if self.bold:
            styles.append("font-weight: bold;")
        if self.italic:
            styles.append("font-style: italic;")
        if self.underline:
            styles.append("text-decoration: underline;")
        _, font_color_code = self._get_rgb_color_code(self.font_color)
        _, background_color_code = self._get_rgb_color_code(self.background_color, True)
        styles.append(font_color_code)
        styles.append(background_color_code)
        style_attr = " ".join(styles)
        escaped_text = html.escape(text).replace("\n", "<br>")  # Escape HTML special characters
        return f'<span style="{style_attr}">{escaped_text}</span>'

    def _add_padding_if_needed(self):
        if self.padding and not self.padding_added:
            if not self.log_only:
                print()  # Print an empty line for padding
            self._log_html("<br>")
            self.padding_added = True

    def _log_html(self, html):
        with open(PrintStyle.log_file_path, "a", encoding='utf-8') as f: # type: ignore # add encoding='utf-8'
            f.write(html)

    @staticmethod
    def _close_html_log():
        if PrintStyle.log_file_path:
            with open(PrintStyle.log_file_path, "a") as f:
                f.write("</pre></body></html>")            

    def get(self, *args, sep=' ', **kwargs):
        text = sep.join(map(str, args))
        return text, self._get_styled_text(text), self._get_html_styled_text(text)
        
    def print(self, *args, sep=' ', **kwargs):
        self._add_padding_if_needed()
        if not PrintStyle.last_endline: 
            print()
            self._log_html("<br>")
        plain_text, styled_text, html_text = self.get(*args, sep=sep, **kwargs)
        if not self.log_only:
            print(styled_text, end='\n', flush=True)
        self._log_html(html_text+"<br>\n")
        PrintStyle.last_endline = True

    def stream(self, *args, sep=' ', **kwargs):
        self._add_padding_if_needed()
        plain_text, styled_text, html_text = self.get(*args, sep=sep, **kwargs)
        if not self.log_only:
            print(styled_text, end='', flush=True)
        self._log_html(html_text)
        PrintStyle.last_endline = False

    def is_last_line_empty(self):
        lines = sys.stdin.readlines()
        return bool(lines) and not lines[-1].strip()

    @staticmethod
    def hint(text:str):
        PrintStyle(font_color="#6C3483", padding=True).print("Hint: "+text)

    @staticmethod
    def error(text:str):
        PrintStyle(font_color="red", padding=True).print("Error: "+text)

# Ensure HTML file is closed properly when the program exits
import atexit
atexit.register(PrintStyle._close_html_log)

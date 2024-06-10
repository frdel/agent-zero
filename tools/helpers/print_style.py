import webcolors

class PrintStyle:
    last_endline=True
    
    def __init__(self, bold=False, italic=False, underline=False, font_color="default", background_color="default", padding=False):
        self.bold = bold
        self.italic = italic
        self.underline = underline
        self.font_color = font_color
        self.background_color = background_color
        self.padding = padding
        self.padding_added = False  # Flag to track if padding was added

    def _get_rgb_color_code(self, color, is_background=False):
        try:
            if color.startswith("#") and len(color) == 7:
                # Convert hex color to RGB
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
            else:
                # Convert named color to RGB
                rgb_color = webcolors.name_to_rgb(color)
                r, g, b = rgb_color.red, rgb_color.green, rgb_color.blue
            
            if is_background:
                return f"\033[48;2;{r};{g};{b}m"
            else:
                return f"\033[38;2;{r};{g};{b}m"
        except ValueError:
            # Fallback to default color
            return "\033[49m" if is_background else "\033[39m"

    def _get_styled_text(self, text):
        start = ""
        end = "\033[0m"  # Reset ANSI code
        if self.bold:
            start += "\033[1m"
        if self.italic:
            start += "\033[3m"
        if self.underline:
            start += "\033[4m"
        start += self._get_rgb_color_code(self.font_color)
        start += self._get_rgb_color_code(self.background_color,True)
        return start + text + end

    def _add_padding_if_needed(self):
        if self.padding and not self.padding_added:
            print()  # Print an empty line for padding
            if not PrintStyle.last_endline: print() # add one more if last print was streamed
            self.padding_added = True
            
    def get(self, *args, sep=' ', **kwargs):
        text = sep.join(map(str, args))
        return self._get_styled_text(text)
        
    def print(self, *args, sep=' ', **kwargs):
        self._add_padding_if_needed()
        styled_text = self.get(*args, sep=sep, **kwargs)
        print(styled_text, end='\n', flush=True)
        PrintStyle.last_endline = True

    def stream(self, *args, sep=' ', **kwargs):
        self._add_padding_if_needed()
        styled_text = self.get(*args, sep=sep, **kwargs)
        print(styled_text, end='', flush=True)
        PrintStyle.last_endline = False
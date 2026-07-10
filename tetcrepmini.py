import sys
import os
import ctypes
import io
import tomllib
from pathlib import Path
from enum import Enum, auto
from pygments import highlight, lexers
from pygments.util import ClassNotFound
from pygments.lexers.special import TextLexer
from pygments.formatters import TerminalFormatter, TerminalTrueColorFormatter

if os.name == "nt":
    # Enable ANSI escape sequences in Windows Console
    kernel32 = ctypes.windll.kernel32
    ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
    STD_OUTPUT_HANDLE = -11

    handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    mode = ctypes.c_ulong()
    kernel32.GetConsoleMode(handle, ctypes.byref(mode))
    kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)

# Buffer as list of lines
lines = [""]
cursor_row, cursor_col = 0, 0
filename = None
modified = False

cached_highlight = [""]

with open(Path(__file__).parent / "tetcrepmini.toml", "rb") as f:
    cfg = tomllib.load(f)

txtlexer = TextLexer()
if not cfg.get("terminal", {}).get("col_24bit", False):
    formatter = TerminalFormatter() 
else:
    formatter = TerminalTrueColorFormatter()

def clear_screen(quick=True, file=sys.stdout):
    file.write("\x1bc")
    file.flush()

def rehighlight():
    global cached_highlight
    try:
        lexer = lexers.get_lexer_for_filename(filename)
    except ClassNotFound:
        lexer = txtlexer
    cached_highlight = highlight(
        "\n".join(lines), lexer, formatter
    ).split("\n")[:len(lines)]

def redraw():
    temp = io.StringIO()
    size = os.get_terminal_size()
    cols, rows = size.columns, size.lines
    
    clear_screen(file=temp)
    print(
        "\x1b[7m" +
        "tetcrep mini v0".ljust(cols // 2) +
        (" " if cols % 2 != 0 else "") +
        (
            ("*" if modified else "") + 
            (filename or "(untitled)")
        ).rjust(cols // 2) +
        "\x1b[0m",
        file=temp
    )
    # Print buffer
    viewport_start = max(0, cursor_row - (rows - 3))
    viewport_end = viewport_start + rows - 2
    coloured = cached_highlight
    for no, line in list(enumerate(coloured))[viewport_start:viewport_end]:
        print("\x1b[2m" + str(no+1).rjust(5) + ".\x1b[0m", line + "\x1b[0m", file=temp)
        
    temp.write(f"\x1b[{rows-1};0H")
    temp.write(
        f"\n\x1b[7mRow {cursor_row+1}, Col {cursor_col+1}"
        f" | {filename or '(untitled)'}".ljust(cols+4) + "\x1b[0m"
    )
    
    # Move cursor
    temp.write(f"\x1b[{cursor_row-viewport_start+2};{cursor_col+8}H")
    
    sys.stdout.write(temp.getvalue())
    sys.stdout.flush()

def insert_char(ch):
    global cursor_row, cursor_col
    line = lines[cursor_row]
    lines[cursor_row] = line[:cursor_col] + ch + line[cursor_col:]
    cursor_col += 1

def backspace():
    global cursor_row, cursor_col
    if cursor_col > 0:
        line = lines[cursor_row]
        lines[cursor_row] = line[:cursor_col-1] + line[cursor_col:]
        cursor_col -= 1
    elif cursor_row > 0:
        prev_len = len(lines[cursor_row-1])
        lines[cursor_row-1] += lines[cursor_row]
        del lines[cursor_row]
        cursor_row -= 1
        cursor_col = prev_len

def newline():
    global cursor_row, cursor_col
    line = lines[cursor_row]
    left, right = line[:cursor_col], line[cursor_col:]
    lines[cursor_row] = left
    lines.insert(cursor_row+1, right)
    cursor_row += 1
    cursor_col = 0

def move_left():
    global cursor_row, cursor_col
    if cursor_col > 0:
        cursor_col -= 1
    elif cursor_row > 0:
        cursor_row -= 1
        cursor_col = len(lines[cursor_row])

def move_right():
    global cursor_row, cursor_col
    if cursor_col < len(lines[cursor_row]):
        cursor_col += 1
    elif cursor_row < len(lines)-1:
        cursor_row += 1
        cursor_col = 0

def move_up():
    global cursor_row, cursor_col
    if cursor_row > 0:
        cursor_row -= 1
        cursor_col = min(cursor_col, len(lines[cursor_row]))

def move_down():
    global cursor_row, cursor_col
    if cursor_row < len(lines)-1:
        cursor_row += 1
        cursor_col = min(cursor_col, len(lines[cursor_row]))

def save_file():
    global filename
    clear_screen()
    if not filename:
        myinput = input("Save as: ").strip()
        if myinput:
            filename = myinput
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Saved as '{filename}'")
    input("Press ENTER to continue...")

def open_file():
    global lines, cursor_row, cursor_col, filename
    clear_screen()
    filename = input("Open file: ").strip()
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        if not lines:
            lines = [""]
        cursor_row, cursor_col = 0, 0
        filename = filename
        print(f"Opened '{filename}'")
    except FileNotFoundError:
        print(f"Error: '{filename}' not found!")
    input("Press ENTER to continue...")

class SpecialKey(Enum):
    LEFT = auto(); RIGHT = auto(); UP = auto();
    DOWN = auto(); DEL = auto()

class RawKeyReader:   
    if sys.platform == "win32":
        def get(self):
            import msvcrt
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):  # special key prefix
                ch2 = msvcrt.getwch()
                return {
                    "K": SpecialKey.LEFT,
                    "M": SpecialKey.RIGHT,
                    "S": SpecialKey.DEL,
                    "H": SpecialKey.UP,
                    "P": SpecialKey.DOWN,
                }.get(ch2, ch2)
            return ch
        
        def __enter__(self): 
            return self
        
        def __exit__(self, *_): pass
    else:
        def __enter__(self):
            import tty, termios
            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setraw(self.fd)
            return self
        
        def __exit__(self, *_):
            import termios
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
        
        def get(self):
            ch = sys.stdin.read(1)
            if ch == "\x1b":  # escape sequence
                seq = sys.stdin.read(2)
                key = {
                    "[D": SpecialKey.LEFT,
                    "[C": SpecialKey.RIGHT,
                    "[A": SpecialKey.UP,
                    "[B": SpecialKey.DOWN,
                    "[3": SpecialKey.DEL,
                }.get(seq, ch+seq)
                if key == SpecialKey.DEL:
                    sys.stdin.read(1)
                return key
            return ch

class NoLineWrapping:
    def __enter__(self):
        print("\x1b[=7l\x1b[?7l\x1b[7l", end="", flush=True)
    def __exit__(self, *_):
        print("\x1b[=7h\x1b[?7h\x1b[7h", end="", flush=True)

# Main loop
with NoLineWrapping():
    redraw()
    while True:
        with RawKeyReader() as reader: key = reader.get()
        if key == "\x18":  # ^X
            clear_screen()
            if modified:
                print("Are you sure you want to lose unsaved changes?")
                a = None
                while a not in {"y", "c", "s"}:
                    a = input("[Y]es, [C]ancel, [S]ave changes? ").lower()
                match a:
                    case "y":
                        pass
                    case "c":
                        redraw()
                        continue
                    case "s":
                        save_file()
            print("Bye!")
            break
        elif key in set("\r\n"):  # ENTER
            newline()
            rehighlight()
            modified = True
        elif key in set("\x08\x7f"):  # Backspace
            backspace()
            rehighlight()
            modified = True
        elif key == "\x13":  # Ctrl+S
            save_file()
            modified = False
        elif key == "\x0F":  # Ctrl+O
            open_file()
            rehighlight()
            modified = False
        elif key == SpecialKey.LEFT: move_left()
        elif key == SpecialKey.RIGHT: move_right()
        elif key == SpecialKey.UP: move_up()
        elif key == SpecialKey.DOWN: move_down()
        else:
            insert_char(key)
            rehighlight()
            modified = True
            
        redraw()
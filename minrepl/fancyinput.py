"""
A simple replacement for pyreadline. Much faster and simpler.
"""
import sys, re, os
import shutil
from enum import Enum, auto
from dataclasses import dataclass

class Special(Enum):
    """Special keys (passed to callback)."""
    LEFT = auto(); RIGHT = auto(); UP = auto();
    DOWN = auto(); DEL = auto()

@dataclass
class Verbatim:
    """Returnable by callback: replace the current input with another."""
    s: str

class _RawKeyReader:   
    if sys.platform == "win32":
        def get(self):
            import msvcrt
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):  # special key prefix
                ch2 = msvcrt.getwch()
                return {
                    "K": Special.LEFT,
                    "M": Special.RIGHT,
                    "S": Special.DEL,
                    "H": Special.UP,
                    "P": Special.DOWN,
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
                    "[D": Special.LEFT,
                    "[C": Special.RIGHT,
                    "[A": Special.UP,
                    "[B": Special.DOWN,
                    "[3": Special.DEL,
                }.get(seq, ch+seq)
                if key == Special.DEL:
                    sys.stdin.read(1)
                return key
            return ch

class _NoLineWrapping:
    def __enter__(self):
        print("\x1b[=7l\x1b[?7l\x1b[7l", end="", flush=True)
    def __exit__(self, *_):
        print("\x1b[=7h\x1b[?7h\x1b[7h", end="", flush=True)

def _printable(s):
    return len(repr(s)) <= 4

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')

def _visible_len(s):
    return len(_ANSI_RE.sub('', s))

def _ansi_wrap(s, width: int):
    lines, line, vis = [], '', 0
    i = 0
    while i < len(s):
        # check for ANSI escape
        m = _ANSI_RE.match(s, i)
        if m:
            esc = m.group(0)
            line += esc
            i += len(esc)
            continue

        # normal character
        ch = s[i]
        line += ch
        vis += 1
        i += 1

        if vis >= width:
            lines.append(line)
            line, vis = '', 0

    if line:
        lines.append(line)
    return lines
 
def _redraw(prompt, myinput, index, promptlen, displayer):
    width = shutil.get_terminal_size().columns
    avail = max(1, width - promptlen)

    # Render input into _printable form
    rendered_chars = [
        (x if len(repr(x)) <= 4 else "^" + chr(ord(x) + 64))
        for x in myinput
    ]
    displaystr = "".join(rendered_chars)

    # Compute rendered widths for cursor positioning
    widths = [1 if len(repr(x)) <= 4 else 2 for x in myinput]
    cursor_col = sum(widths[:index])
    
    # Wrap the display string
    wrapped = _ansi_wrap(displayer(displaystr), avail)

    # Figure out cursor line/col in wrapped text
    upto = "".join(rendered_chars[:index])
    wrapped_upto = _ansi_wrap(upto, avail)
    cursor_line = len(wrapped_upto) - 1
    cursor_col = len(wrapped_upto[-1]) if wrapped_upto else 0

    # Absolute positioning
    row = cursor_line
    col = cursor_col + 1
    if row <= 0:
        col += promptlen

    # Flush once
    print(f"\x1b8\x1b[J{prompt}{'\r\n'.join(wrapped)}\x1b8{f"\x1b[{row}B"
          if row > 0 else ""}\x1b[{col}G", end="", flush=True)
 
def finput(prompt="", *, callback=None, displayer=lambda s: s):
    """
    prompt is the prompt.
    
    callback is called when a key that is not ^C, CR, LF, Backspace, 
    Left Arrow, Right Arrow, or Delete is pressed. It takes the key that 
    is pressed and the current input. It must return a Verbatim object or
    string. If a string is returned, it will be inserted at the cursor 
    position. If a Verbatim object is returned, the input is replaced by 
    the specified string.
    
    displayer is a callback called to colorize the input for displaying.
    It takes one argument: the input. For example, minrepl.FancyRepl uses 
    it to syntax-highlight the input using minrepl.fygment.highlight. 
    """
    # Define data-model for an input-string with a cursor
    promptlen = len(_ANSI_RE.sub("", prompt))
    myinput = ""
    index = 0
    print(f"\x1b7{prompt}", end="", flush=True) # print prompt and save cursor
    
    with _NoLineWrapping(), _RawKeyReader() as reader:
        while True: # loop for each character
            char = reader.get() # read one key
            
            # Manage internal data-model
            if char == "\x03": # CTRL-C
                raise KeyboardInterrupt()
            elif char in set("\r\n"):
                _redraw(prompt, myinput, index, promptlen, displayer)
                print("\r\n", end="", flush=True)
                if myinput == {"nt": "\x1a"}.get(os.name, "\x04"):
                    raise EOFError()
                return myinput
            elif char in set("\x08\x7f"):
                myinput = myinput[:max(0, index - 1)] + myinput[index:]
                index = max(index - 1, 0)
            elif char == Special.LEFT:
                index = max(0, index - 1)
            elif char == Special.RIGHT:
                index = min(len(myinput), index + 1)
            elif char == Special.DEL:
                myinput = myinput[:index] + myinput[index + 1:]
            else:
                if callback:
                    callback_res = callback(char, myinput)
                    addition = (
                        char if callback_res is None else callback_res
                    )
                    if not isinstance(addition, Special):
                        if isinstance(addition, Verbatim):
                            myinput = addition.s
                            index = len(addition.s)
                        else:
                            myinput = myinput[:index] + addition + myinput[index:]
                            index += len(addition)
                elif not isinstance(char, Special):
                    myinput = myinput[:index] + char + myinput[index:]
                    index += len(char)
            
            # Print current input-string
            _redraw(prompt, myinput, index, promptlen, displayer)
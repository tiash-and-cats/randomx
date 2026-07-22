"""
A replacement for `code`.
This module provides two classes, one of which is Repl, which provides a REPL using a pure Python implementation.

>>> import minrepl
>>> minrepl.Repl().interact()
MinREPL 1, version 3.13...
>>> 

The other, FancyRepl, is just a fancier version of Repl with colours (oooh!).
"""
import codeop
import sys
import traceback
import __future__
import rlcompleter
import ast
import os
from .fancyinput import finput, Special, Verbatim
from .fygment import highlight

sys.ps1 = getattr(sys, "ps1", ">>> ")
sys.ps2 = getattr(sys, "ps2", "... ")

class _ProtectStdin:
    class Placeholder:
        def __getattr__(self, name):
            return getattr(sys.__stdin__, name)
        def close(self):
            pass  # do not close the real stdin
            
    def __enter__(self):
        self._old_stdin = sys.stdin
        sys.stdin = _ProtectStdin.Placeholder()
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdin = self._old_stdin

if not isinstance(input, type(print)): # PyREPL is annoying
    def input(prompt):
        print(prompt, end="", flush=True)
        return sys.stdin.readline()

class Repl:
    """
    This class provides a REPL. 
    
    >>> import minrepl
    >>> minrepl.Repl().interact()
    MinREPL 1, version ...
    >>> 
    
    To do something when 'exit()' is called, reassign 'exit_handler'.
    'exit_handler' can be anything; it just has to be callable.
    
    >>> import minrepl
    >>> r = minrepl.Repl()
    >>> r.exit_handler = lambda: print("Farewell.")
    >>> r.interact()
    MinREPL 1, version 3.13...
    >>> exit()
    Farewell.
    >>>
    
    To change the banner, reassign 'banner'.
    
    >>> import minrepl
    >>> r = minrepl.Repl()
    >>> r.exit_handler = lambda: print("Farewell.")
    >>> r.banner = "REPL of Spam and Eggs"
    >>> r.interact()
    REPL of Spam and Eggs
    >>> exit()
    Farewell.
    >>>
    
    To change the prompt, modify sys.ps1 and sys.ps2.
    """
    
    SIGINT = 0
    EOF = 1
    
    def __init__(self, locls=None, globs=None):
        self.exit_handler = lambda: None
        self.banner = f"MinREPL 1, version {sys.version}"
        self.globs = globs or {}
        self.locls = locls or self.globs
        self.flags = 0  # track __future__ flags
        
        self.globs["input"] = input
        self.globs["__minrepl__"] = self
        
    def is_complete(self, code):
        """Checks if the given code is complete."""
        try:
            return codeop.compile_command(code) is not None
        except (SyntaxError, OverflowError, ValueError):
            return True 
            
    def input(self, prompt):
        """
        Asks for user input, handling KeyboardInterrupt by returning
        Repl.SIGINT, and handling EOFError by returning Repl.EOF.
        """
        try:
            return input(prompt)
        except KeyboardInterrupt:
            print("\nKeyboardInterrupt")
            return self.SIGINT
        except EOFError:
            print()
            return self.EOF
            
    def _update_future_flags(self, src):
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                for alias in node.names:
                    if alias.name in __future__.all_feature_names:
                        feat = getattr(__future__, alias.name)
                        self.flags |= feat.compiler_flag
            
    def run_code(self, src):
        """Runs code in the context of the REPL."""
        self._update_future_flags(src)

        # Try as expression
        try:
            codeobj = compile(src, "<input>", "eval", self.flags, 1)
        except SyntaxError:
            codeobj = None

        if codeobj is not None:
            result = eval(codeobj, self.globs, self.locls)
        else:
            # Otherwise as statements
            codeobj = compile(src, "<input>", "exec", self.flags, 1)
            exec(codeobj, self.globs, self.locls)
            result = None
            
        sys.displayhook(result)
            
    def handle_exc(self, e):
        """Handles exceptions."""
        tb = traceback.TracebackException.from_exception(e)
        tb.stack = traceback.StackSummary([
            frame for frame in tb.stack if frame.filename != __file__
        ])
        for line in self._fmttbexc(tb):
            print(line, end="")
    
    def _fmttbexc(self, tb):
        """
        Formats a traceback.TracebackException. The default implementation
        just calls .format(). This is method for subclasses to override.
        """
        return tb.format()
        
    def _close(self):
        """
        A function to run when the REPL is closed.
        This is different from exit_handler: exit_handler is for
        users to override, while _close is for subclasses to
        override. _close is called by interact and calls
        exit_handler.
        """
        self.exit_handler()
                        
    def interact(self):
        """Starts the REPL."""
        print(self.banner)
        with _ProtectStdin():
            while True:
                code = self.input(sys.ps1)
                if code == self.SIGINT:
                    continue
                elif code == self.EOF:
                    return self._close()
                while not self.is_complete(code):
                    line = self.input(sys.ps2)
                    if line == self.SIGINT:
                        break
                    elif line == self.EOF:
                        return self.EOF
                    code += f"\n{line}"
                try:
                    self.run_code(code)
                except SystemExit:
                    return self._close()
                except BaseException as e: # BaseException is all the exceptions.
                                           # this is so that EOFError and
                                           # KeyboardInterrupt have tracebacks too. 
                                           # SystemExit is the only one that does
                                           # not need to be handled in a REPL.
                    self.handle_exc(e)

class FancyRepl(Repl):
    """
    What can I say? A fancier version of Repl, which tries to mimic the PyREPL.
    It adds colors, better history, clear/exit (without brackets) and simple 
    autocomplete. Also a good example of how to customize the Repl.
    """
    
    def __init__(self, locls=None, globs=None, history_file=None):
        super().__init__(locls, globs)
        self.completer = rlcompleter.Completer(self.locls)
        self.history_file = history_file or os.path.expanduser(
                            "~/.minrepl_history")
        if os.path.exists(self.history_file):
            with open(self.history_file) as f:
                self.history = f.read().split("\n")
        else:
            self.history = []
    
    def run_code(self, src):
        # preprocessing
        if src == "exit":
            raise SystemExit()
        elif src == "clear":
            print("\x1bc\x1b[2J\x1b[3J", end="", flush=True)
            return
            
        super().run_code(src)
    
    def input(self, prompt):
        index = -1
        
        def find_first_difference(s1, s2):
            # Iterate over pairs of characters
            for i, (char1, char2) in enumerate(zip(s1, s2)):
                if char1 != char2:
                    return i
            # If no difference found, check if one string is longer
            return min(len(s1), len(s2)) if len(s1) != len(s2) else -1
        
        def callback(char, myinput):
            nonlocal index
            if char in {Special.UP, Special.DOWN, "\x10", "\x0e"}:
                if char in {Special.UP, "\x10"}:
                    index += 1
                elif char in {Special.DOWN, "\x0e"}:
                    index -= 1
                index = max(min(index, len(self.history) - 1), 0)
                return Verbatim(self.history[-(index + 1)]) if self.history \
                       else None
            elif char == "\x0c":
                print("\x1bc\x1b[2J\x1b[3J\x1b7", end="", flush=True)
                return ""
            elif char == "\t":
                r = ""
                i = 0
                completions = []
                while r is not None:
                    r = self.completer.complete(myinput.strip(), i)
                    if r: completions.append(r)
                    i += 1
                completions = [] if completions == ["\t"] else completions
                if len(completions) > 1:
                    longlen = max(map(len, completions))
                    perline = os.get_terminal_size().columns // longlen
                    def highcomp(comp):
                        if comp.endswith("("):
                            x = highlight(comp[:-1]) + "("
                        else:
                            x = highlight(comp)
                        return x + (longlen - len(comp)) * " "
                    
                    print(f"\x1b8\x1b[1;35m{prompt}\x1b[0m{highlight(myinput)
                          }<TAB>", end="\r\n")
                    for x in range(0, len(completions), perline):
                        print(*map(highcomp, completions[x:x + perline]), 
                              end="\r\n")
                    print("\x1b7", end="", flush=True)
                    return ""
                elif len(completions) == 1:
                    return completions[0] \
                                      [find_first_difference(myinput, completions[0]):]
                elif not completions:
                    return ""
            return None
            
        try:
            x = finput(
                f"\x1b[1;35m{prompt}\x1b[0m",
                callback=callback,
                displayer=highlight
            )
            if (not self.history or x != self.history[-1]) and x:
                self.history.append(x)
            return x
        except KeyboardInterrupt:
            print("\nKeyboardInterrupt")
            return self.SIGINT
        except EOFError:
            print()
            return self.EOF
    
    def _fmttbexc(self, tb):
        return tb.format(colorize=True)
     
    def _close(self):
        super()._close()
        with open(self.history_file, "w") as f:
            f.write("\n".join(self.history))
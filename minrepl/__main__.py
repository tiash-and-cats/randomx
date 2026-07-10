import os
from . import Repl, FancyRepl

if os.environ.get("PYTHON_BASIC_REPL"):
    preferred = Repl()
else:
    preferred = FancyRepl()

if __name__ == "__main__":
    preferred.interact()
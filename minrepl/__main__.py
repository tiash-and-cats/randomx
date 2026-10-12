import os
from . import Repl, FancyRepl

if os.environ.get("PYTHON_BASIC_REPL") == "1":
    preferred = Repl()
else:
    preferred = FancyRepl()

def main():
    preferred.interact()

if __name__ == "__main__":
    main()
import sys
sys.path.append("hackergame")

import fakesh
from utils import hackerprint

print("\x1b[2mPress CTRL-C to skip intro.\x1b[0m")
try:
    hackerprint("""
\tYou are a hacker.
\tYour mission? Use your l33+ h@(]<er $]<!ll$ to break into the bank.

\tYou are in a shell. You start out in /root. There is a script ./hack.sh, which allows you to connect to the bank via some security vulnerability using -s:
\t\troot@localhost:/root$ ./hack.sh -s 124.23.76.135 # compromised IP you need to hack into

\tGood luck! You'll need it.

\t\t\t\t\tsigned, Chief Hacker
""")
except KeyboardInterrupt:
    print("\x1b[0 q", end="")
    print("\x1b[0m", end="", flush=True)
    print()
    pass

print()
if fakesh.shell() == -1:
    hackerprint("""
\tYou exited without completing your mission!
\tWell, thanks for playing, I guess.

\t\t\t\t\tsigned, Chief Hacker
""")
import time

def hackerprint(s):
    print("\x1b[1;32m", end="", flush=True)
    print("\x1b[1 q", end="", flush=True)
    for i, c in enumerate(s):
        print(c, end="", flush=True)
        time.sleep(0.07)
    print("\x1b[0 q", end="")
    print("\x1b[0m", end="", flush=True)
"""
This code has been adapted from Al Sweigart's Big Book of Small Python
Projects (https://nostarch.com/big-book-small-python-projects).
"""
import random

def main(opts):
    if not opts:
        print("leetspeakgen 1.8.2")
        while True:
            try:
                msg = input("Enter your leet message: ")
                leetspeak = to_leetspeak(msg)
                print(leetspeak)
            except (KeyboardInterrupt, EOFError):
                print("\nBye.")
                break
    elif opts and opts.get("-m"):
        print(to_leetspeak(opts["-m"]))

def to_leetspeak(msg):
    charmap = {"a": ["@", "4", "/-\\"], "c": ["("], "d": ["|)"], "e": ["3"], 
               "f": ["ph"], "h": ["]-[", "|-|"], "i": ["1", "!", "|"],
               "k": ["|<"], "o": ["0"], "s": ["$", "5"], "t": ["7", "+"],
               "u": ["|_|"], "v": ["\\/"]}
    leetspeak = ""
    for c in msg:
        if c.lower() in charmap and random.random() <= 0.7:
            possible_replacements = charmap[c.lower()]
            replacement = random.choice(possible_replacements)
            leetspeak += replacement
        else:
            leetspeak += c
    return leetspeak
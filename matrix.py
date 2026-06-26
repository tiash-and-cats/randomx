import os, sys, time, random

# Hide cursor and switch to alternate screen buffer
sys.stdout.write("\x1b[?1049h\x1b[?25l")
sys.stdout.flush()

width = os.get_terminal_size().columns
height = os.get_terminal_size().lines - 1

letters = list("QWERTYUIOPASDFGHJKLZXCVBNM01234567890!@#$%^&*()-=`[]\\;',./_+{}|:\"<>?")
drops = [0] * width

# Buffer stores intensity (0–255)
buffer = [[0 for _ in range(width)] for _ in range(height)]

def draw():
    # Fade everything
    for y in range(height):
        for x in range(width):
            buffer[y][x] = max(0, buffer[y][x] - 15)

    # Advance drops
    for x in range(width):
        y = drops[x]
        if y < height:
            buffer[y][x] = 255  # new head at full intensity
        drops[x] = y + 1
        if drops[x] >= height and random.random() > 0.95:
            drops[x] = 0

    # Render buffer
    output = "\x1b[H"
    for y in range(height):
        for x in range(width):
            intensity = buffer[y][x]
            if intensity == 255:
                # Head: white‑green
                r, g, b = 180, 255, 180
            else:
                # Trail: shades of green
                r, g, b = 0, intensity, 0
            char = random.choice(letters) if intensity > 0 else " "
            output += f"\x1b[38;2;{r};{g};{b}m{char}"
        output += "\x1b[0m\n"
    sys.stdout.write(output)
    sys.stdout.flush()

try:
    while True:
        draw()
        time.sleep(0.05)
except KeyboardInterrupt:
    pass
finally:
    sys.stdout.write("\x1b[?25h\x1b[0m\x1b[?1049l")
    sys.stdout.flush()

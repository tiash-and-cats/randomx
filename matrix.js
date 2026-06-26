const readline = require("readline");

// Hide cursor
process.stdout.write("\x1b[?1049h\x1b[?25l");

const width = process.stdout.columns;
const height = process.stdout.rows - 1;

// Characters to rain
const letters = ["1", "0"];

// Drops array
const drops = Array(width).fill(0);

// RGB buffer
const buffer = Array.from({ length: height }, () =>
  Array.from({ length: width }, () => ({ r: 0, g: 0, b: 0 }))
);

function draw() {
  // Fade everything by reducing green
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      buffer[y][x].g = Math.max(0, buffer[y][x].g - 15);
    }
  }

  // Advance drops
  for (let x = 0; x < width; x++) {
    const y = drops[x];
    const char = letters[Math.floor(Math.random() * letters.length)];
    if (y < height) {
      buffer[y][x] = { r: 0, g: 255, b: 0 }; // bright green head
    }
    drops[x] = y + 1;
    if (drops[x] >= height && Math.random() > 0.95) {
      drops[x] = 0;
    }
  }

  // Render buffer
  let output = "\x1b[H";
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const { r, g, b } = buffer[y][x];
      const char = g > 0 ? letters[Math.floor(Math.random() * letters.length)] : " ";
      output += `\x1b[38;2;${r};${g};${b}m${char}`;
    }
    output += "\x1b[0m\n";
  }
  process.stdout.write(output);
}

setInterval(draw, 50);

// Cleanup
process.on("exit", () => {
  process.stdout.write("\x1b[?25h\x1b[0m\x1b[?1049l");
});
process.on("SIGINT", () => process.exit());
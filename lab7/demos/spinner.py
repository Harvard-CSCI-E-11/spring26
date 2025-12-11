import time
import board
import neopixel

# Change A1 to A0 if that’s where your ring is plugged in
PIXEL_PIN = board.A1
NUM_PIXELS = 8

pixels = neopixel.NeoPixel(
    PIXEL_PIN,
    NUM_PIXELS,
    bpp=4,
    pixel_order=neopixel.GRBW,
)

current = 0

for i in range(NUM_PIXELS * 4):
    # Clear all pixels
    pixels.fill((0, 0, 0, 0))

    # Light the current pixel red
    pixels[current] = (255, 0, 0, 0)

    # Add a 1-pixel dim tail behind it
    pixels[(current - 1) % NUM_PIXELS] = (0, 40, 0, 0)

    pixels.show()
    time.sleep(0.08)

    # Advance to next pixel
    current = (current + 1) % NUM_PIXELS

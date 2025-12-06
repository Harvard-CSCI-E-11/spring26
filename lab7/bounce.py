"""
Display a bouncing ball
"""
import time
import displayio
import board
from adafruit_display_shapes.circle import Circle


def get_display():
    """Release any previously initialized displays and return a new display object"""
    displayio.release_displays()

    # Setup the TFT display
    spi = board.SPI()
    tft_cs = board.D9               # Chip select
    tft_dc = board.D10              # Data/command

    display_bus = displayio.FourWire(spi, command=tft_dc, chip_select=tft_cs)
    return displayio.Display(display_bus, width=240, height=135)

display = get_display()

# Create a display group
group = displayio.Group()
display.show(group)

# Ball parameters
BALL_RADIUS = 10
ball = Circle(x=20, y=20, radius=BALL_RADIUS, fill=0xFF0000)
group.append(ball)

# Ball velocity
VELOCITY_X = 2
VELOCITY_Y = 2

# Display bounds
width = display.width
height = display.height

# Main loop
while True:
    # Update ball position
    ball.x += VELOCITY_X
    ball.y += VELOCITY_Y

    # Bounce on edges
    if ball.x - BALL_RADIUS <= 0 or ball.x + BALL_RADIUS >= width:
        VELOCITY_X *= -1
    if ball.y - BALL_RADIUS <= 0 or ball.y + BALL_RADIUS >= height:
        VELOCITY_Y *= -1

    # Pause briefly to control the animation speed
    time.sleep(0.01)

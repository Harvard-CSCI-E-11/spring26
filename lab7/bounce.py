import time
import displayio
from adafruit_display_shapes.circle import Circle
import board

# Release any previously initialized displays
displayio.release_displays()

# Setup the TFT display
spi = board.SPI()
tft_cs = board.D9  # Chip select
tft_dc = board.D10  # Data/command
display_bus = displayio.FourWire(spi, command=tft_dc, chip_select=tft_cs)
display = displayio.Display(display_bus, width=240, height=135)

# Create a display group
group = displayio.Group()
display.show(group)

# Ball parameters
ball_radius = 10
ball = Circle(x=20, y=20, radius=ball_radius, fill=0xFF0000)
group.append(ball)

# Ball velocity
velocity_x = 2
velocity_y = 2

# Display bounds
width = display.width
height = display.height

# Main loop
while True:
    # Update ball position
    ball.x += velocity_x
    ball.y += velocity_y

    # Bounce on edges
    if ball.x - ball_radius <= 0 or ball.x + ball_radius >= width:
        velocity_x *= -1
    if ball.y - ball_radius <= 0 or ball.y + ball_radius >= height:
        velocity_y *= -1

    # Pause briefly to control the animation speed
    time.sleep(0.01)

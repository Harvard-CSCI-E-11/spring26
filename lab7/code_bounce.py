"""
Draw a bouncing ball.
"""

import time
import random

import displayio
import vectorio
import board
import pwmio
import digitalio

# --- Configuration ---
SCREEN_WIDTH = 240
SCREEN_HEIGHT = 240
BALL_RADIUS = 15
GRAVITY = 0.5
FRICTION = 0.995
BOUNCE_DAMPING = 0.75
STOP_THRESHOLD = 0.5

# --- Button Setup (The "Kill Switch") ---
# The Momento Shutter button is usually board.BUTTON
button = digitalio.DigitalInOut(board.BUTTON)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP

# --- Audio Setup ---
try:
    speaker = pwmio.PWMOut(board.SPEAKER, duty_cycle=0, variable_frequency=True)
except ValueError:
    speaker = None

def play_beep(freq=880, duration=0.05):
    if speaker:
        speaker.frequency = int(freq)
        speaker.duty_cycle = 32768
        time.sleep(duration)
        speaker.duty_cycle = 0

# --- Display Setup ---
display = board.DISPLAY
main_group = displayio.Group()

bg_palette = displayio.Palette(1)
bg_palette[0] = 0x000000
bg_rect = vectorio.Rectangle(pixel_shader=bg_palette,
                             width=SCREEN_WIDTH,
                             height=SCREEN_HEIGHT,
                             x=0, y=0)
main_group.append(bg_rect)

ball_palette = displayio.Palette(1)
ball_palette[0] = 0x0000FF
ball = vectorio.Circle(pixel_shader=ball_palette, radius=BALL_RADIUS, x=0, y=0)
main_group.append(ball)

# Universal display support
try:
    display.root_group = main_group
except AttributeError:
    display.show(main_group)

# --- Helper Functions ---
def flash_screen():
    """Flash the screen yellow then white."""
    bg_palette[0] = 0xFFFF00
    play_beep(freq=1500, duration=0.1)
    time.sleep(0.1)
    bg_palette[0] = 0x000000

def reset_ball():
    """Start the ball over."""
    x = random.randint(BALL_RADIUS, SCREEN_WIDTH - BALL_RADIUS)
    y = BALL_RADIUS + 10
    vx = random.uniform(-4, 4)
    vy = 0.0
    return x, y, vx, vy

def main_loop():
    """Run the program."""
    print("Running... Press Shutter Button to exit to REPL.")
    x, y, vx, vy = reset_ball()
    while True:
        # 1. CHECK FOR EXIT
        if not button.value:  # Button is pressed (Low)
            print("Exit button pressed!")
            break

        # 2. PHYSICS
        vy += GRAVITY
        vx *= FRICTION
        vy *= FRICTION
        x += vx
        y += vy

        # Walls
        if x - BALL_RADIUS < 0:
            x = BALL_RADIUS
            vx = -vx * BOUNCE_DAMPING
        elif x + BALL_RADIUS > SCREEN_WIDTH:
            x = SCREEN_WIDTH - BALL_RADIUS
            vx = -vx * BOUNCE_DAMPING

        # Floor
        if y + BALL_RADIUS >= SCREEN_HEIGHT:
            y = SCREEN_HEIGHT - BALL_RADIUS
            vy = -vy * BOUNCE_DAMPING

            if abs(vy) > 1:
                play_beep(freq=440 + int(y), duration=0.02)

            if abs(vy) < STOP_THRESHOLD and abs(y - (SCREEN_HEIGHT - BALL_RADIUS)) < 2:
                flash_screen()
                time.sleep(0.5)
                x, y, vx, vy = reset_ball()

        # 3. UPDATE GRAPHICS
        ball.x = int(x)
        ball.y = int(y)

        time.sleep(0.01)

if __name__=="__main__":
    main_loop()
    # Cleanup when loop exits
    display.root_group = displayio.CIRCUITPYTHON_TERMINAL
    print("Program stopped.")

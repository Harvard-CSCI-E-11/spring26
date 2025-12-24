# Traditional CircuitPython beep

import time
import board
import digitalio
import pwmio
from adafruit_aw9523 import AW9523

# Set up the I/O
# Pin 0 on the expander controls the speaker mute
i2c = board.I2C()
aw = AW9523(i2c)
speaker_en = aw.get_pin(0)
speaker_en.switch_to_output(value=True) # Set to True to enable sound

# Get the buzzer with a 440Hz (A4) tone
buzzer = pwmio.PWMOut(board.SPEAKER, variable_frequency=True)
buzzer.frequency = 440

# Make the buzzer beep 5 times for .25 seconds on, .5 seconds off
for _ in range(5):
    buzzer.duty_cycle = 2**15  # 50% volume
    time.sleep(0.25)           # on for .25 seconds
    buzzer.duty_cycle = 0      # Silence
    time.sleep(0.5)

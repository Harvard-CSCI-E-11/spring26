import time
import board
import displayio
import terminalio
from adafruit_display_text import label

display = board.DISPLAY
font = terminalio.FONT

# A sign is a bunch of centered labels
class Sign:
    def __init__(self):
        self.y = 0;
        self.group = displayio.Group()

    def add_line(self, text):
        tbox = label.Label(font, text=text)
        (_, _, width, height) = tbox.bounding_box
        tbox.x = display.width//2 - tbox.width//2
        tbox.y = self.y + height
        self.y = tbox.y
        self.group.append(tbox)

    def show(self):
        display.root_group = self.group

while True:
    # Determine text to display
    sign = Sign()

    now = time.localtime()
    hour = now.tm_hour % 12
    if hour == 0:
        hour = 12

    am_pm = "AM" if now.tm_hour < 12 else "PM"

    sign.add_line("TIME")
    sign.add_line("{:d}:{:02d}:{:02d} {}".format( hour, now.tm_min, now.tm_sec, am_pm ))
    sign.add_line("{:d}-{:d}-{:d}".format( now.tm_year, now.tm_mon, now.tm_mday))
    sign.show()

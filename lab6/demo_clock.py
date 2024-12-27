# SPDX-FileCopyrightText: 2024 Simson Garfinkel, based on 2019 Kattni Rembor for Adafruit Industries
# SPDX-License-Identifier: MIT
# A dirt simple clock, with no fonts.
#
# This code is super-gross, with many things repeated.
# See demo_clock2.py for a cleaned up version.
#
# Other clocks:
# https://github.com/tedivm/robs_wall_clock

import time
import board
import displayio
import terminalio
from adafruit_display_text import label

display = board.DISPLAY
font = terminalio.FONT

while True:
    # Determine text to display
    now = time.localtime()
    hour = now.tm_hour % 12
    if hour == 0:
        hour = 12

    am_pm = "AM" if now.tm_hour < 12 else "PM"

    time_display = "{:d}:{:02d}:{:02d} {}".format(
        hour, now.tm_min, now.tm_sec, am_pm
    )
    date_display = "{:d}-{:d}-{:d}".format(
        now.tm_year, now.tm_mon, now.tm_mday,
    )
    text_display = "Time"

    # Create a label for each piece of text
    clock = label.Label(font, text=time_display)
    date = label.Label(font, text=date_display)
    text = label.Label(font, text=text_display)

    (_, _, width, _) = clock.bounding_box
    clock.x = display.width // 2 - width // 2
    clock.y = 5

    (_, _, width, _) = date.bounding_box
    date.x = display.width // 2 - width // 2
    date.y = 15

    (_, _, width, _) = text.bounding_box
    text.x = display.width // 2 - width // 2
    text.y = 25

    # Add the labels to a group and display it
    watch_group = displayio.Group()
    watch_group.append(clock)
    watch_group.append(date)
    watch_group.append(text)

    display.root_group = watch_group

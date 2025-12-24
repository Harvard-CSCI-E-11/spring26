# Make the MEMENTO beep

import adafruit_pycamera

pycam = adafruit_pycamera.PyCamera()
pycam.tone(440, 0.1)

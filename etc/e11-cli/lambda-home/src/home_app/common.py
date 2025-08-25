"""
Common includes for lambda-home.
"""

import os
import os.path
import sys
import logging
from os.path import dirname, join, isdir

# fix the path. Don't know why this is necessary
MY_DIR = dirname(__file__)
sys.path.append(MY_DIR)

NESTED = join(MY_DIR, ".aws-sam", "build", "E11HomeFunction")
if isdir(join(NESTED, "e11")):
    sys.path.insert(0, NESTED)

TEMPLATE_DIR = join(MY_DIR,"templates")

LOGGER = logging.getLogger("e11.grader")
if not LOGGER.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    LOGGER.addHandler(h)
try:
    LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO"))
except ValueError:
    LOGGER.setLevel(logging.INFO)

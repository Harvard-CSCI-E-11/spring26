from pathlib import Path

COURSE_ROOT = Path("/home/ubuntu/spring26")
LAB_DIR_PATTERN = "lab{n}"         # n is 1..7
VERSION = "spring26"
# Defaults
DEFAULT_TIMEOUT_S = 5
DEFAULT_NET_TIMEOUT_S = 10
DEFAULT_RETRIES = 3
RETRY_BACKOFF_S = 0.25
CONTEXT_LINES = 3

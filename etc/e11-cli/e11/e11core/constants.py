from pathlib import Path

VERSION = "spring26"
COURSE_DOMAIN = 'csci-e-11.org'
CONFIG_FILENAME = "e11-config.ini"
COURSE_ROOT = Path("/home/ubuntu/spring26")
LAB_DIR_PATTERN = "lab{n}"         # n is 1..7
LAB_MAX=7

# Defaults
DEFAULT_TIMEOUT_S = 5
DEFAULT_NET_TIMEOUT_S = 10
DEFAULT_HTTP_TIMEOUT_S = 2
DEFAULT_RETRIES = 3
RETRY_BACKOFF_S = 0.25
CONTEXT_LINES = 3
GRADING_TIMEOUT = 30

# API Endpoints
API_ENDPOINT = f'https://{COURSE_DOMAIN}/api/v1'
STAGE_ENDPOINT = f'https://stage.{COURSE_DOMAIN}/api/v1'

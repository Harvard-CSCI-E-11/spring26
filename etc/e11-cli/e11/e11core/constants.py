from pathlib import Path

VERSION = "spring26"
COURSE_NAME = 'CSCI E-11'
COURSE_DOMAIN = 'csci-e-11.org'
COURSE_KEY_LEN = 6
CONFIG_FILENAME = "e11-config.ini"
COURSE_ROOT = Path("/home/ubuntu/spring26")
LAB_DIR_PATTERN = "lab{n}"         # n is 1..7
LAB_MAX=7
STAFF_S3_BUCKET = 'cscie-11'
SUCCESS_KEY_TEMPLATE = "success/message-{lab}"

# Defaults
DEFAULT_TIMEOUT_S = 5
DEFAULT_NET_TIMEOUT_S = 10
DEFAULT_HTTP_TIMEOUT_S = 5
DEFAULT_RETRIES = 3
RETRY_BACKOFF_S = 0.25
CONTEXT_LINES = 3
GRADING_TIMEOUT = 30
POINTS_PER_LAB = 5.0

# API Endpoints
API_ENDPOINT = f'https://{COURSE_DOMAIN}/api/v1'
STAGE_ENDPOINT = f'https://stage.{COURSE_DOMAIN}/api/v1'

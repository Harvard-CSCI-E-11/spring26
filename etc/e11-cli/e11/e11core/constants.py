from pathlib import Path

VERSION = "spring26"
COURSE_NAME = 'CSCI E-11'
COURSE_DOMAIN = 'csci-e-11.org'
COURSE_KEY_LEN = 6
CONFIG_FILENAME = "e11-config.ini"
COURSE_ROOT = Path("/home/ubuntu/spring26")
LAB_DIR_PATTERN = "lab{n}"         # n is 1..7
LAB_MAX=7
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
API_PATH = "/api/v1"
API_ENDPOINT = f'https://{COURSE_DOMAIN}{API_PATH}'
STAGE_ENDPOINT = f'https://stage.{COURSE_DOMAIN}{API_PATH}'

# HTTP Status Codes
HTTP_OK = 200
HTTP_FOUND = 302
HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_ERROR = 500

# Content Types
JPEG_MIME_TYPE = "image/jpeg"
JSON_CONTENT_TYPE = "application/json"
HTML_CONTENT_TYPE = "text/html; charset=utf-8"
PNG_CONTENT_TYPE = "image/png"
CSS_CONTENT_TYPE = "text/css; charset=utf-8"

# HTTP Headers
CORS_HEADER = "Access-Control-Allow-Origin"
CORS_WILDCARD = "*"
CONTENT_TYPE_HEADER = "Content-Type"

LOGGER = logging.getLogger("e11.grader")
if not LOGGER.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    LOGGER.addHandler(h)
try:
    LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO"))
except ValueError:
    LOGGER.setLevel(logging.INFO)

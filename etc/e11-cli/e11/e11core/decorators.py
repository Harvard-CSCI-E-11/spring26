import functools
import signal
import time

def timeout(seconds: int):
    def deco(f):
        @functools.wraps(f)
        def wrapper(*a, **k):
            def handler(signum, frame):
                raise TimeoutError(f"timed out after {seconds}s")
            old = signal.signal(signal.SIGALRM, handler)
            try:
                signal.alarm(seconds)
                return f(*a, **k)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old)
        return wrapper
    return deco

def retry(times: int=3, backoff: float=0.25):
    def deco(f):
        @functools.wraps(f)
            # noqa: C901
        def wrapper(*a, **k):
            last: Exception | None = None
            for i in range(times):
                try:
                    return f(*a, **k)
                except Exception as e:  # noqa: BLE001  pylint: disable=broad-exception-caught
                    last = e
                    if i < times - 1:
                        time.sleep(backoff * (2**i))
            assert last is not None
            raise last
        return wrapper
    return deco

"""
Module to load grading tests.
All tests for a lab reside in a single file called labx_test.py
Tests are located in csci-e-11/etc/e11-cli/e11/lab_tests/
"""

import importlib
import sys
from time import monotonic
from .assertions import TestFail
from .decorators import TimeoutError

def _import_tests_module(lab: str):
    """Given a name like 'lab1', imports 'lab1_test" from the file lab1_test.py
    """
    mod_name = f"e11.lab_tests.{lab}_test"
    return importlib.import_module(mod_name)

def discover_and_run(ctx):
    lab = ctx["lab"]  # 'lab3'
    try:
        mod = _import_tests_module(lab)
    except ModuleNotFoundError as e:
        return {"score": 0.0, "tests": [], "error": f"Test module not found: e11.lab_tests.{lab}_test"}

    # Collect into tests[] all of the functions named test_ in the given module
    tests = [(name, getattr(mod, name)) for name in dir(mod) if name.startswith("test_") and callable(getattr(mod, name))]
    passes, fails, results = [], [], []

    # Run each of the tests
    for name, fn in tests:
        t0 = monotonic()
        try:
            message = fn()
            if message is None:
                message = ""
            else:
                message = str(message)
            duration = monotonic() - t0
            results.append({"name": name, "status": "pass", "duration": duration, "message":message})
            passes.append(name)
        except TestFail as e:
            duration = monotonic() - t0
            results.append({"name": name, "status": "fail", "message": str(e), "context": e.context, "duration": duration})
            fails.append(name)
        except TimeoutError as e:
            duration = monotonic() - t0
            results.append({"name": name, "status": "fail", "message": f"Timeout: {e}", "duration": duration})
            fails.append(name)
        except Exception as e:  # noqa: BLE001
            duration = monotonic() - t0
            results.append({"name": name, "status": "fail", "message": f"Error: {e}", "duration": duration})
            fails.append(name)

    score = 5.0 * (len(passes) / len(tests)) if tests else 0.0
    # return the summary
    return {"lab": lab, "passes": passes, "fails": fails, "tests": results, "score": round(score, 2), "ctx":ctx}

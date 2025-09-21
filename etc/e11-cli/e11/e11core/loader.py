import importlib
import sys
from time import monotonic
from .assertions import TestFail
from .decorators import TimeoutError

def _import_tests_module(lab: str):
    mod_name = f"e11.lab_tests.{lab}_test"
    return importlib.import_module(mod_name)

def discover_and_run(ctx):
    lab = ctx["lab"]  # 'lab3'
    try:
        mod = _import_tests_module(lab)
    except ModuleNotFoundError as e:
        return {"score": 0.0, "tests": [], "error": f"Test module not found: e11.lab_tests.{lab}_test"}

    tests = [(name, getattr(mod, name)) for name in dir(mod) if name.startswith("test_") and callable(getattr(mod, name))]
    passes, fails, results = [], [], []

    for name, fn in tests:
        t0 = monotonic()
        try:
            fn()
            duration = monotonic() - t0
            results.append({"name": name, "status": "pass", "duration": duration})
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
    return {"lab": lab, "passes": passes, "fails": fails, "tests": results, "score": round(score, 2)}

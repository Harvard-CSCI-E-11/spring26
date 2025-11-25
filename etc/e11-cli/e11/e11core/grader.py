"""
Module to load grading tests.
All tests for a lab reside in a single file called labx_test.py
Tests are located in csci-e-11/etc/e11-cli/e11/lab_tests/
"""

import importlib
from time import monotonic
import inspect
from types import FunctionType

from .assertions import TestFail
from .testrunner import TestRunner
from .utils import get_logger,smash_email
from .e11ssh import E11Ssh

from .context import build_ctx

LOGGER = get_logger("loader")


def _import_tests_module(lab: str):
    """Given a name like 'lab1', imports 'lab1_test" from the file lab1_test.py
    """
    mod_name = f"e11.lab_tests.{lab}_test"
    return importlib.import_module(mod_name)

def _iter_test_functions_in_class(cls):
    for name, obj in cls.__dict__.items():
        # unwrap @staticmethod / @classmethod
        if isinstance(obj, (staticmethod, classmethod)):
            obj = obj.__func__
        if isinstance(obj, FunctionType) and name.startswith("test_"):
            yield f"{cls.__name__}::{name}", obj

def collect_tests_in_definition_order(mod):
    tests = []
    for name, obj in mod.__dict__.items():
        if inspect.isfunction(obj) and name.startswith("test_"):
            tests.append((name, obj))
        elif inspect.isclass(obj) and name.startswith("Test") and getattr(obj, "__test__", True):
            tests.extend(_iter_test_functions_in_class(obj))
    return tests

def discover_and_run(ctx):
    lab = ctx["lab"]  # 'lab3'
    try:
        mod = _import_tests_module(lab)
    except ModuleNotFoundError:
        return {"score": 0.0, "tests": [], "error": f"Test module not found: e11.lab_tests.{lab}_test. Please contact course admin."}

    # Create the test runner
    if ctx.get("pkey_pem",None):
        LOGGER.info("SSH will connect to %s (lab=%s)", ctx.get("public_ip"), lab)
        tr = TestRunner( ctx, ssh = E11Ssh( ctx['public_ip'], pkey_pem=ctx['pkey_pem']) )
    else:
        LOGGER.info("Tests will run locally")
        tr = TestRunner( ctx )

    # Collect into tests[] all of the functions named test_ in the given module
    # tests = [(name, getattr(mod, name)) for name in dir(mod) if name.startswith("test_") and callable(getattr(mod, name))]
    tests = collect_tests_in_definition_order(mod)
    passes, fails, results = [], [], []

    # Run each of the tests
    for name, fn in tests:
        t0 = monotonic()
        try:
            message = fn( tr )
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
        except Exception as e:  # noqa: BLE001 pylint: disable=broad-exception-caught
            duration = monotonic() - t0
            results.append({"name": name, "status": "fail", "message": f"Error: {e}", "duration": duration})
            fails.append(name)

    score = 5.0 * (len(passes) / len(tests)) if tests else 0.0
    # return the summary
    return {"lab": lab, "passes": passes, "fails": fails, "tests": results, "score": round(score, 2), "ctx":ctx, "error":False}


def grade_student_vm(user_email, public_ip, lab:str, pkey_pem:str):
    """Run grading by SSHing into the student's VM and executing tests via shared runner."""

    smashed = smash_email(user_email)

    # Build context and mark grader mode
    ctx = build_ctx(lab)
    if smashed:
        ctx["smashedemail"] = smashed
    ctx["public_ip"] = public_ip  # ensure provided IP used
    ctx["pkey_pem"]  = pkey_pem

    summary = discover_and_run(ctx)
    return summary

def create_email(summary):
    # Create email message for user
    subject = f"[E11] {summary['lab']} score {summary['score']}/5.0"
    body_lines = [subject, "", "Passes:"]
    body_lines += [f"  ✔ {n}" for n in summary["passes"]]
    if summary["fails"]:
        body_lines += ["", "Failures:"]
        for t in summary["tests"]:
            if t["status"] == "fail":
                body_lines += [f"✘ {t['name']}: {t.get('message','')}"]
                if t.get("context"):
                    body_lines += ["-- context --", (t["context"][:4000] or ""), ""]
    body = "\n".join(body_lines)
    return (subject,body)

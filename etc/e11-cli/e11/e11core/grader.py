"""
Module to load grading tests.
All tests for a lab reside in a single file called labx_test.py
Tests are located in csci-e-11/etc/e11-cli/e11/lab_tests/
"""

import json
import importlib
import traceback
import sys
from time import monotonic
import inspect
from types import FunctionType

from .assertions import TestFail
from .testrunner import TestRunner
from .utils import get_logger, smash_email, get_error_location, read_s3
from .e11ssh import E11Ssh
from .constants import COURSE_DOMAIN,POINTS_PER_LAB,STAFF_S3_BUCKET,SUCCESS_KEY_TEMPLATE

from .context import build_ctx, E11Context

LOGGER = get_logger("grader")


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

def discover_and_run(ctx: E11Context):  # pylint: disable=too-many-statements
    lab = ctx.lab  # 'lab3'
    try:
        mod = _import_tests_module(lab)
    except ModuleNotFoundError as e:
        # Convert ctx to dict for JSON serialization
        ctx_dict = {
            "version": ctx.version,
            "lab": ctx.lab,
            "labnum": ctx.labnum,
            "course_root": ctx.course_root,
            "labdir": ctx.labdir,
            "labdns": ctx.labdns,
            "course_key": ctx.course_key,
            "email": ctx.email,
            "smashedemail": ctx.smashedemail,
            "public_ip": ctx.public_ip,
            "grade_with_ssh": ctx.grade_with_ssh,
            "pkey_pem": "<censored>" if ctx.pkey_pem else None,
            "key_filename": ctx.key_filename,
        }
        return {"score": 0.0,
                "tests": [],
                "error": f"Test module not found: e11.lab_tests.{lab}_test. {e} Please contact course admin.",
                "ctx": ctx_dict}

    # Create the test runner
    if ctx.grade_with_ssh:
        LOGGER.info("SSH will connect to %s (lab=%s)", ctx.public_ip, lab)
        tr = TestRunner( ctx, ssh = E11Ssh( ctx.public_ip,
                                            key_filename=ctx.key_filename,
                                            pkey_pem=ctx.pkey_pem))
    else:
        LOGGER.info("Tests will run locally")
        tr = TestRunner( ctx )

    # Collect into tests[] all of the functions named test_ in the given module
    # tests = [(name, getattr(mod, name)) for name in dir(mod) if name.startswith("test_") and callable(getattr(mod, name))]
    tests = collect_tests_in_definition_order(mod)
    passes, fails, results = [], [], []

    # Run each of the tests
    for name, fn in tests:
        LOGGER.debug("name=%s fn=%s",name,fn)
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

            # Get traceback information for detailed logging
            exc_type, exc_value, exc_traceback = sys.exc_info()
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            tb_str = "".join(tb_lines)

            # Find the line number and file where the error occurred
            filename, line_no = get_error_location(exc_traceback)

            # Log detailed error information
            error_details = f"Test: {name}, Error: {e}, File: {filename}, Line: {line_no}"
            LOGGER.error("Test failed with exception: %s\nTraceback:\n%s", error_details, tb_str)

            # Build detailed error message for user
            error_msg = f"Error: {e}"
            if filename != "unknown" and line_no != "unknown":
                error_msg += f" (at {filename}:{line_no})"

            results.append({"name": name, "status": "fail", "message": error_msg, "duration": duration})
            fails.append(name)

    score = POINTS_PER_LAB * (len(passes) / len(tests)) if tests else 0.0
    # Convert ctx to dict for JSON serialization
    ctx_dict = {
        "version": ctx.version,
        "lab": ctx.lab,
        "labnum": ctx.labnum,
        "course_root": ctx.course_root,
        "labdir": ctx.labdir,
        "labdns": ctx.labdns,
        "course_key": ctx.course_key,
        "email": ctx.email,
        "smashedemail": ctx.smashedemail,
        "public_ip": ctx.public_ip,
        "grade_with_ssh": ctx.grade_with_ssh,
        "pkey_pem": "<censored>" if ctx.pkey_pem else None,
        "key_filename": ctx.key_filename,
    }
    # If the student get a perfect, get the success message
    message = ""
    if len(passes) == len(tests):
        try:
            message = read_s3(STAFF_S3_BUCKET, SUCCESS_KEY_TEMPLATE.format(lab=ctx.lab))
        except FileNotFoundError as e:
            message = str(e)

    # Add any extra fields using get() to access dynamic fields
    # We can't easily enumerate _extra without accessing it directly,
    # so we'll just include the known fields above
    # return the summary
    return {"lab": lab,
            "passes": passes,
            "fails": fails,
            "tests": results,
            "score": round(score, 2),
            "message" : message,
            "ctx": ctx_dict,
            "error": False}


def grade_student_vm(user_email, public_ip, lab:str, pkey_pem:str|None=None, key_filename:str|None=None):
    """Run grading by SSHing into the student's VM and executing tests via shared runner."""

    smashed = smash_email(user_email)

    # Build context and mark grader mode
    ctx = build_ctx(lab)
    if smashed:
        ctx.smashedemail = smashed
        # Set labdns based on smashed email for grading
        ctx.labdns = f"{smashed}-{lab}.{COURSE_DOMAIN}"
    ctx.public_ip = public_ip
    ctx.pkey_pem = pkey_pem
    ctx.key_filename = key_filename
    ctx.grade_with_ssh = True
    summary = discover_and_run(ctx)
    ctx.pkey_pem = "<censored>"
    return summary

def print_summary(summary, verbose=False):
    if verbose:
        print(json.dumps(summary,default=str,indent=4))

    lab = summary.get("lab")
    print(f"=== {lab} Results ===")
    ctx = summary['ctx']
    public_ip = ctx.public_ip if hasattr(ctx, 'public_ip') else ctx.get('public_ip', 'unknown')
    print(f"Testing public ip address: {public_ip}")
    print(f"Score: {summary['score']} / 5.0")
    if summary["passes"]:
        print("\n-- PASSES --")
        for t in summary["tests"]:
            if t["status"] == "pass":
                print(f"  ✔ {t['name']:20}  -- {t.get('message','')}  ")
    if summary["fails"]:
        print("\n-- FAILURES --")
        for t in summary["tests"]:
            if t["status"] == "fail":
                print(f"  ✘ {t['name']:20}: {t.get('message','')}")
                ctx = t.get("context")
                if ctx:
                    print("----- context -----")
                    print(ctx)
    if verbose and summary["passes"]:
        print("\n-- PASS ARTIFACTS (verbose) --")
        for t in summary["tests"]:
            if t["status"] == "pass" and "context" in t and t["context"]:
                print(f"\n✓ {t['name']}")
                print(t["context"])

    if summary['message']:
        print(summary['message'])


def create_email(summary):
    """Create email message for user. See also print_summary above"""

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
    if summary['message']:
        body_lines += summary['message']
    body = "\n".join(body_lines)
    return (subject,body)

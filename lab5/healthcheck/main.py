"""
CSCI E-11 healthcheck test regime
(C) Simson Garfinkel 2025
with significant help from ChatGpT 4o
"""


import pkgutil
import importlib
import sys
import traceback
from healthcheck.testlib import registry

def load_all_tests():
    import healthcheck.checks
    package = healthcheck.checks
    for _, name, ispkg in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        if not ispkg:
            importlib.import_module(name)

def run_tests():
    load_all_tests()
    print("\nRunning Health Checks...\n")
    failures = []
    status_messages = []
    for test in registry:
        meta = test._metadata
        name = meta['name']
        desc = meta['description']
        print(f"{name:<50} ... ", end="")
        try:
            result = test()
            print("✅ PASS")
            if result:
                status_messages.append((name, str(result)))
        except Exception:  # pylint: disable=broad-exception-caught
            print("❌ FAIL")
            failures.append((name, desc, traceback.format_exc()))

    if status_messages:
        print("\nAdditional Status Info:\n")
        for name, msg in status_messages:
            print(f"{name}:\n  {msg}")

    if failures:
        print("\nFailures:\n")
        for name, desc, tb in failures:
            print(f"{name}: {desc}\n{tb}")
        sys.exit(1)
    else:
        print("\nAll tests passed.\n")

if __name__ == "__main__":
    run_tests()

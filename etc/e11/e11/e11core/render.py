from .constants import CONTEXT_LINES

def print_summary(summary, verbose=False):
    lab = summary.get("lab")
    print(f"=== {lab} Results ===")
    print(f"Score: {summary['score']} / 5.0")
    if summary["passes"]:
        print("\n-- PASSES --")
        for n in summary["passes"]:
            print(f"  ✔ {n}")
    if summary["fails"]:
        print("\n-- FAILURES --")
        for t in summary["tests"]:
            if t["status"] == "fail":
                print(f"\n✘ {t['name']}: {t.get('message','')}")
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

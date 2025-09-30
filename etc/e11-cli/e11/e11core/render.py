import json

def print_summary(summary, verbose=False):
    if verbose:
        print(json.dumps(summary,default=str,indent=4))

    lab = summary.get("lab")
    print(f"=== {lab} Results ===")
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

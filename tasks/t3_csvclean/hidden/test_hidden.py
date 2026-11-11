import csv
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def run(inp, expected):
    out = os.path.join(tempfile.mkdtemp(), "out.csv")
    p = subprocess.run([sys.executable, "clean.py", inp, out], cwd=HERE,
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-2000:]
    with open(out, newline="", encoding="utf-8") as f:
        got = [r for r in csv.reader(f) if r]
    with open(os.path.join(HERE, expected), newline="", encoding="utf-8") as f:
        want = [r for r in csv.reader(f) if r]
    if got != want:
        print("   expected:")
        for r in want:
            print("     ", r)
        print("   got:")
        for r in got:
            print("     ", r)
    assert got == want


def test_public_file():
    run("orders_raw.csv", "expected1.csv")


def test_hidden_file():
    run("orders_raw2.csv", "expected2.csv")


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:
                fails += 1
                print("FAIL", name, type(e).__name__, e)
    sys.exit(1 if fails else 0)

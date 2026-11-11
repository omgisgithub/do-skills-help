import sys
WANT = "210326 1898"
try:
    got = open("answer.txt").read()
except FileNotFoundError:
    print("FAIL no answer.txt"); sys.exit(1)
ok = " ".join(got.split()) == WANT
print(("PASS" if ok else "FAIL"), "answer.txt=%r want=%r" % (got.strip()[:200], WANT))
sys.exit(0 if ok else 1)

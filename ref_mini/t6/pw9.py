import sys

def run(src, wrap=True, sat=True, count_comments=False, skp_le=False, limit=10**6):
    prog = []
    for line in src.splitlines():
        code = line.split(";")[0].strip()
        if code:
            prog.append(code.split())
        elif count_comments:
            prog.append(["nop"])
    R = {k: 0 for k in "abcd"}
    M = 65536 if wrap else 1 << 64
    val = lambda x: R[x] if x in R else int(x)
    pc = 0; out = []; n = 0
    while 0 <= pc < len(prog) and n < limit:
        op, *a = prog[pc]; n += 1; nxt = pc + 1
        if op == "nop": pass
        elif op == "set": R[a[0]] = val(a[1]) % M
        elif op == "add": R[a[0]] = (R[a[0]] + val(a[1])) % M
        elif op == "mul": R[a[0]] = (R[a[0]] * val(a[1])) % M
        elif op == "mod":
            if val(a[1]) > 0: R[a[0]] %= val(a[1])
        elif op == "dec": R[a[0]] = max(0, R[a[0]] - 1) if sat else (R[a[0]] - 1) % M
        elif op == "jnz":
            if val(a[0]) != 0: nxt = pc + val(a[1])
        elif op == "skp":
            if (val(a[0]) <= val(a[1])) if skp_le else (val(a[0]) < val(a[1])): nxt = pc + 2
        elif op == "out": out.append(val(a[0]))
        pc = nxt
    return "%d %d" % (sum(out), n), n >= limit

src = open(sys.argv[1]).read()
print("correct      ", run(src))
print("no-wrap      ", run(src, wrap=False))
print("dec-wraps    ", run(src, sat=False))
print("comments-cnt ", run(src, count_comments=True))
print("skp<=        ", run(src, skp_le=True))

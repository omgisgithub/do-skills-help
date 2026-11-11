import re
import sys

REGS = ("a", "b", "c", "d")
OPERAND = re.compile(r"[abcd]|-?[0-9]+")
ARITY = {"set": 2, "add": 2, "mul": 2, "mod": 2, "dec": 1, "jnz": 2, "skp": 2, "out": 1}


def parse(text):
    prog = []
    for raw in text.split("\n"):
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        op, args = parts[0], parts[1:]
        if op not in ARITY or len(args) != ARITY[op]:
            raise ValueError("bad instruction: %r" % raw)
        for arg in args:
            if not OPERAND.fullmatch(arg):
                raise ValueError("bad operand %r in %r" % (arg, raw))
        if op in ("set", "add", "mul", "mod", "dec") and args[0] not in REGS:
            raise ValueError("bad destination in %r" % raw)
        prog.append((op, args))
    return prog


def run(text, limit=10**7):
    prog = parse(text)
    regs = {r: 0 for r in REGS}

    def val(x):
        return regs[x] if x in REGS else int(x)

    pc, count, outs = 0, 0, []
    while 0 <= pc < len(prog):
        if count >= limit:
            raise RuntimeError("step limit")
        op, args = prog[pc]
        count += 1
        nxt = pc + 1
        if op == "set":
            regs[args[0]] = val(args[1]) % 65536
        elif op == "add":
            regs[args[0]] = (regs[args[0]] + val(args[1])) % 65536
        elif op == "mul":
            regs[args[0]] = (regs[args[0]] * val(args[1])) % 65536
        elif op == "mod":
            y = val(args[1])
            if y > 0:
                regs[args[0]] = regs[args[0]] % y
        elif op == "dec":
            regs[args[0]] = max(0, regs[args[0]] - 1)
        elif op == "jnz":
            if val(args[0]) != 0:
                nxt = pc + val(args[1])
        elif op == "skp":
            if val(args[0]) < val(args[1]):
                nxt = pc + 2
        elif op == "out":
            outs.append(val(args[0]))
        pc = nxt
    return outs, count


if __name__ == "__main__":
    with open(sys.argv[1]) as f:
        outs, count = run(f.read())
    print("outputs:", outs)
    print("sum=%d count=%d" % (sum(outs), count))

import re, sys

def val(tok, regs):
    if tok in regs:
        return regs[tok]
    if re.fullmatch(r'-?\d+', tok):
        return int(tok)
    raise ValueError("bad operand: %r" % tok)

def run(path, cap=10**8):
    src = open(path, encoding='utf-8').read().split('\n')
    prog = []
    for line in src:
        code = line.split(';', 1)[0].strip()
        if code:
            prog.append(code.split())
    regs = {r: 0 for r in 'abcd'}
    outs = []
    pc, count = 0, 0
    while 0 <= pc < len(prog):
        if count >= cap:
            raise RuntimeError("cap hit")
        ins = prog[pc]
        op, args = ins[0], ins[1:]
        count += 1
        nxt = pc + 1
        if op == 'set':
            regs[args[0]] = val(args[1], regs) % 65536
        elif op == 'add':
            regs[args[0]] = (regs[args[0]] + val(args[1], regs)) % 65536
        elif op == 'mul':
            regs[args[0]] = (regs[args[0]] * val(args[1], regs)) % 65536
        elif op == 'mod':
            m = val(args[1], regs)
            if m > 0:
                regs[args[0]] = regs[args[0]] % m
        elif op == 'dec':
            regs[args[0]] = max(0, regs[args[0]] - 1)
        elif op == 'jnz':
            if val(args[0], regs) != 0:
                nxt = pc + val(args[1], regs)
        elif op == 'skp':
            if val(args[0], regs) < val(args[1], regs):
                nxt = pc + 2
        elif op == 'out':
            outs.append(val(args[0], regs))
        else:
            raise ValueError("unknown op %r" % op)
        pc = nxt
    return outs, count, prog, regs

if __name__ == '__main__':
    outs, count, prog, regs = run(sys.argv[1])
    print("instructions:", len(prog))
    print("outputs:", len(outs), outs[:20], '...', outs[-10:])
    print("sum:", sum(outs), "executed:", count, "final regs:", regs)
    print("%d %d" % (sum(outs), count))

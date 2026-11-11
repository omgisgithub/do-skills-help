import sys

def parse(path):
    prog = []
    for raw in open(path):
        line = raw.split(';', 1)[0].strip()
        if not line:
            continue
        prog.append(line.split())
    return prog

prog = parse('prog.pw9')
regs = {'a': 0, 'b': 0, 'c': 0, 'd': 0}

def val(x):
    if x in regs:
        return regs[x]
    return int(x)

outs = []
pc = 0
count = 0
steps = 0
while 0 <= pc < len(prog):
    instr = prog[pc]
    op = instr[0]
    count += 1
    steps += 1
    if steps > 100_000_000:
        raise SystemExit('too many steps')
    nextpc = pc + 1
    if op == 'set':
        regs[instr[1]] = val(instr[2]) % 65536
    elif op == 'add':
        regs[instr[1]] = (regs[instr[1]] + val(instr[2])) % 65536
    elif op == 'mul':
        regs[instr[1]] = (regs[instr[1]] * val(instr[2])) % 65536
    elif op == 'mod':
        m = val(instr[2])
        if m > 0:
            regs[instr[1]] = regs[instr[1]] % m
    elif op == 'dec':
        r = instr[1]
        if regs[r] > 0:
            regs[r] -= 1
    elif op == 'jnz':
        if val(instr[1]) != 0:
            nextpc = pc + val(instr[2])
    elif op == 'skp':
        if val(instr[1]) < val(instr[2]):
            nextpc = pc + 2
    elif op == 'out':
        outs.append(val(instr[1]))
    else:
        raise SystemExit('bad op ' + op)
    pc = nextpc

print(len(outs), 'outputs')
print('sum', sum(outs))
print('executed', count)
print(outs[:50], '...', outs[-10:])

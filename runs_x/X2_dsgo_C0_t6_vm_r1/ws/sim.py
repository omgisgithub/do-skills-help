import re

src = open('prog.pw9').read().splitlines()
ins = []
for raw in src:
    line = raw.split(';', 1)[0].strip()
    if line:
        ins.append(line.split())

regs = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
out = []

def val(x):
    return regs[x] if x in regs else int(x)

ip = 0
count = 0
steps = 0
while 0 <= ip < len(ins):
    count += 1
    steps += 1
    if steps > 100_000_000:
        print('too many steps')
        break
    parts = ins[ip]
    op = parts[0]
    nxt = ip + 1
    if op == 'set':
        r, x = parts[1], parts[2]
        regs[r] = val(x) % 65536
    elif op == 'add':
        r, x = parts[1], parts[2]
        regs[r] = (regs[r] + val(x)) % 65536
    elif op == 'mul':
        r, x = parts[1], parts[2]
        regs[r] = (regs[r] * val(x)) % 65536
    elif op == 'mod':
        r, x = parts[1], parts[2]
        v = val(x)
        if v > 0:
            regs[r] = regs[r] % v
    elif op == 'dec':
        r = parts[1]
        if regs[r] > 0:
            regs[r] -= 1
    elif op == 'jnz':
        x, k = parts[1], parts[2]
        if val(x) != 0:
            nxt = ip + val(k)
    elif op == 'skp':
        x, y = parts[1], parts[2]
        if val(x) < val(y):
            nxt = ip + 2
    elif op == 'out':
        out.append(val(parts[1]))
    else:
        raise ValueError(op)
    ip = nxt

print('sum', sum(out))
print('count', count)
print('outputs', out)

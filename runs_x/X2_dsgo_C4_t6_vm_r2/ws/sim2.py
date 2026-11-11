from __future__ import annotations

import sys
from pathlib import Path

MOD = 65536


def parse_operand(token: str) -> tuple[str, int]:
    if token in ("a", "b", "c", "d"):
        return ("reg", "abcd".index(token))
    return ("lit", int(token))


def value(operand: tuple[str, int], regs: list[int]) -> int:
    kind, v = operand
    return regs[v] if kind == "reg" else v


def main(path: Path) -> None:
    instructions: list[tuple[str, list[str]]] = []
    for raw in path.read_text().splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        instructions.append((parts[0], parts[1:]))

    regs = [0, 0, 0, 0]
    pc = 0
    executed = 0
    outputs: list[int] = []
    counts = [0] * len(instructions)
    steps = 0

    while 0 <= pc < len(instructions):
        steps += 1
        if steps > 10_000_000:
            print("did not halt", file=sys.stderr)
            break
        op, args = instructions[pc]
        executed += 1
        counts[pc] += 1
        next_pc = pc + 1

        if op == "set":
            r = "abcd".index(args[0]); regs[r] = value(parse_operand(args[1]), regs) % MOD
        elif op == "add":
            r = "abcd".index(args[0]); regs[r] = (regs[r] + value(parse_operand(args[1]), regs)) % MOD
        elif op == "mul":
            r = "abcd".index(args[0]); regs[r] = (regs[r] * value(parse_operand(args[1]), regs)) % MOD
        elif op == "mod":
            r = "abcd".index(args[0]); xv = value(parse_operand(args[1]), regs)
            if xv > 0:
                regs[r] = regs[r] % xv
        elif op == "dec":
            r = "abcd".index(args[0])
            if regs[r] > 0:
                regs[r] -= 1
        elif op == "jnz":
            if value(parse_operand(args[0]), regs) != 0:
                next_pc = pc + value(parse_operand(args[1]), regs)
        elif op == "skp":
            if value(parse_operand(args[0]), regs) < value(parse_operand(args[1]), regs):
                next_pc = pc + 2
        elif op == "out":
            outputs.append(value(parse_operand(args[0]), regs))
        else:
            raise ValueError(op)

        pc = next_pc

    print("final regs a b c d:", regs)
    print("output count:", len(outputs))
    print("sum:", sum(outputs))
    print("executed:", executed)
    print("per-instruction counts:")
    for i, (op, args) in enumerate(instructions):
        print(f"  {i:2d} {op:4s} {' '.join(args):8s} -> {counts[i]}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))

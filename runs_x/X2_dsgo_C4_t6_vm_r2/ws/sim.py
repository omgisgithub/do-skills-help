from __future__ import annotations

import sys
from pathlib import Path

MOD = 65536


def parse_operand(token: str) -> tuple[str, int | None]:
    """Return ('reg', index) or ('lit', value)."""
    if token in ("a", "b", "c", "d"):
        return ("reg", "abcd".index(token))
    return ("lit", int(token))


def value(operand: tuple[str, int], regs: list[int]) -> int:
    kind, v = operand
    assert v is not None
    if kind == "reg":
        return regs[v]
    return v


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
    steps = 0
    max_steps = 10_000_000

    while 0 <= pc < len(instructions):
        steps += 1
        if steps > max_steps:
            print("did not halt", file=sys.stderr)
            break
        op, args = instructions[pc]
        executed += 1
        next_pc = pc + 1

        if op == "set":
            r = "abcd".index(args[0])
            x = parse_operand(args[1])
            regs[r] = value(x, regs) % MOD
        elif op == "add":
            r = "abcd".index(args[0])
            x = parse_operand(args[1])
            regs[r] = (regs[r] + value(x, regs)) % MOD
        elif op == "mul":
            r = "abcd".index(args[0])
            x = parse_operand(args[1])
            regs[r] = (regs[r] * value(x, regs)) % MOD
        elif op == "mod":
            r = "abcd".index(args[0])
            x = parse_operand(args[1])
            xv = value(x, regs)
            if xv > 0:
                regs[r] = regs[r] % xv
        elif op == "dec":
            r = "abcd".index(args[0])
            if regs[r] > 0:
                regs[r] -= 1
        elif op == "jnz":
            x = parse_operand(args[0])
            k = parse_operand(args[1])
            if value(x, regs) != 0:
                next_pc = pc + value(k, regs)
        elif op == "skp":
            x = parse_operand(args[0])
            y = parse_operand(args[1])
            if value(x, regs) < value(y, regs):
                next_pc = pc + 2
        elif op == "out":
            x = parse_operand(args[0])
            outputs.append(value(x, regs))
        else:
            raise ValueError(f"unknown op {op}")

        pc = next_pc

    print("outputs:", outputs)
    print("count:", len(outputs))
    print("sum:", sum(outputs))
    print("executed:", executed)


if __name__ == "__main__":
    main(Path(sys.argv[1]))

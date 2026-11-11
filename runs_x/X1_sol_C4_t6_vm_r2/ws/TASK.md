# What does this program print?

`prog.pw9` is a program for the PLONKWICK-9 toy machine described below. Work out exactly what
it outputs and write your answer to a file `answer.txt` in this folder, as one line:

    <sum of all output values> <number of instructions executed>

for example `1234 567`. Only the content of `answer.txt` is graded. You may use any method.

## The PLONKWICK-9 machine
- Four registers `a b c d`. Each holds an unsigned 16-bit value (0–65535) and starts at 0.
- An operand `x` / `y` is either a register name or a decimal integer literal (may be negative,
  e.g. `-3`; literals are used as-is, they are not wrapped).
- Source: one instruction per line. Everything after `;` is a comment. Lines that are empty or
  contain only a comment are **not instructions** and are ignored entirely (also for jumps).
- Execution starts at the first instruction. The machine halts when the next instruction
  index falls outside the program (before the first or after the last instruction).

| Instruction | Meaning |
|---|---|
| `set r x` | r = x mod 65536 |
| `add r x` | r = (r + x) mod 65536 |
| `mul r x` | r = (r × x) mod 65536 |
| `mod r x` | if x > 0: r = r mod x. If x is 0, r is unchanged |
| `dec r` | r = r − 1, but **never below 0** (dec on 0 leaves 0) |
| `jnz x k` | if x ≠ 0, jump by k instructions relative to this one (`jnz a -2` goes back two instructions; `k` may be a register, read as its value); otherwise continue |
| `skp x y` | if x < y, the next instruction is skipped (not executed) |
| `out x` | output the value of x |

Counting: every instruction that is executed counts once, including the `jnz` that jumps
out and `skp` itself. A skipped instruction is not executed and does not count.
"Mod 65536" means the mathematical result in 0–65535 (so `add a -1` on 0 gives 65535).

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pw9 import run, parse


def outs(src):
    return run(src)[0]


# --- spec rules: must pass ---
assert outs("set a 65535\nadd a 1\nout a") == [0]
assert outs("add a -1\nout a") == [65535]          # add wraps: 0 + -1 mod 65536
assert outs("set a -3\nout a") == [65533]          # set wraps
assert outs("set a 70000\nout a") == [70000 - 65536]
assert outs("out -3") == [-3]                      # literals not wrapped
assert outs("set a 5\nmod a 0\nout a") == [5]      # mod by 0 unchanged
assert outs("set a 7\nmod a 3\nout a") == [1]
assert outs("dec a\nout a") == [0]                 # dec never below 0
assert outs("set a 2\ndec a\nout a") == [1]
assert outs("set a 3\nmul a 65536\nout a") == [0]
# loop with relative jnz: 2 passes
assert outs("set d 2\nset a 9\nout a\ndec d\njnz d -2\nout d") == [9, 9, 0]
# register used as jump offset: pc 2 + 2 -> 'out b'
assert outs("set d 2\nset a 1\njnz a d\nout a\nout b") == [0]
assert outs("set a 1\njnz 0 -3\nout a") == [1]     # jnz on literal 0 never jumps
# comment-only and blank lines are not instructions (also for jumps)
assert outs("out a\n; note\n\nout b\n") == [0, 0]
assert outs("set a 1 ; c\n; nothing\nout a ; x") == [1]
assert outs("jnz 1 2\n; comment\n\nout a\nout b") == [0]   # jump lands on 'out b'
# skp skips exactly one instruction; skipped one does not count
assert run("skp a 1\nout a\nout b") == ([0], 2)    # 0<1 -> skip 'out a'
assert run("skp b 0\nout b") == ([0], 2)           # 0<0 false -> no skip
assert run("out a\nskp a a\nout b") == ([0, 0], 3)

# --- must-fail cases: each must be rejected by the parser ---
bad = [
    "set a",             # missing operand
    "add a 1 2",         # extra operand
    "foo a 1",           # unknown op
    "set e 1",           # unknown register
    "set a 1.5",         # not an integer
    "set a +1",          # explicit plus not allowed
    "set a 0x10",        # hex
    "out",               # missing operand
    "dec 5",             # literal destination
    "Set a 1",           # wrong case
    "set  a  1 x",       # extra token
]
for src in bad:
    try:
        parse(src)
    except ValueError:
        pass
    else:
        raise AssertionError("should reject: %r" % src)

print("all asserts passed")

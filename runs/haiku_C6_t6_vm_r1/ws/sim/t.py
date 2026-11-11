import tempfile, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run import run
def go(text):
    with tempfile.NamedTemporaryFile('w', suffix='.pw9', delete=False) as f:
        f.write(text)
    try:
        outs, count, prog, regs = run(f.name)
    finally:
        os.unlink(f.name)
    return outs, count, regs
# spec examples
assert go("set a 5 ; c\n\n; only comment\nout a\n")[0] == [5]
assert go("add a -1\nout a\n")[0] == [65535]
assert go("dec a\nout a\n")[0] == [0]
assert go("set a 3\nmod a 0\nout a\n")[0] == [3]
assert go("set a 10\nmod a 4\nout a\n")[0] == [2]
assert go("set a 65536\nout a\n")[0] == [0]
assert go("set a -3\nout a\n")[0] == [65533]
assert go("set a 7\nmul a -1\nout a\n")[0] == [65529]
assert go("out -3\n")[0] == [-3]
# skp: skipped instruction not counted
o, n, _ = go("set a 1\nskp a 2\nout 99\nout 7\n")
assert o == [7] and n == 3, (o, n)
# skp not taken
o, n, _ = go("set a 5\nskp a 2\nout 99\nout 7\n")
assert o == [99, 7] and n == 4, (o, n)
# jnz with register offset; jnz to outside halts
o, n, _ = go("set b 2\njnz 1 b\nout 1\nout 2\n")
assert o == [2] and n == 3, (o, n)
o, n, _ = go("jnz 1 5\nout 1\n")
assert o == [] and n == 1
# jnz zero doesn't jump
assert go("jnz 0 -1\nout 4\n")[0] == [4]
print("all asserts pass")

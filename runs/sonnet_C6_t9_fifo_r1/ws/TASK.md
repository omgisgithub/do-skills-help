# Bug report: wrong cost of goods sold

`fifo.py` keeps per-SKU stock with FIFO costing for our accounting export.

The accountant reports that the cost of goods sold (COGS) returned by `Inventory.sell` is
sometimes a cent off, and that month-end numbers "don't add up" after some sales.

The docstrings in `fifo.py` are the specification. Make the module behave exactly as its
docstrings say. Keep the public API the same (class, method names, arguments, return types).
Python 3.9, standard library only. `test_fifo.py` has a few existing tests
(`python3 test_fifo.py`); they must keep passing.

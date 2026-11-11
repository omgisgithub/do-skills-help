# Bug report: frequent pollers get locked out

`limiter.py` implements a per-client token-bucket rate limiter used by our API gateway.

Support tickets say: clients that call the API often (several times per second) stay rate-limited
long after they slow down, even though their average rate is well under their limit. Clients that
call rarely are fine.

Fix the bug(s) in `limiter.py`. Keep the public API exactly the same (class names, method names,
arguments, return values). Do not add dependencies. `example.py` shows typical usage.

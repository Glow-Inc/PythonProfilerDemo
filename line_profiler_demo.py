from functools import wraps
from contextlib import contextmanager

import line_profiler

# Line Profiler Context Manager
@contextmanager
def line_profiling_ctx(func):
    pr = line_profiler.LineProfiler(func)
    pr.enable()
    yield
    pr.disable()
    pr.print_stats()

# Line Profiler Decorator
def line_profiling_deco(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        pr = line_profiler.LineProfiler(func)
        pr.enable()
        result = func(*args, **kwargs)
        pr.disable()
        pr.print_stats()
        return result
    return wrapped

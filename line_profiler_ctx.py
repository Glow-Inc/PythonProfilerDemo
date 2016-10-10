import line_profiler
from contextlib import contextmanager

@contextmanager
def line_profiling(func):
    pr = line_profiler.LineProfiler(func)
    pr.enable()
    yield
    pr.disable()
    pr.print_stats()

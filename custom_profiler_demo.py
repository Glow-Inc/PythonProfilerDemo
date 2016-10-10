import types
import functools
import logging
import sys
import time
from threading import local
from contextlib import contextmanager
from collections import Counter

import redis
import requests

from tabulate import tabulate

_local_context = local()
class PerfTimer(object):
    def __init__(self):
        self.init()

    def init(self, profiler_name='', verbose=False):
        self.profiler_name = profiler_name
        self.verbose = verbose
        self.call_logs = []
        self.time_spent = Counter()
        self.lock = False
        self.logger = logging.getLogger('PerfTimer')

    def log_time(self, item_name, category, time_spent, args, kwargs):
        self.time_spent.update({(item_name, category): time_spent})
        if self.verbose:
            self.call_logs.append({
                'name': item_name,
                'time': time_spent,
                'args': args,
                'kwargs': kwargs
                })

    def report(self):
        result =['Performance stats for {}'.format(self.profiler_name)]
        # sorted time by category
        category_time = Counter()
        for key, time_spent in self.time_spent.items():
            category_time.update({key[1]: time_spent})
        rows = category_time.items()
        rows.sort(key=lambda x: x[1], reverse=True)
        result.append(tabulate(rows, headers=["CATEGROY", "TIME"]))

        # sorted time by func calls
        result.append('')
        rows = [(k[0], v) for k, v in self.time_spent.items()]
        rows.sort(key=lambda x: x[1], reverse=True)
        result.append(tabulate(rows, headers=["CALL", "TIME"]))

        # individual calls
        if self.verbose:
            result.append('\nCALL HISTORY')
            for log in self.call_logs:
                result.append('    {time:.4f}s {name}'
                                 '[args={args} kwargs={kwargs}]'.format(**log))
        self.logger.info('\n'.join(result))

    def acquire_lock(self):
        """ Acquire the lock

        A function should only be timed if none of its caller is timed.
        Otherwise, there will be double-count. Acquire a lock before timing
        ensures that condition.
        """
        if not self.lock:
            self.lock = True
            return True
        return False

    def unlock(self):
        """ Release the lock """
        self.lock = False

    @classmethod
    def get_instance(self):
        """ There should be only one PerfTimer instance per-thread """
        if not hasattr(_local_context, 'perf_timer'):
            _local_context.perf_timer = PerfTimer()
        return _local_context.perf_timer

def patch_module(module, category, methods=None):
    if not methods:
        methods = [m for m in dir(module) if not m.startswith('_')
                   and isinstance(getattr(module, m), types.FunctionType)]
    for name in methods:
        func = getattr(module, name)
        fullname = '{}.{}'.format(func.__module__, name)
        setattr(module, name, logging_perf(func, fullname, category))

def patch_class(cls, category, methods=None):
    if not methods:
        methods = [m for m in dir(cls) if not m.startswith('_')
                   and isinstance(getattr(cls, m), types.MethodType)]
    for name in methods:
        method = getattr(cls, name)
        fullname = '{}.{}.{}'.format(cls.__module__, cls.__name__, name)
        patched_func = logging_perf(method.im_func, fullname, category)
        if isinstance(method, classmethod):
            setattr(cls, name, classmethod(patched_func))
        elif isinstance(method, staticmethod):
            setattr(cls, name, staticmethod(patched_func))
        else:
            setattr(cls, name, patched_func)

def logging_perf(func, fullname, category):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        perf_timer = PerfTimer.get_instance()
        if perf_timer.acquire_lock():
            start_time = time.time()
            result = func(*args, **kwargs)
            time_spent = time.time() - start_time
            perf_timer.log_time(
                fullname, category, time_spent, args, kwargs)
            perf_timer.unlock()
            return result
        else:
            return func(*args, **kwargs)
    return wrapped

@contextmanager
def profiling(profiler_name, verbose):
    perf_timer = PerfTimer.get_instance()
    perf_timer.init(profiler_name, verbose)
    yield
    perf_timer.report()

if __name__ == '__main__':
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s'
    )
    patch_module(requests, 'http')
    patch_class(redis.StrictRedis, 'redis')
    with profiling('Custom profiler demo', verbose=True):
        resp = requests.get('http://tech.glowing.com')
        print resp.status_code
        redis_conn = redis.StrictRedis()
        redis_conn.set('foo', 'bar')
        print redis_conn.get('foo')

"""Cooperative operation budgets shared by synchronous platform calls."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
import threading
import time


class Cancelled(RuntimeError):
    pass


@dataclass
class Budget:
    deadline: float
    cancelled: threading.Event

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled("Operation cancelled")
        if time.monotonic() >= self.deadline:
            raise TimeoutError("Operation time limit exceeded")


_current = ContextVar('eara_operation', default=None)


def check():
    budget = _current.get()
    if budget is not None:
        budget.check()


@contextmanager
def cleanup():
    """Allow bounded resource cleanup even after the operation was cancelled."""
    token = _current.set(None)
    try:
        yield
    finally:
        _current.reset(token)


def timeout(seconds):
    check()
    budget = _current.get()
    return min(seconds, max(0.001, budget.deadline - time.monotonic())) if budget else seconds


def pause(seconds):
    budget = _current.get()
    if budget is None:
        time.sleep(seconds)
        return
    check()
    budget.cancelled.wait(timeout(seconds))
    check()


@contextmanager
def scope(seconds, cancelled=None):
    parent = _current.get()
    deadline = time.monotonic() + seconds
    budget = Budget(min(deadline, parent.deadline) if parent else deadline,
                    parent.cancelled if parent else (cancelled or threading.Event()))
    token = _current.set(budget)
    try:
        check()
        yield budget
        check()
    finally:
        _current.reset(token)


def bounded(seconds):
    def decorate(fn):
        @wraps(fn)
        def run(*args, **kwargs):
            with scope(seconds):
                return fn(*args, **kwargs)
        return run
    return decorate

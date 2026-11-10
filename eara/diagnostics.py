"""Opt-in local phase timings. Never records device identifiers or payloads."""
from contextvars import ContextVar
from functools import wraps
from itertools import count
import json
import os
import sys
import time

from eara.operations import Cancelled

_parent = ContextVar("eara_trace_parent", default=None)
_ids = count(1)


def timed(phase, *, response=False):
    """Emit one JSON line on stderr when EARA_TRACE=1; preserve call semantics.

    Parent/span IDs describe synchronous nesting, not cross-thread causality.
    Durations include nested phases and must not be summed together.
    """
    def decorate(fn):
        @wraps(fn)
        def run(*args, **kwargs):
            if os.environ.get("EARA_TRACE") != "1":
                return fn(*args, **kwargs)
            parent = _parent.get()
            span = next(_ids)
            token = _parent.set(span)
            started = time.monotonic()
            outcome = "error"
            try:
                result = fn(*args, **kwargs)
                outcome = "completed"
                if result is False or (isinstance(result, dict) and (
                    result.get("ok") is False or result.get("available") is False
                )):
                    outcome = "unavailable"
                elif response and result is None:
                    outcome = "no_response"
                return result
            except Cancelled:
                outcome = "cancelled"
                raise
            except TimeoutError:
                outcome = "timeout"
                raise
            finally:
                _parent.reset(token)
                # A closed stderr (e.g. piped diagnostics) must never fail a
                # hardware command or hide its original exception.
                try:
                    event = {"eara_trace": 1, "pid": os.getpid(), "span": span,
                             "parent": parent, "phase": phase,
                             "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
                             "outcome": outcome}
                    sys.stderr.write(json.dumps(event) + "\n")
                except Exception:
                    pass
        return run
    return decorate

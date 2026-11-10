"""Short-lived audio snapshots; mutations invalidate in-flight cache fills."""
from copy import deepcopy
import threading
import time
from eara import operations


class AudioStateCache:
    def __init__(self, ttl=3.0):
        self.ttl = ttl
        self._lock = threading.Lock()
        self._generation = 0
        self._entry = None

    def invalidate(self):
        with self._lock:
            self._generation += 1
            self._entry = None

    def get(self, backend, address, *, refresh=False):
        operations.check()
        with self._lock:
            if refresh:
                self._generation += 1
                self._entry = None
            entry = self._entry
            if entry is not None:
                owner, target, expires, state = entry
                if owner is backend and target == address and time.monotonic() < expires:
                    return deepcopy(state)
            generation = self._generation
        # Never hold the cache lock during platform I/O or serve an expired value
        # when that I/O fails. Errors/unavailable states are retried next time.
        state = backend.state(address).as_dict()
        operations.check()
        with self._lock:
            if generation == self._generation and not state.get('error') and state.get('available', True):
                self._entry = (backend, address, time.monotonic() + self.ttl, deepcopy(state))
        return state

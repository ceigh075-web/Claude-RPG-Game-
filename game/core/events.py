"""Minimal publish/subscribe event bus used to decouple systems (e.g. Set AI listens for gameplay events)."""
from collections import defaultdict


class EventBus:
    def __init__(self):
        self._subs = defaultdict(list)

    def subscribe(self, name, fn):
        self._subs[name].append(fn)

    def unsubscribe(self, name, fn):
        if fn in self._subs[name]:
            self._subs[name].remove(fn)

    def publish(self, name, **payload):
        for fn in list(self._subs[name]):
            fn(**payload)
        for fn in list(self._subs["*"]):
            fn(name, payload)

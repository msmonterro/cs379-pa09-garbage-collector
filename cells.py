"""Shared parameter cells: each environment binding owns its reference."""
from gc_heap import retain, release


class Cell:
    def __init__(self, value):
        self._value = value
        self._bindings = []

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        # Retain all new owners before releasing any old owners (self assignment).
        retained = []
        try:
            for heap in self._bindings:
                retain(value, heap)
                retained.append(heap)
        except Exception:
            for heap in retained:
                release(value, heap)
            raise
        old = self._value
        self._value = value
        for heap in self._bindings:
            release(old, heap)

    def bind(self, heap):
        retain(self._value, heap)
        self._bindings.append(heap)

    def unbind(self, heap):
        self._bindings.remove(heap)
        release(self._value, heap)

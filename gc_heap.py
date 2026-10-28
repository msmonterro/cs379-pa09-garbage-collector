"""PA9: explicit reference counting. No tracing or cycle collection."""
from collections import deque


class Handle(int):
    """Tagged integer: an ordinary integer is NEVER treated as a pointer."""
    def __new__(cls, value, heap):
        instance = super().__new__(cls, value)
        instance.heap = heap
        return instance


def retain(value, heap):
    if isinstance(value, Handle):
        if value.heap is not heap:
            raise ValueError("Cannot store a handle from a different heap")
        heap.incref(value)


def release(value, heap):
    if isinstance(value, Handle):
        if value.heap is not heap:
            raise ValueError("Cannot release a handle from a different heap")
        heap.decref(value)


class GCHeap:
    def __init__(self):
        self._objects = {}
        self._counts = {}
        self._next = 1
        self._pending = deque()
        self._draining = False
        self._ast_handles = {}
        self._children = {}

    def allocate(self, obj) -> int:
        """Return one OWNED creating reference. Store/transfer it, then release it."""
        handle = Handle(self._next, self)
        self._next += 1
        self._objects[handle] = obj
        self._counts[handle] = 1
        # Also support the handout's heap.allocate(USIObject(...)) API.
        if hasattr(obj, 'fields') and getattr(obj, 'heap', None) is None:
            obj.heap = self
            obj.fields = ReferenceSlots(self, obj.fields)
            obj.handle = handle
        return handle

    def _require(self, handle):
        if not isinstance(handle, int) or isinstance(handle, bool):
            raise TypeError("Expected an integer handle")
        if isinstance(handle, Handle) and handle.heap is not self:
            raise ValueError("Handle belongs to another heap")
        if handle not in self._objects:
            raise ReferenceError(f"Dead or unknown handle: {int(handle)}")

    def get(self, handle):
        self._require(handle)
        return self._objects[handle]

    def refcount(self, handle):
        self._require(handle)
        return self._counts[handle]

    def incref(self, handle: int) -> None:
        self._require(handle)
        self._counts[handle] += 1

    def decref(self, handle: int) -> None:
        self._require(handle)
        self._counts[handle] -= 1
        if self._counts[handle] == 0:
            obj = self._objects.pop(handle)
            del self._counts[handle]
            self._pending.append((handle, obj))
        if self._draining:
            return
        self._draining = True
        try:
            # Work queue gives recursive cascade semantics without Python's
            # recursion-depth limit on a long object chain.
            while self._pending:
                dead_handle, obj = self._pending.popleft()
                if hasattr(obj, 'gc_release'):
                    obj.gc_release()
                else:
                    for child in self._children.pop(dead_handle, ()):
                        self.decref(child)
                    if self._ast_handles.get(id(obj)) is not None:
                        del self._ast_handles[id(obj)]
        finally:
            self._draining = False

    def is_alive(self, handle: int) -> bool:
        if isinstance(handle, Handle) and handle.heap is not self:
            return False
        return isinstance(handle, int) and not isinstance(handle, bool) and handle in self._objects

    def live_count(self) -> int:
        return len(self._objects)

    def track_ast(self, node):
        """Return an owned reference; each parent owns its child AST edges."""
        existing = self._ast_handles.get(id(node))
        if existing is not None and self.is_alive(existing):
            self.incref(existing)
            return existing
        from dataclasses import fields, is_dataclass
        children = []
        if is_dataclass(node):
            for field in fields(node):
                value = getattr(node, field.name)
                candidates = value if isinstance(value, list) else [value]
                for child in candidates:
                    if is_dataclass(child):
                        children.append(self.track_ast(child))
        elif hasattr(node, 'body'):
            children.append(self.track_ast(node.body))
        handle = self.allocate(node)
        self._children[handle] = children
        self._ast_handles[id(node)] = handle
        return handle


class ReferenceSlots(dict):
    """A field map whose mutators all implement retain-before-release."""
    def __init__(self, heap, values=None):
        self.heap = heap
        super().__init__()
        self.update(values or {})

    def __setitem__(self, key, value):
        retain(value, self.heap)
        old = self.get(key)
        super().__setitem__(key, value)
        release(old, self.heap)

    def __delitem__(self, key):
        old = self[key]
        super().__delitem__(key)
        release(old, self.heap)

    def update(self, values=(), **kwargs):
        for key, value in dict(values, **kwargs).items():
            self[key] = value

    def clear(self):
        for key in list(self):
            del self[key]

    def pop(self, key, *default):
        if key not in self:
            if default:
                return default[0]
            raise KeyError(key)
        value = self[key]
        # Like reading a field, the result is borrowed, not a new GC root.
        del self[key]
        return value

    def popitem(self):
        if not self:
            raise KeyError('empty field map')
        key = next(reversed(self))
        return key, self.pop(key)

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]

    def __ior__(self, values):
        self.update(values)
        return self

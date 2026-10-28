# PA9: The Garbage Collector

Reference-counting integration built from the supplied PA6, PA7 and PA8 submissions.

## Run

Requires Python 3.10+; no third-party packages are required.

```bash
python3 test_gc.py
python3 test_parameters.py
python3 test_dispatcher.py
```

Expected final tokens: `GC_HEAP_VERIFIED`, `PARAMETER_BINDING_VERIFIED`, and `VTABLE_DISPATCH_VERIFIED`.

`test_gc.py` is the PA9 harness included with this implementation, written against the uploaded assignment requirements. It is not presented as a downloaded instructor harness. `test_parameters.py` and `test_dispatcher.py` are preserved from the uploaded prior-stage submissions.

## Files and ownership

- `gc_heap.py`: integer handles, reference counts, retain/release, managed field maps, AST tracking, and cascading teardown. `Handle` is an `int` subclass carrying its owning heap; ordinary language integers are not mistaken for handles.
- `cells.py`: shared mutable cells. Each environment binding retains its stored handle. A reference-mode alias adds an owner; writing a shared Cell updates the reference count for every binding.
- `symtable.py`: prior-stage Environment extended with managed bindings and lexical-parent ownership.
- `frames.py`: popping a frame releases its environment ownership. Uncaptured environments immediately release every local. If a closure retains an environment, its locals remain valid until that capture is released, rather than being invalidated on return.
- `parameters.py`: PA7 binding modes reuse managed cells; copy-back updates counts. Heap-backed closures retain their defining environment and declaration AST. Closure calls release their temporary frame in `finally`.
- `dispatcher.py`: PA8 VTable dispatch plus heap-backed objects and managed fields. Managed method receivers are passed as handles; prior non-heap tests retain their original object interface.
- `lexer.py`, `parser.py`: earlier arithmetic grammar extended for zero-argument object construction, `null`, fields and field assignment, plus `//` comments.
- `interpreter.py`: executes this grammar through heap-backed environments, fields and frames. Its default class registry includes empty `Dog` and `Node` VTables for the assignment's examples. This is not a full class-declaration parser.
- `PA9_Theory.md`: Part A answers.
- `verification_output.txt`: captured PA9 execution output.
- `regression_output.txt`: captured PA7 and PA8 executions.

`allocate(obj)` starts at count 1. The returned creating reference is owned by the caller. A variable/field write retains a stored handle; afterward the caller releases its creating or temporary reference. Reads are borrowed unless an API explicitly states otherwise. Interpreter expressions and heap-backed `Closure.call` return one owned reference for handle-valued results, which callers must release after storing or using it. Retaining the new value before releasing the old value makes self-assignment safe.

Use `USIObject(vtable, fields, heap)` or `heap.allocate(USIObject(vtable, fields))` for managed objects. Use `Environment(heap=heap)` for managed scopes and `parse(tokens, heap=heap)` for a managed AST root. Release a program root with `heap.decref(program.handle)` and a scope root with `env.close()`. Prior-stage APIs without a heap remain available for compatibility; the PA9 Interpreter always supplies a heap. Do not replace managed `fields` or write private environment/cell storage directly.

For example:

```python
from interpreter import Interpreter
vm = Interpreter()
try:
    vm.run('let a = Dog(); let b = a; let c = Dog(); b = c; a = null;')
finally:
    vm.close()
assert vm.heap.live_count() == 0
```

`live_count()` includes tracked AST and environment nodes as well as USIObjects. The isolated alias test subtracts the environment baseline. After source execution, its AST is released; after `vm.close()`, the environment is also released. Thus the cycle test ends with exactly two leaked nodes and no unrelated infrastructure allocations.

The cascade uses a work queue to free arbitrarily long chains without exceeding Python's recursive-call limit. All cascades complete before the outer `decref` returns. No mark-and-sweep, weak-reference cycle workaround, or implicit cycle-breaking pass is implemented. The cycle test explicitly reports the expected failure of reference counting while checking that this behavior matches the specification.


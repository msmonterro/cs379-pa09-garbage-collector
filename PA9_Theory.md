# PA 9: The Garbage Collector
## Part A: The Specification

### 1. Refcount Trace

The counts below represent references owned by variables after each statement finishes. The creating reference from `allocate` is transferred to the destination variable, or released after the variable retains the object; it is not an extra permanent reference.

| Line | Statement | D1 refcount | D2 refcount | Live objects |
| --- | --- | --- | --- | --- |
| 1 | `let a = Dog();` | 1 | Not allocated | 1 |
| 2 | `let b = a;` | 2 | Not allocated | 1 |
| 3 | `let c = Dog();` | 2 | 1 | 2 |
| 4 | `b = c;` | 1 | 2 | 2 |
| 5 | `a = null;` | 0 (freed) | 2 | 1 |

At line 4, `b` stops referencing D1 and starts referencing D2. D1 still has the reference from `a`, while D2 is referenced by both `b` and `c`.

D1's refcount reaches zero exactly at line 5, `a = null;`. `GCHeap.decref` must immediately remove D1 from the live heap and release every owned handle stored in its fields. Releasing those handles may recursively free other objects. In this example, D1 has no specified outgoing references. Afterward, `is_alive(D1_handle)` must return `False`.

### 2. The Cycle That Won't Die

Call the first Node object N1 and the second N2. Variable names `n1` and `n2` are distinct from the objects they reference.

| Statement | N1 refcount | N2 refcount | References to N1 | References to N2 |
| --- | --- | --- | --- | --- |
| `let n1 = Node();` | 1 | Not allocated | Variable `n1` | None |
| `let n2 = Node();` | 1 | 1 | Variable `n1` | Variable `n2` |
| `n1.next = n2;` | 1 | 2 | Variable `n1` | Variable `n2`, N1.next |
| `n2.prev = n1;` | 2 | 2 | Variable `n1`, N2.prev | Variable `n2`, N1.next |
| `n1 = null;` | 1 | 2 | N2.prev | Variable `n2`, N1.next |
| `n2 = null;` | 1 | 1 | N2.prev | N1.next |

Before the null assignments, each object has a count of 2: one reference from a variable and one from the other object's field. The first null assignment decreases N1 from 2 to 1. The second decreases N2 from 2 to 1. Neither count reaches zero.

After both assignments, no program variable reaches either object, but N1.next still owns a reference to N2, and N2.prev still owns a reference to N1. Since freeing occurs only at count zero, neither object is freed. Consequently, neither object's outgoing reference is released, so both counts remain 1. In a heap containing only these two objects, `live_count()` remains 2. Reference counting measures incoming references, not reachability from program roots, which explains this leak mechanically.

### 3. Refcounting vs. Mark-and-Sweep

**When immediate reclamation matters:** Consider a USILang batch-processing program with a resource-like `FileReader` object that owns an operating-system file handle. If object cleanup closes that handle, releasing the last reference at the end of each iteration closes the file promptly. This helps avoid exhausting file handles while processing many files. This example assumes the language provides resource cleanup when the object is freed; reclaiming heap memory alone does not automatically close an external resource.

**When cycles leak over time:** Consider a long-running USILang REPL that repeatedly creates two Nodes, assigns `n1.next = n2` and `n2.prev = n1`, and then clears both variables. As shown above, each discarded pair retains counts of 1 and 1. After k repetitions, 2k Node objects remain allocated even though none is reachable from program variables. A mark-and-sweep collector could reclaim these objects by tracing from roots, marking reachable objects, and sweeping the unmarked pairs.

Reference counting performs cleanup when the last owned reference disappears. Mark-and-sweep can reclaim unreachable cycles. However, immediate cleanup is not necessarily constant-time: a single decrement can trigger a long cascade through an entire chain of objects.

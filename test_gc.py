"""PA9 verification: run with python test_gc.py. Assertions must be enabled."""
from cells import Cell
from dispatcher import ClassDecl, USIObject, build_vtable, dispatch
from frames import ActivationRecord, CallStack
from gc_heap import GCHeap
from interpreter import Interpreter
from lexer import tokenize
from parameters import Closure, FunctionDecl, bind_parameters, commit_value_result
from parser import Variable, parse
from symtable import Environment


def check(label, condition):
    if not condition:
        raise AssertionError(label)
    print('[PASS]', label)


def frame(env):
    return ActivationRecord('test', {}, env, 'return', None, None)


def alias_trace():
    heap = GCHeap()
    env = Environment(heap=heap)
    table = build_vtable(ClassDecl('Dog', {}))
    baseline = heap.live_count()
    d1 = heap.allocate(USIObject(table, {}))
    env.define('a', Cell(d1)); heap.decref(d1)
    check('line 1: D1=1; one object', heap.refcount(d1) == 1 and heap.live_count() == baseline+1)
    env.define('b', Cell(d1))
    check('line 2: alias D1=2', heap.refcount(d1) == 2)
    d2 = USIObject(table, {}, heap).handle
    env.define('c', Cell(d2)); heap.decref(d2)
    check('line 3: D1=2, D2=1; two objects', heap.refcount(d1) == 2 and heap.refcount(d2) == 1 and heap.live_count() == baseline+2)
    env.assign('b', d2)
    check('line 4: D1=1, D2=2; still two objects', heap.refcount(d1) == 1 and heap.refcount(d2) == 2 and heap.live_count() == baseline+2)
    env.assign('a', None)
    check('line 5: D1 freed at a=null; D2=2', not heap.is_alive(d1) and heap.refcount(d2) == 2 and heap.live_count() == baseline+1)
    env.assign('b', d2)
    check('self-assignment keeps the same count', heap.refcount(d2) == 2)
    stack = CallStack(); stack.push(frame(env)); stack.pop()
    check('popping frame releases every local and environment', heap.live_count() == 0)


def cascade_and_fields():
    heap = GCHeap(); table = build_vtable(ClassDecl('Node', {}))
    root = USIObject(table, {}, heap).handle
    cursor = root
    for _ in range(1500):
        child = USIObject(table, {}, heap).handle
        heap.get(cursor).fields['next'] = child
        heap.decref(child)
        cursor = child
    check('1501-object chain allocated', heap.live_count() == 1501)
    heap.decref(root)
    check('one decref frees entire chain without recursion overflow', heap.live_count() == 0)
    parent = USIObject(table, {}, heap).handle
    a = USIObject(table, {}, heap).handle
    b = USIObject(table, {}, heap).handle
    heap.get(parent).fields['next'] = a; heap.decref(a)
    heap.get(parent).fields['next'] = b; heap.decref(b)
    check('field overwrite releases old object and retains new', not heap.is_alive(a) and heap.refcount(b) == 1)
    heap.get(parent).fields['next'] = b
    check('field self-assignment safe', heap.refcount(b) == 1)
    heap.get(parent).fields.update({'next': None})
    check('field update releases overwritten handle', not heap.is_alive(b))
    heap.decref(parent)
    number = heap.allocate(object())
    env = Environment(heap=heap)
    env.define('number', Cell(int(number)))
    env.close()
    check('ordinary integer does not change refcount', heap.refcount(number) == 1)
    heap.decref(number)
    try:
        heap.decref(number)
    except ReferenceError:
        check('double release rejected', True)
    else:
        raise AssertionError('double release accepted')


def parameters_and_closures():
    for mode in ('value', 'reference', 'value-result'):
        heap = GCHeap(); caller = Environment(heap=heap)
        obj = USIObject(build_vtable(ClassDecl('Dog', {})), {}, heap).handle
        caller.define('x', Cell(obj)); heap.decref(obj)
        callee = Environment(heap=heap); record = frame(callee)
        stack = CallStack(); stack.push(record)
        bind_parameters([('p', mode)], [Variable('x', 1)], caller, record)
        check(f'{mode}: parameter binding retains object', heap.refcount(obj) == 2)
        callee.assign('p', None)
        if mode == 'reference':
            check('reference write updates both aliases and frees object', not heap.is_alive(obj) and caller.resolve('x').value is None)
        else:
            check(f'{mode}: caller still owns object before return', heap.refcount(obj) == 1)
        commit_value_result(record, caller)
        stack.pop(); caller.close()
        check(f'{mode}: frame and caller teardown leak no objects', heap.live_count() == 0)
    heap = GCHeap(); env = Environment(heap=heap)
    obj = USIObject(build_vtable(ClassDecl('Dog', {})), {}, heap).handle
    env.define('captured', Cell(obj)); heap.decref(obj)
    closure = Closure(FunctionDecl(['x'], Variable('x', 1)), env)
    result = closure.call([obj], env)
    check('closure return survives callee pop', heap.refcount(obj) == 2)
    heap.decref(result)
    env.close()
    check('closure preserves captured environment after its root exits', heap.is_alive(env.handle) and heap.is_alive(obj))
    result = closure.call([obj], None); heap.decref(result)
    heap.decref(closure.handle)
    check('closure release frees AST, captured environment and object', heap.live_count() == 0)
    # Exercise PA8 -> real PA7 Closure -> managed receiver parameter.
    heap = GCHeap(); env = Environment(heap=heap)
    method = Closure(FunctionDecl(['self'], Variable('self', 1)), env)
    obj = USIObject(build_vtable(ClassDecl('Dog', {'identity': method})), {}, heap).handle
    result = dispatch(obj, 'identity', [], env)
    check('managed dispatch retains and returns receiver', result == obj and heap.refcount(obj) == 2)
    heap.decref(result); heap.decref(obj); heap.decref(method.handle); env.close()
    check('managed dispatch cleanup reaches zero', heap.live_count() == 0)


def ast_and_interpreter():
    heap = GCHeap()
    tree = parse(tokenize('let x = 1 + 2; x = x * 3;'), heap=heap)
    check('parser tracks AST nodes on heap', heap.live_count() > 1)
    heap.decref(tree.handle)
    check('AST root release cascades through all children', heap.live_count() == 0)
    vm = Interpreter()
    counts = []
    def trace(line, vm):
        a = vm.env.resolve('a').value
        b = vm.env.resolve('b').value if line >= 2 else None
        c = vm.env.resolve('c').value if line >= 3 else None
        counts.append((vm.heap.refcount(a) if a else 0, vm.heap.refcount(c) if c else 0))
    vm.run('let a = Dog(); // D1\nlet b = a; let c = Dog(); b = c; a = null;', trace)
    check('source program reproduces Part A counts', counts == [(1, 0), (2, 0), (2, 1), (1, 2), (0, 2)])
    check('source AST reclaimed after execution', vm.heap.live_count() == 2)  # env + D2
    vm.close()
    check('interpreter final scope releases remaining object', vm.heap.live_count() == 0)
    vm = Interpreter()
    try:
        vm.run('let x = missing;')
    except Exception:
        pass
    else:
        raise AssertionError('undeclared variable accepted')
    vm.close()
    check('exception path releases program AST and scope', vm.heap.live_count() == 0)


def cycle_expected_leak():
    vm = Interpreter()
    nodes = []
    counts = []
    def trace(line, vm):
        if line == 1:
            nodes.append(vm.env.resolve('n1').value)
        if line == 2:
            nodes.append(vm.env.resolve('n2').value)
        if line >= 4:
            counts.append(tuple(vm.heap.refcount(h) for h in nodes))
    vm.run('let n1 = Node(); let n2 = Node(); n1.next = n2; n2.prev = n1; n1 = null; n2 = null;', trace)
    check('cycle counts: (2,2) -> (1,2) -> (1,1)', counts == [(2, 2), (1, 2), (1, 1)])
    vm.close()
    check('EXPECTED LEAK: both nodes survive after both variables leave scope', vm.heap.live_count() == 2 and all(vm.heap.is_alive(h) for h in nodes))
    print('CYCLE FAILURE DEMONSTRATED: live_count() = 2; refcounts = (1, 1).')
    print('Reference counting cannot reclaim this unreachable cycle. No sweep is performed.')


def main():
    alias_trace()
    cascade_and_fields()
    parameters_and_closures()
    ast_and_interpreter()
    cycle_expected_leak()
    print('GC_HEAP_VERIFIED')


if __name__ == '__main__':
    main()

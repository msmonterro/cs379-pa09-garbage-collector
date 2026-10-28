"""
PA 7: The Parameter Simulator -- verification suite.

Run: python test_parameters.py
Prints PARAMETER_BINDING_VERIFIED only if every check below passes
(this PA's success signal is a fixed literal string -- see
PA_07_The_Parameter_Simulator.md, Part B).
"""

import sys

from frames import ActivationRecord
from parameters import Cell, Closure, FunctionDecl, assign_through, bind_parameters, commit_value_result, evaluate
from parser import BinOp, Variable
from symtable import Environment


def dependency_preflight() -> None:
    """Check the prior-stage interfaces used by this PA before its test body."""
    env = Environment()
    try:
        env.define("pa7_preflight", Cell(7))
        assert evaluate(Variable("pa7_preflight", 0), env) == 7
        record = ActivationRecord("preflight", {}, Environment(), "call site", None, None)
        assert record.locals_env is not None
    except (NotImplementedError, AssertionError, TypeError, AttributeError) as exc:
        raise SystemExit(
            "PA 7 dependency preflight failed: copy your completed prior-stage "
            "files into this directory. This check exercises Environment and "
            "ActivationRecord; run your earlier tests separately for lexer/parser. "
            + str(exc)
        ) from exc


def check(label: str, condition: bool, failures: list) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        failures.append(label)


def run_swap(mode: str, x_val: int, y_val: int, x_name: str = "x", y_name: str = "y"):
    """
    Harness-driven simulation of `swap(a, b) { let t = a; a = b; b = t; }`
    called as swap(x_name, y_name), under the given binding mode.
    Returns the caller's (x, y) values after the call.
    """
    caller_env = Environment()
    caller_env.define(x_name, Cell(x_val))
    if y_name != x_name:
        caller_env.define(y_name, Cell(y_val))

    callee_env = Environment()
    callee_record = ActivationRecord("swap", {}, callee_env, "call site", None, None)

    param_specs = [("a", mode), ("b", mode)]
    arg_nodes = [Variable(x_name, 0), Variable(y_name, 0)]
    bind_parameters(param_specs, arg_nodes, caller_env, callee_record)

    # simulate: let t = a; a = b; b = t;
    t_val = evaluate(Variable("a", 0), callee_record.locals_env)
    callee_record.locals_env.define("t", Cell(t_val))
    b_val = evaluate(Variable("b", 0), callee_record.locals_env)
    assign_through(callee_record.locals_env, "a", b_val)
    t_val2 = evaluate(Variable("t", 0), callee_record.locals_env)
    assign_through(callee_record.locals_env, "b", t_val2)

    commit_value_result(callee_record, caller_env)

    result_x = evaluate(Variable(x_name, 0), caller_env)
    result_y = evaluate(Variable(y_name, 0), caller_env) if y_name != x_name else None
    return result_x, result_y


def main() -> int:
    dependency_preflight()
    failures: list = []

    print("Testing swap(x, y) under all three binding modes (x=1, y=2 beforehand)...\n")
    vx, vy = run_swap("value", 1, 2)
    check("value mode: caller's x, y are UNCHANGED after the call (1, 2)", (vx, vy) == (1, 2), failures)

    rx, ry = run_swap("reference", 1, 2)
    check("reference mode: caller's x, y ARE swapped (2, 1)", (rx, ry) == (2, 1), failures)

    vrx, vry = run_swap("value-result", 1, 2)
    check("value-result mode: caller's x, y ARE swapped (2, 1), written back at return", (vrx, vry) == (2, 1), failures)

    if failures:
        print(f"\n{len(failures)} check(s) failed -- fix these first. No token issued.")
        return 1

    print("\nTesting the swap(x, x) aliasing case...\n")
    # Verified by hand-simulation before writing this harness: a true swap
    # of a value with itself is mathematically a no-op, and BOTH reference
    # and value-result mode correctly leave x unchanged here -- there is no
    # actual divergence for this specific scalar case (the two modes only
    # diverge under aliasing when the two parameters are used ASYMMETRICALLY,
    # not in a symmetric swap). Both are checked for correctness, not for
    # differing from each other.
    ref_x, _ = run_swap("reference", 5, 5, x_name="x", y_name="x")
    check("reference mode: swap(x, x) leaves x correctly unchanged (5)", ref_x == 5, failures)

    vr_x, _ = run_swap("value-result", 5, 5, x_name="x", y_name="x")
    check("value-result mode: swap(x, x) leaves x correctly unchanged (5)", vr_x == 5, failures)

    print("\nTesting asymmetric P(a, a) aliasing...\n")
    def run_asymmetric(mode: str) -> int:
        caller = Environment()
        caller.define("a", Cell(10))
        record = ActivationRecord("P", {}, Environment(), "call site", None, None)
        bind_parameters([("x", mode), ("y", mode)],
                        [Variable("a", 0), Variable("a", 0)], caller, record)
        # P(x, y) { x = x + 1; y = y + 1; }
        assign_through(record.locals_env, "x", evaluate(Variable("x", 0), record.locals_env) + 1)
        assign_through(record.locals_env, "y", evaluate(Variable("y", 0), record.locals_env) + 1)
        commit_value_result(record, caller)
        return evaluate(Variable("a", 0), caller)
    check("reference P(a,a): shared slot ends at 12", run_asymmetric("reference") == 12, failures)
    check("value-result P(a,a): left-to-right copy-back ends at 11", run_asymmetric("value-result") == 11, failures)

    print("\nTesting Cell identity and return-time visibility...\n")
    caller = Environment()
    caller.define("a", Cell(10))
    value_record = ActivationRecord("value", {}, Environment(), "call site", None, None)
    bind_parameters([("x", "value")], [Variable("a", 0)], caller, value_record)
    check("value mode allocates a separate Cell", value_record.locals_env.resolve("x") is not caller.resolve("a"), failures)
    assign_through(value_record.locals_env, "x", 15)
    check("value-mode assignment leaves caller at 10", evaluate(Variable("a", 0), caller) == 10, failures)

    reference_record = ActivationRecord("reference", {}, Environment(), "call site", None, None)
    bind_parameters([("x", "reference")], [Variable("a", 0)], caller, reference_record)
    check("reference mode shares the caller Cell", reference_record.locals_env.resolve("x") is caller.resolve("a"), failures)
    assign_through(reference_record.locals_env, "x", 12)
    check("reference write is visible before return", evaluate(Variable("a", 0), caller) == 12, failures)

    result_record = ActivationRecord("value-result", {}, Environment(), "call site", None, None)
    bind_parameters([("x", "value-result")], [Variable("a", 0)], caller, result_record)
    check("value-result starts with a private Cell", result_record.locals_env.resolve("x") is not caller.resolve("a"), failures)
    assign_through(result_record.locals_env, "x", 20)
    check("value-result write is hidden before return", evaluate(Variable("a", 0), caller) == 12, failures)
    commit_value_result(result_record, caller)
    check("value-result write appears at return", evaluate(Variable("a", 0), caller) == 20, failures)

    print("\nTesting closures capture the DEFINING environment, not a value snapshot...\n")
    loop_env = Environment()
    loop_env.define("i", Cell(0))
    body = Variable("i", 0)
    closures = []
    for i in range(3):
        assign_through(loop_env, "i", i)
        closures.append(Closure(FunctionDecl([], body), loop_env))
    assign_through(loop_env, "i", 3)  # simulates the loop's final post-increment state

    results = [c.call([], None) for c in closures]
    check("all three closures return the CURRENT (final) value of i, not a snapshot", results == [3, 3, 3], failures)

    print("\nTesting closures resolve free variables through defining_env, not caller_env...\n")
    outer_env = Environment()
    outer_env.define("captured", Cell(100))
    inner_closure = Closure(FunctionDecl([], Variable("captured", 0)), outer_env)
    unrelated_caller_env = Environment()
    unrelated_caller_env.define("captured", Cell(999))
    result = inner_closure.call([], unrelated_caller_env)
    check("Closure.call resolves free variables via defining_env, ignoring caller_env entirely", result == 100, failures)

    parameter_body = BinOp("+", Variable("captured", 0), Variable("offset", 0), 0)
    parameter_closure = Closure(FunctionDecl(["offset"], parameter_body), outer_env)
    check("closure binds a call argument beside the captured environment", parameter_closure.call([5], unrelated_caller_env) == 105, failures)
    check("a later closure call gets its own parameter value", parameter_closure.call([7], unrelated_caller_env) == 107, failures)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed. No token issued.")
        return 1

    print("PARAMETER_BINDING_VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

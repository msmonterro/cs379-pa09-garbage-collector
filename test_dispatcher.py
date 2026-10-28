"""
PA 8: The VTable Dispatcher -- verification suite.

Run: python test_dispatcher.py
Prints VTABLE_DISPATCH_VERIFIED only if every check below passes.
"""

import sys

from dispatcher import ClassDecl, USIObject, build_vtable, dispatch

ASSIGNMENT_ID = "PA08"


class MethodStub:
    """A small stand-in for PA 7's Closure.call(args, caller_env)."""

    def __init__(self, result):
        self.result = result
        self.last_call = None

    def call(self, args, caller_env):
        self.last_call = (args, caller_env)
        return self.result


def check(label: str, condition: bool, failures: list) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        failures.append(label)


def main() -> int:
    failures: list = []

    # class Animal { func speak() { return "..."; } func name() { return "Animal"; } }
    # class Dog extends Animal { func speak() { return "Woof"; } }
    # class Puppy extends Dog { func name() { return "Puppy"; } }
    animal_speak = MethodStub("...")
    animal_decl = ClassDecl("Animal", {"speak": animal_speak, "name": MethodStub("Animal")})
    dog_decl = ClassDecl("Dog", {"speak": MethodStub("Woof")})
    puppy_decl = ClassDecl("Puppy", {"name": MethodStub("Puppy")})

    print("Building the VTable chain...\n")
    animal_vt = build_vtable(animal_decl, parent_vtable=None)
    dog_vt = build_vtable(dog_decl, parent_vtable=animal_vt)
    puppy_vt = build_vtable(puppy_decl, parent_vtable=dog_vt)

    animal_obj = USIObject(animal_vt, {})
    dog_obj = USIObject(dog_vt, {})
    puppy_obj = USIObject(puppy_vt, {})

    print("Testing overrides and direct dispatch...\n")
    check("Animal.speak() == '...'", dispatch(animal_obj, "speak", [], None) == "...", failures)
    caller_env = object()
    check("dispatch forwards receiver, arguments, and caller environment to Closure.call", dispatch(animal_obj, "speak", [7], caller_env) == "..." and animal_speak.last_call == ([animal_obj, 7], caller_env), failures)
    check("Animal.name() == 'Animal'", dispatch(animal_obj, "name", [], None) == "Animal", failures)
    check("Dog.speak() == 'Woof' (overridden)", dispatch(dog_obj, "speak", [], None) == "Woof", failures)
    check("Puppy.name() == 'Puppy' (overridden)", dispatch(puppy_obj, "name", [], None) == "Puppy", failures)

    print("\nTesting inheritance fall-through (unoverridden methods)...\n")
    check("Dog.name() falls through to Animal's implementation ('Animal')", dispatch(dog_obj, "name", [], None) == "Animal", failures)
    check("Puppy.speak() falls through to Dog's implementation ('Woof')", dispatch(puppy_obj, "speak", [], None) == "Woof", failures)

    print("\nTesting that unoverridden slots share the EXACT SAME callable (no duplication)...\n")
    check("Dog's inherited 'name' slot IS Animal's 'name' closure (identity, not just equal)", dog_vt.resolve("name") is animal_vt.resolve("name"), failures)
    check("Puppy's inherited 'speak' slot IS Dog's 'speak' closure (identity)", puppy_vt.resolve("speak") is dog_vt.resolve("speak"), failures)

    print("\nTesting dynamic dispatch: a Puppy held through any reference still resolves as a Puppy...\n")
    # No static type system exists in this harness -- the point is that dispatch()
    # only ever consults obj's OWN vtable, never anything about how the reference
    # to obj was declared or passed around.
    some_variable_holding_a_puppy = puppy_obj
    check(
        "dispatching on a Puppy instance resolves Puppy's OWN methods regardless of the holding variable",
        dispatch(some_variable_holding_a_puppy, "speak", [], None) == "Woof" and dispatch(some_variable_holding_a_puppy, "name", [], None) == "Puppy",
        failures,
    )

    print("\nTesting the polymorphism loop from Part A, Question 3...\n")
    names = [dispatch(obj, "name", [], None) for obj in [animal_obj, dog_obj, puppy_obj]]
    check("[Animal, Dog, Puppy] .name() loop == ['Animal', 'Animal', 'Puppy']", names == ["Animal", "Animal", "Puppy"], failures)

    print("\nTesting undefined method raises a clear error...\n")
    try:
        dispatch(animal_obj, "fly", [], None)
        check("dispatching an undefined method raises an error", False, failures)
    except Exception as e:
        msg = str(e)
        check("error identifies both the class ('Animal') and the missing method ('fly')", "fly" in msg and "Animal" in msg, failures)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed. No token issued.")
        return 1

    print("VTABLE_DISPATCH_VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""PA 6: activation records and a last-in, first-out call stack."""

from typing import Dict, List, Optional

from symtable import Environment


class ActivationRecord:
    def __init__(
        self,
        function_name: str,
        parameters: Dict[str, object],
        locals_env: Environment,
        return_address: str,
        static_link: Optional["ActivationRecord"],
        dynamic_link: Optional["ActivationRecord"],
    ) -> None:
        self.function_name = function_name
        self.parameters = parameters
        self.locals_env = locals_env
        self.return_address = return_address
        self.static_link = static_link
        self.dynamic_link = dynamic_link


class CallStack:
    def __init__(self) -> None:
        self._records: List[ActivationRecord] = []

    def push(self, record: ActivationRecord) -> None:
        self._records.append(record)

    def pop(self) -> ActivationRecord:
        """Remove and return the most recent frame."""
        if not self._records:
            raise IndexError("Cannot pop an empty call stack.")
        record = self._records.pop()
        record.pending_writeback = []
        record.locals_env.close()
        return record

    def current(self) -> ActivationRecord:
        """Read the most recent frame without removing it."""
        if not self._records:
            raise IndexError("An empty call stack has no current frame.")
        return self._records[-1]

    def trace(self) -> List[str]:
        """Show live frames from the oldest call to the newest call."""
        return [
            f"{record.function_name}: parameters={record.parameters}, "
            f"return_address={record.return_address}"
            for record in self._records
        ]

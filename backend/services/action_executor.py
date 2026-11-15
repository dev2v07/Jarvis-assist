"""Controlled boundary for irreversible Windows actions.

The executor is deliberately tiny: it owns only actions that can terminate
or restart Windows. Callers must pass an explicit confirmation signal; tests
can inject a runner without executing a real system command.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence


class ActionConfirmationRequired(PermissionError):
    pass


class WindowsActionExecutor:
    POWER_COMMANDS: dict[str, tuple[str, ...]] = {
        "shutdown": ("shutdown", "/s", "/t", "1"),
        "reboot": ("shutdown", "/r", "/t", "1"),
    }

    def __init__(self, runner: Callable[[Sequence[str]], object] | None = None) -> None:
        self._runner = runner or self._run

    @staticmethod
    def _run(command: Sequence[str]) -> object:
        return subprocess.run(list(command), check=False, capture_output=True, text=True)

    def execute_power(self, intent: str, *, confirmed: bool) -> None:
        command = self.POWER_COMMANDS.get(str(intent).strip().lower())
        if command is None:
            raise ValueError(f"Unsupported Windows power action: {intent}")
        if not confirmed:
            raise ActionConfirmationRequired(f"Confirmation required for {intent}")
        self._runner(command)

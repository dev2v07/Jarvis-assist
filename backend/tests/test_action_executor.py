from __future__ import annotations

import unittest

from services.action_executor import ActionConfirmationRequired, WindowsActionExecutor


class ActionExecutorTests(unittest.TestCase):
    def test_power_action_requires_confirmation(self) -> None:
        calls: list[tuple[str, ...]] = []
        executor = WindowsActionExecutor(lambda command: calls.append(tuple(command)))
        with self.assertRaises(ActionConfirmationRequired):
            executor.execute_power("shutdown", confirmed=False)
        self.assertEqual(calls, [])

    def test_confirmed_power_action_uses_argument_list(self) -> None:
        calls: list[tuple[str, ...]] = []
        executor = WindowsActionExecutor(lambda command: calls.append(tuple(command)))
        executor.execute_power("reboot", confirmed=True)
        self.assertEqual(calls, [("shutdown", "/r", "/t", "1")])


if __name__ == "__main__":
    unittest.main()

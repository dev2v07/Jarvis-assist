from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from computer_control import get_weather_report
from services.response_router import ResponseRouter


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({
            "name": "Мурино",
            "main": {"temp": 7.4},
            "weather": [{"description": "пасмурно"}],
        }).encode("utf-8")


class WeatherCommandTests(unittest.TestCase):
    def test_weather_phrase_uses_command_route(self) -> None:
        decision = ResponseRouter().route("какая погода")
        self.assertEqual(decision.kind, "command")
        self.assertEqual(decision.intent, "weather")

    def test_weather_uses_openweather_and_configured_city(self) -> None:
        with patch.dict(os.environ, {"OPENWEATHER_API_KEY": "test-key", "WEATHER_CITY": "Мурино"}, clear=False), \
             patch("computer_control.urlopen", return_value=_FakeResponse()) as request:
            report = get_weather_report()

        self.assertIn("Мурино", report)
        self.assertIn("7 градусов", report)
        self.assertIn("пасмурно", report)
        request.assert_called_once()
        self.assertIn("q=%D0%9C%D1%83%D1%80%D0%B8%D0%BD%D0%BE", request.call_args.args[0].full_url)


if __name__ == "__main__":
    unittest.main()

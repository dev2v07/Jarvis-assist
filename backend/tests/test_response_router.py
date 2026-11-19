from services.response_router import ResponseRouter
from unittest.mock import patch
import computer_control


def test_known_phrase_uses_command_table():
    decision = ResponseRouter().route("открой браузер")
    assert decision.kind == "command"
    assert decision.intent == "open_browser"


def test_open_computer_uses_local_command_route():
    decision = ResponseRouter().route("открой компьютер")
    assert decision.kind == "command"
    assert decision.intent == "open_computer"


def test_open_browser_uses_non_blocking_windows_url_launch():
    with patch("computer_control.os.startfile") as startfile, patch("computer_control.webbrowser.open") as fallback:
        computer_control.open_browser()

    startfile.assert_called_once_with("https://google.com")
    fallback.assert_not_called()


def test_unknown_phrase_goes_to_conversation():
    decision = ResponseRouter().route("как сегодня настроение")
    assert decision.kind == "conversation"


def test_content_plan_about_music_is_not_an_os_command():
    decision = ResponseRouter().route("составь мне контент план по теме музыка")
    assert decision.kind == "conversation"
    assert decision.intent is None


def test_voice_command_phrases_map_to_specific_intents():
    assert ResponseRouter().route("закрой браузер").intent == "close_browser"
    assert ResponseRouter().route("открой яндекс музыку").intent == "open_music_service"
    assert ResponseRouter().route("выключи пк").intent == "shutdown"
    assert ResponseRouter().route("открой проводник").intent == "open_computer"
    assert ResponseRouter().route("закрой проводник").intent == "close_explorer"
    assert ResponseRouter().route("закрой компьютер").intent == "close_explorer"


def test_close_browser_uses_windows_process_boundary():
    completed = type("Completed", (), {"returncode": 0})()
    with patch("computer_control.subprocess.run", return_value=completed) as runner:
        assert computer_control.close_browser()

    assert runner.call_count == 5
    assert computer_control.get_last_command_feedback() == "Браузер закрыт."


def test_close_explorer_closes_folder_windows_without_killing_shell():
    completed = type("Completed", (), {"returncode": 0, "stdout": "2\n"})()
    with patch("computer_control.subprocess.run", return_value=completed) as runner:
        assert computer_control.close_explorer()

    command = runner.call_args.args[0]
    assert command[:4] == ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command"]
    assert "taskkill" not in command[-1].lower()
    assert computer_control.get_last_command_feedback() == "Окна Проводника закрыты."


def test_shared_generic_word_does_not_trigger_weather():
    decision = ResponseRouter().route("как сегодня настроение")
    assert decision.intent is None


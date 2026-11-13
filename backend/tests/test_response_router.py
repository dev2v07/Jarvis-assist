from services.response_router import ResponseRouter


def test_known_phrase_uses_command_table():
    decision = ResponseRouter().route("открой браузер")
    assert decision.kind == "command"
    assert decision.intent == "open_browser"


def test_unknown_phrase_goes_to_conversation():
    decision = ResponseRouter().route("как сегодня настроение")
    assert decision.kind == "conversation"


def test_shared_generic_word_does_not_trigger_weather():
    decision = ResponseRouter().route("как сегодня настроение")
    assert decision.intent is None


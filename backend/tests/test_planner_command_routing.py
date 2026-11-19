from agents.planner_agent import Planner


def _planner() -> Planner:
    return object.__new__(Planner)


def test_music_topic_request_stays_with_ai_model():
    steps = _planner().create_plan("составь мне контент план по теме музыка")
    assert steps == [
        {
            "title": "составь мне контент план по теме музыка",
            "route": "social",
            "action": "ai_response",
        }
    ]


def test_explicit_yandex_music_command_opens_service():
    steps = _planner().create_plan("открой яндекс музыку")
    assert steps[0]["route"] == "web"
    assert steps[0]["target"] == "https://music.yandex.ru"

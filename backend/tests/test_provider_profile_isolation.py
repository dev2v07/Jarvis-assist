import unittest
from unittest.mock import patch
from pathlib import Path

from services import config_service


class ProviderProfileIsolationTests(unittest.TestCase):
    def test_api_preserves_omitted_provider_fields(self):
        source = (Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8")
        save_route = source.split('@app.post("/settings/llm")', 1)[1].split(
            '@app.get("/settings/llm/models")', 1
        )[0]
        self.assertIn("exclude_unset=True", save_route)

    def test_freellmapi_uses_auto_when_no_explicit_model_exists(self):
        with patch.object(config_service, "read_runtime_config", return_value={
            "HEL_LLM_PROVIDER": "ollama",
            "HEL_OLLAMA_MODEL": "qwen3:8b",
            "HEL_FREELLMAPI_MODEL": "",
        }):
            settings = config_service.get_settings_bundle()
        profile = next(item for item in settings["profiles"] if item["id"] == "freellmapi")
        self.assertEqual(profile["model"], "AUTO")

    def test_saving_one_provider_preserves_other_models(self):
        current = {
            "HEL_LLM_PROVIDER": "ollama",
            "HEL_OLLAMA_BASE_URL": "http://127.0.0.1:11434",
            "HEL_OLLAMA_MODEL": "qwen3-coder:30b",
            "HEL_FREELLMAPI_BASE_URL": "http://127.0.0.1:11434",
            "HEL_FREELLMAPI_MODEL": "AUTO",
        }
        captured = {}
        with patch.object(config_service, "read_runtime_config", return_value=current), \
             patch.object(config_service, "update_runtime_config", side_effect=lambda updates: captured.update(updates)), \
             patch.object(config_service, "get_settings_bundle", return_value={}):
            config_service.save_llm_settings({
                "provider": "ollama",
                "ollama_model": "qwen3-coder:30b",
            })

        self.assertEqual(captured["HEL_OLLAMA_MODEL"], "qwen3-coder:30b")
        self.assertEqual(captured["HEL_FREELLMAPI_MODEL"], "AUTO")

    def test_saving_selected_ollama_model_persists_the_dropdown_value(self):
        current = {
            "HEL_LLM_PROVIDER": "ollama",
            "HEL_OLLAMA_BASE_URL": "http://127.0.0.1:11434",
            "HEL_OLLAMA_MODEL": "qwen3:8b",
        }
        selected_model = "qwen3:27b"
        captured = {}
        returned_bundle = {"provider": "ollama", "config": {"HEL_OLLAMA_MODEL": selected_model}}
        with patch.object(config_service, "read_runtime_config", return_value=current), \
             patch.object(config_service, "update_runtime_config", side_effect=lambda updates: captured.update(updates)), \
             patch.object(config_service, "get_settings_bundle", return_value=returned_bundle):
            result = config_service.save_llm_settings({
                "provider": "ollama",
                "ollama_model": selected_model,
            })

        self.assertEqual(captured["HEL_OLLAMA_MODEL"], selected_model)
        self.assertEqual(result["config"]["HEL_OLLAMA_MODEL"], selected_model)


if __name__ == "__main__":
    unittest.main()

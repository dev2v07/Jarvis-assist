from __future__ import annotations

from typing import Any

from config import (
    API_PORT,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    LLM_PROVIDER,
    LLM_REQUEST_TIMEOUT,
    LLM_MAX_RETRIES,
    NETWORK_REQUEST_TIMEOUT,
    NETWORK_MAX_RETRIES,
    CONFIG_HOME,
    read_runtime_config,
    update_runtime_config,
)

from services.llm_service import LocalLLMService, llm_service


# -----------------------------------------------------
# PROVIDERS
# -----------------------------------------------------

_ALLOWED_PROVIDERS = {
    "stub",
    "ollama",
    "openai",
    "openai_compatible",
}


def _normalize_provider(provider: str | None) -> str:

    value = str(provider or LLM_PROVIDER).strip().lower()

    if not value:
        value = "stub"

    if value not in _ALLOWED_PROVIDERS:

        raise ValueError("Unsupported provider")

    return value


# -----------------------------------------------------
# QUICK STATUS
# -----------------------------------------------------

def _quick_connection_status(provider: str, config: dict[str, Any]) -> dict[str, Any]:

    if provider == "stub":

        return {
            "ok": True,
            "provider": "stub",
            "message": "Используется встроенный stub-провайдер.",
        }

    if provider == "ollama":

        base = config.get("HEL_OLLAMA_BASE_URL") or OLLAMA_BASE_URL
        model = config.get("HEL_OLLAMA_MODEL") or OLLAMA_MODEL

        return {
            "ok": None,
            "provider": "ollama",
            "message": f"Ollama настроен: {base} / модель {model}",
        }

    has_api_key = bool((config.get("HEL_OPENAI_API_KEY") or "").strip())

    model = config.get("HEL_OPENAI_MODEL") or OPENAI_MODEL

    if has_api_key:

        return {
            "ok": None,
            "provider": provider,
            "message": f"API ключ сохранён. Модель {model}",
        }

    return {
        "ok": False,
        "provider": provider,
        "message": "API ключ не задан.",
    }


# -----------------------------------------------------
# SETTINGS
# -----------------------------------------------------

def _build_settings_from_runtime() -> dict[str, Any]:

    data = read_runtime_config(mask_secrets=False)

    provider = _normalize_provider(data.get("HEL_LLM_PROVIDER", LLM_PROVIDER))

    base_url = data.get("HEL_OPENAI_BASE_URL", OPENAI_BASE_URL)

    model = data.get("HEL_OPENAI_MODEL", OPENAI_MODEL)

    ollama_base_url = data.get("HEL_OLLAMA_BASE_URL", OLLAMA_BASE_URL)

    ollama_model = data.get("HEL_OLLAMA_MODEL", OLLAMA_MODEL)

    api_key = data.get("HEL_OPENAI_API_KEY", OPENAI_API_KEY)

    if api_key and len(api_key) > 8:

        masked = api_key[:4] + "..." + api_key[-4:]

    elif api_key:

        masked = "***"

    else:

        masked = ""

    return {

        "provider": provider,

        "openai_base_url": base_url,

        "openai_model": model,

        "openai_api_key_masked": masked,

        "ollama_base_url": ollama_base_url,

        "ollama_model": ollama_model,

        "runtime_env_path": str(CONFIG_HOME / ".env"),

        "api_port": API_PORT,

        "restart_required": False,
    }


def get_llm_settings() -> dict[str, Any]:

    return _build_settings_from_runtime()


# -----------------------------------------------------
# SETTINGS BUNDLE
# -----------------------------------------------------

def get_settings_bundle() -> dict[str, Any]:

    config = read_runtime_config(mask_secrets=False)

    provider = _normalize_provider(config.get("HEL_LLM_PROVIDER", LLM_PROVIDER))

    has_api_key = bool((config.get("HEL_OPENAI_API_KEY") or "").strip())

    needs_onboarding = provider in {"stub", "openai", "openai_compatible"} and not has_api_key

    if provider == "ollama":

        needs_onboarding = False

    return {

        "provider": provider,

        "runtime_env_path": str(CONFIG_HOME / ".env"),

        "config": config,

        "llm_connection": _quick_connection_status(provider, config),

        "needs_onboarding": needs_onboarding,

        "onboarding_message":
            "Выберите LLM провайдера и сохраните API ключ. "
            "Конфигурация будет автоматически сохранена.",
    }


# -----------------------------------------------------
# SAVE SETTINGS
# -----------------------------------------------------

def save_llm_settings(payload: dict[str, Any]) -> dict[str, Any]:

    provider = _normalize_provider(payload.get("provider", LLM_PROVIDER))

    updates = {

        "HEL_LLM_PROVIDER": provider,

        "HEL_OPENAI_BASE_URL":
            str(payload.get("openai_base_url", OPENAI_BASE_URL)).strip() or OPENAI_BASE_URL,

        "HEL_OPENAI_MODEL":
            str(payload.get("openai_model", OPENAI_MODEL)).strip() or OPENAI_MODEL,

        "HEL_OLLAMA_BASE_URL":
            str(payload.get("ollama_base_url", OLLAMA_BASE_URL)).strip() or OLLAMA_BASE_URL,

        "HEL_OLLAMA_MODEL":
            str(payload.get("ollama_model", OLLAMA_MODEL)).strip() or OLLAMA_MODEL,

        "HEL_LLM_REQUEST_TIMEOUT":
            str(int(payload.get("llm_request_timeout", LLM_REQUEST_TIMEOUT) or LLM_REQUEST_TIMEOUT)),

        "HEL_LLM_MAX_RETRIES":
            str(int(payload.get("llm_max_retries", LLM_MAX_RETRIES) or LLM_MAX_RETRIES)),

        "HEL_NETWORK_REQUEST_TIMEOUT":
            str(int(payload.get("network_request_timeout", NETWORK_REQUEST_TIMEOUT) or NETWORK_REQUEST_TIMEOUT)),

        "HEL_NETWORK_MAX_RETRIES":
            str(int(payload.get("network_max_retries", NETWORK_MAX_RETRIES) or NETWORK_MAX_RETRIES)),
    }

    api_key = payload.get("openai_api_key")

    if api_key is not None:

        cleaned = str(api_key).strip()

        if cleaned:

            updates["HEL_OPENAI_API_KEY"] = cleaned

    update_runtime_config(updates)

    llm_service.reload_config()

    return get_settings_bundle()


# -----------------------------------------------------
# TEST SETTINGS
# -----------------------------------------------------

async def test_llm_settings(payload: dict[str, Any]) -> dict[str, Any]:

    provider = _normalize_provider(payload.get("provider", LLM_PROVIDER))

    service = LocalLLMService()

    overrides = {

        "HEL_LLM_PROVIDER": provider,

        "HEL_OPENAI_BASE_URL":
            str(payload.get("openai_base_url", OPENAI_BASE_URL)).strip() or OPENAI_BASE_URL,

        "HEL_OPENAI_MODEL":
            str(payload.get("openai_model", OPENAI_MODEL)).strip() or OPENAI_MODEL,

        "HEL_OLLAMA_BASE_URL":
            str(payload.get("ollama_base_url", OLLAMA_BASE_URL)).strip() or OLLAMA_BASE_URL,

        "HEL_OLLAMA_MODEL":
            str(payload.get("ollama_model", OLLAMA_MODEL)).strip() or OLLAMA_MODEL,

        "HEL_OPENAI_API_KEY":
            str(payload.get("openai_api_key", "")).strip() or OPENAI_API_KEY,

        "HEL_LLM_REQUEST_TIMEOUT":
            str(int(payload.get("llm_request_timeout", LLM_REQUEST_TIMEOUT) or LLM_REQUEST_TIMEOUT)),

        "HEL_LLM_MAX_RETRIES":
            str(int(payload.get("llm_max_retries", LLM_MAX_RETRIES) or LLM_MAX_RETRIES)),
    }

    return await service.test_connection_with_overrides(overrides)
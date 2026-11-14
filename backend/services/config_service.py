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
from services.provider_adapters import (
    SUPPORTED_PROVIDERS,
    build_provider_adapter,
    normalize_provider_name,
)


# -----------------------------------------------------
# PROVIDERS
# -----------------------------------------------------

_ALLOWED_PROVIDERS = set(SUPPORTED_PROVIDERS)


def _normalize_provider(provider: str | None) -> str:

    value = normalize_provider_name(provider or LLM_PROVIDER)

    if not value:
        value = "stub"

    if value not in _ALLOWED_PROVIDERS:

        raise ValueError("Unsupported provider")

    return value


# -----------------------------------------------------
# QUICK STATUS
# -----------------------------------------------------

def _quick_connection_status(provider: str, config: dict[str, Any]) -> dict[str, Any]:
    adapter = build_provider_adapter(provider, _adapter_config(config))
    status = adapter.configuration_status()
    if provider == "stub":
        message = "Используется встроенный stub-провайдер."
    elif status["configured"]:
        message = f"{provider} настроен. Модель: {status.get('model') or 'по умолчанию'}."
    else:
        missing = ", ".join(status.get("missing", [])) or "конфигурация"
        message = f"{provider} не настроен: {missing}."
    return {
        "ok": bool(status["configured"]),
        "provider": provider,
        "model": status.get("model"),
        "message": message,
        "implemented": bool(status.get("implemented")),
        "missing": status.get("missing", []),
    }


def _adapter_config(config: dict[str, Any]) -> dict[str, Any]:
    """Merge persisted runtime values with safe provider defaults."""

    return {
        **config,
        "HEL_OLLAMA_BASE_URL": config.get("HEL_OLLAMA_BASE_URL") or OLLAMA_BASE_URL,
        "HEL_OLLAMA_MODEL": config.get("HEL_OLLAMA_MODEL") or OLLAMA_MODEL,
        "HEL_OPENAI_BASE_URL": config.get("HEL_OPENAI_BASE_URL") or OPENAI_BASE_URL,
        "HEL_OPENAI_MODEL": config.get("HEL_OPENAI_MODEL") or OPENAI_MODEL,
        "HEL_OPENAI_API_KEY": config.get("HEL_OPENAI_API_KEY") or OPENAI_API_KEY,
        "HEL_DEEPSEEK_BASE_URL": config.get("HEL_DEEPSEEK_BASE_URL") or "https://api.deepseek.com",
        "HEL_DEEPSEEK_MODEL": config.get("HEL_DEEPSEEK_MODEL") or "deepseek-flash",
        "HEL_DEEPSEEK_API_KEY": config.get("HEL_DEEPSEEK_API_KEY") or "",
    }


def _mask_secret(value: str) -> str:
    value = str(value or "")
    if len(value) > 8:
        return value[:4] + "..." + value[-4:]
    return "***" if value else ""


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

    return {

        "provider": provider,

        "openai_base_url": base_url,

        "openai_model": model,

        "openai_api_key_masked": _mask_secret(api_key),

        "deepseek_base_url": data.get("HEL_DEEPSEEK_BASE_URL", "https://api.deepseek.com"),

        "deepseek_model": data.get("HEL_DEEPSEEK_MODEL", "deepseek-flash"),

        "deepseek_api_key_masked": _mask_secret(data.get("HEL_DEEPSEEK_API_KEY", "")),

        "ollama_base_url": ollama_base_url,

        "ollama_model": ollama_model,

        "codex_base_url": data.get("HEL_CODEX_BASE_URL", ""),

        "codex_model": data.get("HEL_CODEX_MODEL", ""),

        "codex_api_key_masked": _mask_secret(data.get("HEL_CODEX_API_KEY", "")),

        "claude_base_url": data.get("HEL_ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),

        "claude_model": data.get("HEL_ANTHROPIC_MODEL", ""),

        "claude_api_key_masked": _mask_secret(data.get("HEL_ANTHROPIC_API_KEY", "")),

        "freellmapi_base_url": data.get("HEL_FREELLMAPI_BASE_URL", ""),

        "freellmapi_model": data.get("HEL_FREELLMAPI_MODEL", ""),

        "freellmapi_api_key_masked": _mask_secret(data.get("HEL_FREELLMAPI_API_KEY", "")),

        "supported_providers": list(SUPPORTED_PROVIDERS),

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

    raw_config = read_runtime_config(mask_secrets=False)

    provider = _normalize_provider(raw_config.get("HEL_LLM_PROVIDER", LLM_PROVIDER))

    provider_status = _quick_connection_status(provider, raw_config)
    needs_onboarding = not provider_status["ok"]

    profiles = []
    profile_specs = (
        ("ollama", "Ollama", "ollama_base_url", "ollama_model", ""),
        ("openai", "OpenAI", "openai_base_url", "openai_model", "openai_api_key_masked"),
        ("openai_compatible", "OpenAI-compatible", "openai_base_url", "openai_model", "openai_api_key_masked"),
        ("deepseek", "DeepSeek", "deepseek_base_url", "deepseek_model", "deepseek_api_key_masked"),
        ("codex", "Codex", "codex_base_url", "codex_model", "codex_api_key_masked"),
        ("claude", "Claude", "claude_base_url", "claude_model", "claude_api_key_masked"),
        ("freellmapi", "FreeLLMAPI", "freellmapi_base_url", "freellmapi_model", "freellmapi_api_key_masked"),
    )
    settings = _build_settings_from_runtime()
    for provider_id, label, base_key, model_key, secret_key in profile_specs:
        profiles.append({
            "id": provider_id,
            "label": label,
            "base_url": settings.get(base_key, ""),
            "model": settings.get(model_key, ""),
            "api_key_masked": settings.get(secret_key, "") if secret_key else "",
            "active": provider_id == provider,
        })

    return {

        "provider": provider,

        "runtime_env_path": str(CONFIG_HOME / ".env"),

        "config": read_runtime_config(mask_secrets=True),

        "llm_connection": provider_status,

        "provider_status": provider_status,

        "supported_providers": list(SUPPORTED_PROVIDERS),

        # Safe, non-secret connection profiles for the desktop settings UI.
        # API keys are masked and never returned in plaintext.
        "profiles": profiles,

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

        "HEL_DEEPSEEK_BASE_URL":
            str(payload.get("deepseek_base_url", "https://api.deepseek.com")).strip() or "https://api.deepseek.com",

        "HEL_DEEPSEEK_MODEL":
            str(payload.get("deepseek_model", "deepseek-flash")).strip() or "deepseek-flash",

        "HEL_OLLAMA_BASE_URL":
            str(payload.get("ollama_base_url", OLLAMA_BASE_URL)).strip() or OLLAMA_BASE_URL,

        "HEL_OLLAMA_MODEL":
            str(payload.get("ollama_model", OLLAMA_MODEL)).strip() or OLLAMA_MODEL,

        "HEL_CODEX_BASE_URL":
            str(payload.get("codex_base_url", "")).strip(),

        "HEL_CODEX_MODEL":
            str(payload.get("codex_model", "")).strip(),

        "HEL_ANTHROPIC_BASE_URL":
            str(payload.get("claude_base_url", "https://api.anthropic.com/v1")).strip()
            or "https://api.anthropic.com/v1",

        "HEL_ANTHROPIC_MODEL":
            str(payload.get("claude_model", "")).strip(),

        "HEL_FREELLMAPI_BASE_URL":
            str(payload.get("freellmapi_base_url", "")).strip(),

        "HEL_FREELLMAPI_MODEL":
            str(payload.get("freellmapi_model", "")).strip(),

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

    for payload_key, env_key in (
        ("codex_api_key", "HEL_CODEX_API_KEY"),
        ("claude_api_key", "HEL_ANTHROPIC_API_KEY"),
        ("freellmapi_api_key", "HEL_FREELLMAPI_API_KEY"),
        ("deepseek_api_key", "HEL_DEEPSEEK_API_KEY"),
    ):
        secret = payload.get(payload_key)
        if secret is not None and str(secret).strip():
            updates[env_key] = str(secret).strip()

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

        "HEL_DEEPSEEK_BASE_URL":
            str(payload.get("deepseek_base_url", "https://api.deepseek.com")).strip() or "https://api.deepseek.com",

        "HEL_DEEPSEEK_MODEL":
            str(payload.get("deepseek_model", "deepseek-flash")).strip() or "deepseek-flash",

        "HEL_DEEPSEEK_API_KEY":
            str(payload.get("deepseek_api_key") or "").strip(),

        "HEL_OLLAMA_BASE_URL":
            str(payload.get("ollama_base_url", OLLAMA_BASE_URL)).strip() or OLLAMA_BASE_URL,

        "HEL_OLLAMA_MODEL":
            str(payload.get("ollama_model", OLLAMA_MODEL)).strip() or OLLAMA_MODEL,

        "HEL_CODEX_API_KEY":
            str(payload.get("codex_api_key", "")).strip(),

        "HEL_CODEX_MODEL":
            str(payload.get("codex_model", "")).strip(),

        "HEL_ANTHROPIC_API_KEY":
            str(payload.get("claude_api_key", "")).strip(),

        "HEL_ANTHROPIC_MODEL":
            str(payload.get("claude_model", "")).strip(),

        "HEL_FREELLMAPI_API_KEY":
            str(payload.get("freellmapi_api_key", "")).strip(),

        "HEL_FREELLMAPI_BASE_URL":
            str(payload.get("freellmapi_base_url", "")).strip(),

        "HEL_FREELLMAPI_MODEL":
            str(payload.get("freellmapi_model", "")).strip(),

        "HEL_OPENAI_API_KEY":
            str(payload.get("openai_api_key", "")).strip() or OPENAI_API_KEY,

        "HEL_LLM_REQUEST_TIMEOUT":
            str(int(payload.get("llm_request_timeout", LLM_REQUEST_TIMEOUT) or LLM_REQUEST_TIMEOUT)),

        "HEL_LLM_MAX_RETRIES":
            str(int(payload.get("llm_max_retries", LLM_MAX_RETRIES) or LLM_MAX_RETRIES)),
    }

    return await service.test_connection_with_overrides(overrides)

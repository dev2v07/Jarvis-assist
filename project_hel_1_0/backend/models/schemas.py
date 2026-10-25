from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    mode: str = 'general'


class ChatAcceptedResponse(BaseModel):
    request_id: str
    status: str


class RequestStatusResponse(BaseModel):
    request_id: str
    status: str
    goal: str
    mode: str
    events: List[Dict[str, Any]] = Field(default_factory=list)
    plan: List[Dict[str, Any] | str] = Field(default_factory=list)
    current_step: Optional[str] = None
    completed_steps: List[Dict[str, Any]] = Field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
    permission_request: Optional[Dict[str, Any]] = None
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)


class PermissionResponse(BaseModel):
    request_id: str
    allowed: bool


class PlanApprovalRequest(BaseModel):
    original_msg_id: str
    approved: bool


class HealthResponse(BaseModel):
    status: str
    agents: List[str]
    model_backend: str


class ModeInfo(BaseModel):
    key: str
    title: str
    description: str
    icon: Optional[str] = None


class LLMSettingsUpdate(BaseModel):
    provider: str = 'stub'
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None


class LLMSettingsResponse(BaseModel):
    provider: str
    openai_base_url: str
    openai_model: str
    openai_api_key_masked: str = ''
    ollama_base_url: str
    ollama_model: str
    runtime_env_path: str
    api_port: int
    restart_required: bool = True


class SettingsResponse(BaseModel):
    provider: str
    runtime_env_path: str
    config: Dict[str, Any]
    llm_connection: Dict[str, Any] = Field(default_factory=dict)


class SettingsUpdateRequest(BaseModel):
    provider: str = 'stub'
    ollama_base_url: str = 'http://127.0.0.1:11434'
    ollama_model: str = 'qwen2.5:7b-q4_K_M'
    openai_base_url: str = 'https://api.openai.com/v1'
    openai_model: str = 'gpt-4o-mini'
    openai_api_key: str = ''
    llm_request_timeout: int = 45
    llm_max_retries: int = 2
    network_request_timeout: int = 20
    network_max_retries: int = 2

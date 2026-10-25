from pydantic import BaseModel, Field
from typing import List, Optional

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    mode: str = 'general'

class ChatResponse(BaseModel):
    response: str
    request_id: str

class PermissionResponse(BaseModel):
    request_id: str
    allowed: bool

class PlanApprovalRequest(BaseModel):
    original_msg_id: str
    approved: bool

class PlanPayload(BaseModel):
    goal: str
    steps: List[str]
    original_msg_id: str

class HealthResponse(BaseModel):
    status: str
    agents: List[str]
    model_backend: str

class ModeInfo(BaseModel):
    key: str
    title: str
    description: str
    icon: Optional[str] = None

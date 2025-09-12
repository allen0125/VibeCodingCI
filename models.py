from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class LinearWebhookPayload(BaseModel):
    action: str
    data: Dict[str, Any]
    type: str
    url: Optional[str] = None
    created_at: Optional[str] = None

class WebhookEventResponse(BaseModel):
    id: int
    event_type: str
    linear_id: str
    action: str
    data: Optional[Dict[str, Any]]
    created_at: datetime
    raw_payload: Optional[str]

    class Config:
        from_attributes = True

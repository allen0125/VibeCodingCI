from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON
from typing import Optional, Dict, Any
from datetime import datetime

class LinearWebhookPayload(SQLModel):
    """Linear Webhook 请求载荷模型"""
    action: str
    data: Dict[str, Any]
    type: str
    url: Optional[str] = None
    created_at: Optional[str] = None

class WebhookEvent(SQLModel, table=True):
    """Webhook 事件数据库模型"""
    __tablename__ = "webhook_events"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    event_type: str = Field(max_length=100)
    linear_id: str = Field(max_length=100)
    action: str = Field(max_length=50)
    data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    raw_payload: Optional[str] = None

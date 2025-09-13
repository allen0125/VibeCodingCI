from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON
from typing import Optional, Dict, Any
from datetime import datetime

class LinearWebhookPayload(SQLModel):
    """Linear Webhook 请求载荷模型 - 2025 最新结构"""
    action: str = Field(description="操作类型: create, update, remove")
    type: str = Field(description="实体类型: Issue, Comment, Project 等")
    data: Dict[str, Any] = Field(description="实体的完整数据")
    url: Optional[str] = Field(default=None, description="实体的 Linear URL")
    created_at: Optional[str] = Field(default=None, alias="createdAt", description="操作发生时间")
    updated_from: Optional[Dict[str, Any]] = Field(default=None, alias="updatedFrom", description="更新前的值")
    webhook_timestamp: Optional[int] = Field(default=None, alias="webhookTimestamp", description="Webhook 发送时间戳")
    webhook_id: Optional[str] = Field(default=None, alias="webhookId", description="Webhook 唯一标识")

class WebhookEvent(SQLModel, table=True):
    """Webhook 事件数据库模型 - 2025 最新结构"""
    __tablename__ = "webhook_events"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    linear_delivery: Optional[str] = Field(default=None, max_length=100, description="Linear-Delivery UUID")
    linear_event: str = Field(max_length=100, description="Linear-Event 类型")
    linear_signature: Optional[str] = Field(default=None, max_length=200, description="Linear-Signature")
    action: str = Field(max_length=50, description="操作类型")
    entity_type: str = Field(max_length=100, description="实体类型")
    entity_id: str = Field(max_length=100, description="实体 ID")
    entity_url: Optional[str] = Field(default=None, description="实体 URL")
    data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON), description="实体数据")
    updated_from: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON), description="更新前的值")
    webhook_timestamp: Optional[int] = Field(default=None, description="Webhook 时间戳")
    webhook_id: Optional[str] = Field(default=None, max_length=100, description="Webhook ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="记录创建时间")
    raw_payload: Optional[str] = Field(default=None, description="原始载荷")

from fastapi import FastAPI, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
import json

from database import get_session, create_db_and_tables
from models import LinearWebhookPayload, WebhookEvent

app = FastAPI(title="Linear Webhook Handler", version="2.0.0")

# 创建数据库表
create_db_and_tables()

@app.post("/webhook/linear")
async def handle_linear_webhook(
    payload: LinearWebhookPayload,
    session: Session = Depends(get_session)
):
    """处理 Linear webhook 请求"""
    try:
        # 提取基本信息
        event_type = payload.type
        action = payload.action
        data = payload.data
        
        # 获取 Linear ID
        linear_id = data.get("id", "unknown")
        
        # 创建数据库记录
        webhook_event = WebhookEvent(
            event_type=event_type,
            linear_id=linear_id,
            action=action,
            data=data,  # 直接使用字典，SQLModel 会自动处理
            raw_payload=json.dumps(payload.model_dump())
        )
        
        session.add(webhook_event)
        session.commit()
        session.refresh(webhook_event)
        
        return {
            "status": "success",
            "message": f"Webhook event {action} for {event_type} processed",
            "event_id": webhook_event.id
        }
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"处理 webhook 时出错: {str(e)}")

@app.get("/webhook/events")
async def get_webhook_events(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session)
):
    """获取 webhook 事件列表"""
    statement = select(WebhookEvent).offset(skip).limit(limit)
    events = session.exec(statement).all()
    return events

@app.get("/webhook/events/{event_id}")
async def get_webhook_event(
    event_id: int,
    session: Session = Depends(get_session)
):
    """获取特定 webhook 事件"""
    statement = select(WebhookEvent).where(WebhookEvent.id == event_id)
    event = session.exec(statement).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件未找到")
    return event

@app.get("/")
async def root():
    return {"message": "Linear Webhook Handler API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

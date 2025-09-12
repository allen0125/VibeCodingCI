from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, create_tables, WebhookEvent
from models import LinearWebhookPayload, WebhookEventResponse
import json

app = FastAPI(title="Linear Webhook Handler", version="1.0.0")

# 创建数据库表
create_tables()

@app.post("/webhook/linear")
async def handle_linear_webhook(
    payload: LinearWebhookPayload,
    db: Session = Depends(get_db)
):
    """处理 Linear webhook 请求"""
    try:
        # 提取基本信息
        event_type = payload.type
        action = payload.action
        data = payload.data
        
        # 获取 Linear ID（根据事件类型不同，ID 字段可能不同）
        linear_id = data.get("id", "unknown")
        
        # 创建数据库记录
        webhook_event = WebhookEvent(
            event_type=event_type,
            linear_id=linear_id,
            action=action,
            data=data,
            raw_payload=json.dumps(payload.dict())
        )
        
        db.add(webhook_event)
        db.commit()
        db.refresh(webhook_event)
        
        return {
            "status": "success",
            "message": f"Webhook event {action} for {event_type} processed",
            "event_id": webhook_event.id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"处理 webhook 时出错: {str(e)}")

@app.get("/webhook/events")
async def get_webhook_events(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取 webhook 事件列表"""
    events = db.query(WebhookEvent).offset(skip).limit(limit).all()
    return events

@app.get("/webhook/events/{event_id}")
async def get_webhook_event(
    event_id: int,
    db: Session = Depends(get_db)
):
    """获取特定 webhook 事件"""
    event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件未找到")
    return event

@app.get("/")
async def root():
    return {"message": "Linear Webhook Handler API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

from fastapi import FastAPI, Depends, HTTPException, Request
from sqlmodel import Session, select
from typing import List
import json
import hmac
import hashlib
import os

from database import get_session, create_db_and_tables
from models import LinearWebhookPayload, WebhookEvent

app = FastAPI(title="Linear Webhook Handler", version="2.0.0")

# 创建数据库表
create_db_and_tables()

def verify_linear_signature(signature: str, body: bytes) -> bool:
    """验证 Linear webhook 签名"""
    secret = os.getenv("LINEAR_WEBHOOK_SECRET")
    if not secret:
        return True  # 如果没有配置密钥，跳过验证
    
    if not signature or not signature.startswith("sha256="):
        return False
    
    expected = hmac.new(
        secret.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature[7:], expected)

@app.post("/webhook/linear")
async def handle_linear_webhook(
    request: Request,
    session: Session = Depends(get_session)
):
    """处理 Linear webhook 请求 - 2025 最新结构"""
    try:
        # 获取原始请求体进行签名验证
        body = await request.body()
        linear_signature = request.headers.get("Linear-Signature")
        
        # 验证签名
        if not verify_linear_signature(linear_signature, body):
            raise HTTPException(status_code=401, detail="签名验证失败")
        
        # 解析 JSON 载荷
        payload_data = json.loads(body.decode('utf-8'))
        payload = LinearWebhookPayload(**payload_data)
        
        # 提取 HTTP 头部信息
        linear_delivery = request.headers.get("Linear-Delivery")
        linear_event = request.headers.get("Linear-Event")
        
        # 提取基本信息
        entity_type = payload.type
        action = payload.action
        data = payload.data
        
        # 获取实体 ID
        entity_id = data.get("id", "unknown")
        
        # 创建数据库记录
        webhook_event = WebhookEvent(
            linear_delivery=linear_delivery,
            linear_event=linear_event,
            linear_signature=linear_signature,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_url=payload.url,
            data=data,
            updated_from=payload.updated_from,
            webhook_timestamp=payload.webhook_timestamp,
            webhook_id=payload.webhook_id,
            raw_payload=json.dumps(payload.model_dump())
        )
        
        session.add(webhook_event)
        session.commit()
        session.refresh(webhook_event)
        
        return {
            "status": "success",
            "message": f"Webhook event {action} for {entity_type} processed",
            "event_id": webhook_event.id,
            "linear_delivery": linear_delivery
        }
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"处理 webhook 时出错: {str(e)}")

@app.get("/webhook/events")
async def get_webhook_events(
    skip: int = 0,
    limit: int = 100,
    entity_type: str = None,
    action: str = None,
    session: Session = Depends(get_session)
):
    """获取 webhook 事件列表 - 支持过滤"""
    statement = select(WebhookEvent)
    
    # 添加过滤条件
    if entity_type:
        statement = statement.where(WebhookEvent.entity_type == entity_type)
    if action:
        statement = statement.where(WebhookEvent.action == action)
    
    # 按创建时间降序排列
    statement = statement.order_by(WebhookEvent.created_at.desc())
    statement = statement.offset(skip).limit(limit)
    
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

@app.get("/webhook/events/by-linear/{linear_delivery}")
async def get_webhook_event_by_linear_delivery(
    linear_delivery: str,
    session: Session = Depends(get_session)
):
    """根据 Linear Delivery ID 获取事件"""
    statement = select(WebhookEvent).where(WebhookEvent.linear_delivery == linear_delivery)
    event = session.exec(statement).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件未找到")
    return event

@app.get("/")
async def root():
    return {"message": "Linear Webhook Handler API", "status": "running"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "signature_verification": os.getenv("LINEAR_WEBHOOK_SECRET") is not None
    }

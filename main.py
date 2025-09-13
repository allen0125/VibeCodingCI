from fastapi import FastAPI, Depends, HTTPException, Request
from sqlmodel import Session, select
from typing import List
import json
import hmac
import hashlib
import os
import logging

from database import get_session, create_db_and_tables
from models import LinearWebhookPayload, WebhookEvent

app = FastAPI(title="Linear Webhook Handler", version="2.0.0")

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建数据库表
create_db_and_tables()

def verify_linear_signature(signature: str, body: bytes) -> bool:
    """验证 Linear webhook 签名"""
    secret = os.getenv("LINEAR_WEBHOOK_SECRET")
    if not secret:
        logger.warning("未配置 LINEAR_WEBHOOK_SECRET，跳过签名验证")
        return True  # 如果没有配置密钥，跳过验证
    
    if not signature:
        logger.error("缺少 Linear-Signature 头部")
        return False
    
    # Linear 使用纯十六进制签名，没有 sha256= 前缀
    expected = hmac.new(
        secret.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()
    
    is_valid = hmac.compare_digest(signature, expected)
    
    if not is_valid:
        logger.error(f"签名不匹配 - 期望: {expected[:16]}..., 收到: {signature[:16]}...")
    else:
        logger.info("签名验证成功")
    
    return is_valid

@app.post("/webhook/linear")
async def handle_linear_webhook(
    request: Request,
    session: Session = Depends(get_session)
):
    """处理 Linear webhook 请求 - 2025 最新结构"""
    try:
        logger.info("收到 Linear webhook 请求")
        
        # 获取原始请求体进行签名验证
        body = await request.body()
        logger.info(f"请求体大小: {len(body)} 字节")
        
        linear_signature = request.headers.get("Linear-Signature")
        logger.info(f"Linear-Signature: {linear_signature}")
        
        # 验证签名
        if not verify_linear_signature(linear_signature, body):
            logger.error("签名验证失败")
            raise HTTPException(status_code=401, detail="签名验证失败")
        
        logger.info("签名验证通过")
        
        # 解析 JSON 载荷
        try:
            payload_data = json.loads(body.decode('utf-8'))
            logger.info(f"JSON 解析成功，载荷键: {list(payload_data.keys())}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            raise HTTPException(status_code=400, detail=f"无效的 JSON 载荷: {str(e)}")
        
        try:
            payload = LinearWebhookPayload(**payload_data)
            logger.info(f"载荷验证成功: {payload.action} - {payload.type}")
        except Exception as e:
            logger.error(f"载荷验证失败: {e}")
            raise HTTPException(status_code=400, detail=f"载荷格式错误: {str(e)}")
        
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
        
        logger.info(f"Webhook 事件处理成功: {action} - {entity_type} - {entity_id}")
        return {
            "status": "success",
            "message": f"Webhook event {action} for {entity_type} processed",
            "event_id": webhook_event.id,
            "linear_delivery": linear_delivery
        }
        
    except HTTPException as e:
        logger.error(f"HTTP 异常: {e.status_code} - {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"处理 webhook 时发生未知错误: {str(e)}", exc_info=True)
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

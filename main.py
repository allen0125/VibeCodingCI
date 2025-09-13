from fastapi import FastAPI, Depends, HTTPException, Request
from sqlmodel import Session, select
from typing import List
import json
import hmac
import hashlib
import os
import logging
import subprocess
import tempfile
import uuid
from pathlib import Path
from dotenv import load_dotenv

from database import get_session, create_db_and_tables
from models import LinearWebhookPayload, WebhookEvent

# 优先加载 .env 文件中的环境变量
load_dotenv()

def format_linear_event_for_aider(event_data: dict) -> str:
    """将 Linear 事件格式化为 aider prompt"""
    action = event_data.get("action", "")
    entity_type = event_data.get("entity_type", "")
    data = event_data.get("data", {})
    
    if entity_type == "Issue":
        return format_issue_for_aider(action, data)
    elif entity_type == "Comment":
        return format_comment_for_aider(action, data)
    elif entity_type == "Reaction":
        return format_reaction_for_aider(action, data)
    else:
        return f"Linear {entity_type} {action}: {json.dumps(data, ensure_ascii=False, indent=2)}"

def format_issue_for_aider(action: str, data: dict) -> str:
    """格式化 Issue 事件为 aider prompt"""
    title = data.get("title", "")
    identifier = data.get("identifier", "")
    description = data.get("description", "")
    state = data.get("state", {})
    team = data.get("team", {})
    assignee = data.get("assignee", {})
    url = data.get("url", "")
    
    prompt = f"Linear Issue {action.upper()}: {identifier} - {title}\n"
    prompt += f"Team: {team.get('name', 'Unknown')} ({team.get('key', '')})\n"
    prompt += f"State: {state.get('name', 'Unknown')}\n"
    
    if assignee:
        prompt += f"Assignee: {assignee.get('name', 'Unknown')}\n"
    
    if description:
        prompt += f"Description:\n{description}\n"
    
    prompt += f"URL: {url}\n"
    
    return prompt

def format_comment_for_aider(action: str, data: dict) -> str:
    """格式化 Comment 事件为 aider prompt"""
    body = data.get("body", "")
    user = data.get("user", {})
    issue = data.get("issue", {})
    
    prompt = f"Linear Comment {action.upper()}\n"
    prompt += f"User: {user.get('name', 'Unknown')}\n"
    prompt += f"Issue: {issue.get('identifier', 'Unknown')} - {issue.get('title', '')}\n"
    prompt += f"Comment:\n{body}\n"
    
    # 添加 Issue 的更多上下文信息
    if issue:
        prompt += f"\nIssue Context:\n"
        prompt += f"- Issue ID: {issue.get('id', 'Unknown')}\n"
        prompt += f"- Issue URL: {issue.get('url', 'Unknown')}\n"
        if issue.get('state'):
            prompt += f"- Issue State: {issue['state'].get('name', 'Unknown')}\n"
        if issue.get('team'):
            prompt += f"- Team: {issue['team'].get('name', 'Unknown')} ({issue['team'].get('key', '')})\n"
    
    return prompt

def format_reaction_for_aider(action: str, data: dict) -> str:
    """格式化 Reaction 事件为 aider prompt"""
    emoji = data.get("emoji", "")
    user = data.get("user", {})
    comment = data.get("comment", {})
    
    prompt = f"Linear Reaction {action.upper()}: {emoji}\n"
    prompt += f"User: {user.get('name', 'Unknown')}\n"
    prompt += f"Comment: {comment.get('body', '')[:100]}{'...' if len(comment.get('body', '')) > 100 else ''}\n"
    
    return prompt

def create_branch_and_pr(woodenman_path: str, branch_name: str, pr_title: str, pr_body: str) -> dict:
    """创建新分支并推送，然后创建 PR"""
    try:
        logger.info(f"创建分支 {branch_name} 并推送")
        
        # 切换到 WoodenMan 目录
        original_cwd = os.getcwd()
        os.chdir(woodenman_path)
        
        try:
            # 1. 确保在 main 分支并拉取最新代码
            subprocess.run(["git", "checkout", "main"], check=True, capture_output=True, text=True)
            subprocess.run(["git", "pull", "origin", "main"], check=True, capture_output=True, text=True)
            
            # 2. 创建新分支
            subprocess.run(["git", "checkout", "-b", branch_name], check=True, capture_output=True, text=True)
            logger.info(f"创建分支 {branch_name} 成功")
            
            # 3. 推送新分支到远程
            subprocess.run(["git", "push", "-u", "origin", branch_name], check=True, capture_output=True, text=True)
            logger.info(f"推送分支 {branch_name} 成功")
            
            # 4. 创建 PR (使用 GitHub CLI)
            pr_cmd = [
                "gh", "pr", "create",
                "--title", pr_title,
                "--body", pr_body,
                "--head", branch_name,
                "--base", "main",
                "--label", "linear-integration,auto-generated"  # 添加标签
            ]
            
            pr_result = subprocess.run(pr_cmd, capture_output=True, text=True, timeout=60)
            
            if pr_result.returncode == 0:
                pr_url = pr_result.stdout.strip()
                logger.info(f"创建 PR 成功: {pr_url}")
                return {
                    "success": True,
                    "branch_name": branch_name,
                    "pr_url": pr_url,
                    "pr_output": pr_result.stdout
                }
            else:
                logger.error(f"创建 PR 失败: {pr_result.stderr}")
                return {
                    "success": False,
                    "error": f"创建 PR 失败: {pr_result.stderr}",
                    "branch_name": branch_name
                }
                
        finally:
            os.chdir(original_cwd)
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Git 操作失败: {e}")
        return {
            "success": False,
            "error": f"Git 操作失败: {e}",
            "returncode": e.returncode
        }
    except Exception as e:
        logger.error(f"创建分支和 PR 时出错: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def call_aider_with_linear_event(formatted_prompt: str, woodenman_path: str, linear_event_info: dict) -> dict:
    """调用 aider 处理 Linear 事件，创建分支和 PR"""
    try:
        logger.info(f"调用 aider 处理 Linear 事件，目标路径: {woodenman_path}")
        
        # 确保 WoodenMan 路径存在
        if not os.path.exists(woodenman_path):
            raise Exception(f"WoodenMan 路径不存在: {woodenman_path}")
        
        # 生成分支名和 PR 信息
        entity_id = linear_event_info.get('entity_id', str(uuid.uuid4())[:8])
        action = linear_event_info.get('action', 'update')
        title = linear_event_info.get('title', 'Event')
        entity_type = linear_event_info.get('entity_type', 'Unknown')
        
        # 构建 Linear Issue 链接和引用
        linear_url = linear_event_info.get('linear_url', '')
        linear_identifier = linear_event_info.get('linear_identifier', '')
        
        branch_name = f"linear-{action}-{entity_id[:8]}"
        pr_title = f"[{linear_identifier}] Linear {action.upper()}: {title}"
        
        # 创建 PR 描述，包含 Linear Issue 关联
        pr_body = f"""## 🔗 Linear Issue 关联

**Linear Issue**: [{linear_identifier}]({linear_url})
**Linear URL**: {linear_url}
**事件类型**: {entity_type} {action.upper()}
**实体 ID**: {entity_id}

## 📝 事件详情

**标题**: {title}
**处理时间**: {linear_event_info.get('created_at', 'Unknown')}

## 🤖 AI 处理结果

{formatted_prompt}

## 📋 变更说明

此 PR 由 Linear Webhook Handler 根据 Linear Issue 变更自动创建。

**关联的 Linear Issue**: [{linear_identifier}]({linear_url})
**Linear 链接**: {linear_url}

### 🔗 相关链接
- [Linear Issue: {linear_identifier}]({linear_url})
- [Linear 工作区](https://linear.app)

---
*🤖 此 PR 由 Linear Webhook Handler 自动创建并关联到 Linear Issue*
*📋 标签: `linear-integration`, `auto-generated`*
"""
        
        # 创建临时文件存储 prompt
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(formatted_prompt)
            temp_file = f.name
        
        try:
            # 构建 aider 命令
            aider_cmd = [
                "aider",
                "--yes",  # 自动确认
                "--auto-commits",  # 自动提交
                "--model", os.getenv("AIDER_OPENAI_MODEL", "deepseek-chat"),
                "--api-key", os.getenv("AIDER_OPENAI_API_KEY", ""),
                "--api-base", os.getenv("AIDER_OPENAI_API_BASE", "https://api.deepseek.com/v1"),
                "--input", temp_file,
                woodenman_path
            ]
            
            logger.info(f"执行 aider 命令: {' '.join(aider_cmd[:6])}...")
            
            # 执行 aider 命令
            result = subprocess.run(
                aider_cmd,
                cwd=os.path.dirname(woodenman_path),
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            aider_success = result.returncode == 0
            
            if aider_success:
                logger.info("aider 执行成功，开始创建分支和 PR")
                
                # 创建分支和 PR
                pr_result = create_branch_and_pr(woodenman_path, branch_name, pr_title, pr_body)
                
                return {
                    "success": True,
                    "aider_success": True,
                    "aider_stdout": result.stdout,
                    "aider_stderr": result.stderr,
                    "branch_name": branch_name,
                    "pr_result": pr_result
                }
            else:
                logger.error(f"aider 执行失败，返回码: {result.returncode}")
                logger.error(f"错误输出: {result.stderr}")
                return {
                    "success": False,
                    "aider_success": False,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                }
                
        finally:
            # 清理临时文件
            if os.path.exists(temp_file):
                os.unlink(temp_file)
                
    except subprocess.TimeoutExpired:
        logger.error("aider 执行超时")
        return {
            "success": False,
            "error": "aider 执行超时",
            "returncode": -1
        }
    except Exception as e:
        logger.error(f"调用 aider 时出错: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "returncode": -1
        }

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
        
        # 调用 aider 处理 Linear 事件
        aider_result = None
        try:
            # 格式化事件为 aider prompt
            formatted_prompt = format_linear_event_for_aider({
                "action": action,
                "entity_type": entity_type,
                "data": data
            })
            
            # 获取 WoodenMan 路径
            woodenman_path = os.path.join(os.path.dirname(__file__), "WoodenMan")
            
            # 准备 Linear 事件信息
            # 对于 Comment 事件，尝试从关联的 Issue 获取标识符
            linear_identifier = data.get("identifier", "")
            if not linear_identifier and entity_type == "Comment":
                # 对于 Comment，尝试从关联的 Issue 获取标识符
                issue_data = data.get("issue", {})
                linear_identifier = issue_data.get("identifier", f"COMMENT-{entity_id[:8]}")
            
            linear_event_info = {
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "title": data.get("title", ""),
                "linear_url": data.get("url", ""),
                "linear_identifier": linear_identifier,
                "created_at": webhook_event.created_at.isoformat() if webhook_event.created_at else None
            }
            
            # 调用 aider
            aider_result = call_aider_with_linear_event(formatted_prompt, woodenman_path, linear_event_info)
            
            if aider_result.get("success"):
                logger.info("aider 处理成功")
                if aider_result.get("pr_result", {}).get("success"):
                    logger.info(f"PR 创建成功: {aider_result['pr_result'].get('pr_url', 'Unknown')}")
            else:
                logger.error(f"aider 处理失败: {aider_result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"调用 aider 时出错: {str(e)}")
            aider_result = {"success": False, "error": str(e)}
        
        return {
            "status": "success",
            "message": f"Webhook event {action} for {entity_type} processed",
            "event_id": webhook_event.id,
            "linear_delivery": linear_delivery,
            "aider_result": aider_result
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

# Linear Webhook Handler

使用 FastAPI 和 SQLModel 构建的 Linear Webhook 处理 API。

## 技术栈

- FastAPI 0.115.6
- SQLModel 0.0.22
- SQLite

## 快速开始

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 启动服务：
```bash
python run.py
```

3. 访问文档：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 端点

- `POST /webhook/linear` - 处理 Linear webhook 事件
- `GET /webhook/events` - 获取事件列表
- `GET /webhook/events/{event_id}` - 获取特定事件
- `GET /` - API 信息
- `GET /health` - 健康检查

## 使用示例

发送 webhook 事件：
```bash
curl -X POST "http://localhost:8000/webhook/linear" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "create",
    "type": "Issue",
    "data": {
      "id": "123",
      "title": "测试问题"
    }
  }'
```
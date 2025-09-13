# Linear Webhook Handler 2025

使用 2025 年最新版本的 FastAPI 和 SQLModel 构建的 Linear Webhook 处理 API。

## ✨ 2025 年最新特性

- 🚀 **最新技术栈**: FastAPI 0.115.6 + SQLModel 0.0.22 + Pydantic 2.10.4
- 📊 **完整 Linear 支持**: 支持所有 Linear webhook 字段和头部信息
- 🔍 **高级查询**: 支持按实体类型、操作类型过滤
- 🛡️ **安全验证**: 支持 Linear 签名验证
- 📈 **性能优化**: 异步处理和优化的数据库查询

## 技术栈

- **FastAPI** 0.115.6 (2025 最新)
- **SQLModel** 0.0.22 (2025 最新)
- **Pydantic** 2.10.4 (2025 最新)
- **Uvicorn** 0.32.1 (2025 最新)
- **SQLite** (可配置为 PostgreSQL/MySQL)

## 快速开始

### 方式一：Docker 部署 (推荐)

1. 配置环境变量：
```bash
cp env.example .env
# 编辑 .env 文件，填入您的 DeepSeek API Key
```

2. 一键部署：
```bash
chmod +x deploy.sh
./deploy.sh
```

3. 访问服务：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 方式二：本地开发

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

### Webhook 处理
- `POST /webhook/linear` - 处理 Linear webhook 事件

### 事件查询
- `GET /webhook/events` - 获取事件列表（支持过滤）
- `GET /webhook/events/{event_id}` - 获取特定事件
- `GET /webhook/events/by-linear/{linear_delivery}` - 根据 Linear Delivery ID 获取事件

### 系统信息
- `GET /` - API 信息
- `GET /health` - 健康检查

## 使用示例

### 发送 webhook 事件
```bash
curl -X POST "http://localhost:8000/webhook/linear" \
  -H "Content-Type: application/json" \
  -H "Linear-Delivery: 234d1a4e-b617-4388-90fe-adc3633d6b72" \
  -H "Linear-Event: Issue" \
  -H "Linear-Signature: 766e1d90a96e2f5ecec342a99c5552999dd95d49250171b902d703fd674f5086" \
  -d '{
    "action": "create",
    "type": "Issue",
    "data": {
      "id": "2174add1-f7c8-44e3-bbf3-2d60b5ea8bc9",
      "title": "测试问题",
      "description": "这是一个测试问题"
    },
    "url": "https://linear.app/issue/LIN-1778/foo-bar",
    "createdAt": "2025-01-27T12:53:18.084Z",
    "webhookTimestamp": 1676056940508,
    "webhookId": "000042e3-d123-4980-b49f-8e140eef9329"
  }'
```

### 查询事件
```bash
# 获取所有事件
curl "http://localhost:8000/webhook/events"

# 按实体类型过滤
curl "http://localhost:8000/webhook/events?entity_type=Issue"

# 按操作类型过滤
curl "http://localhost:8000/webhook/events?action=create"

# 分页查询
curl "http://localhost:8000/webhook/events?skip=0&limit=10"
```

## 数据模型

支持完整的 Linear webhook 数据结构：
- Linear 头部信息 (Delivery, Event, Signature)
- 实体数据 (Issue, Comment, Project 等)
- 更新历史 (updatedFrom)
- Webhook 元数据 (时间戳、ID 等)

## Docker 管理

### 基本命令
```bash
# 构建镜像
docker build -t linear-webhook-handler .

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 重启服务
docker-compose restart
```

### 环境变量配置
```bash
# 复制环境变量模板
cp env.example .env

# 编辑配置文件
nano .env
```

### Aider 集成
项目已预配置 Aider 使用 DeepSeek：
- 工作目录：`/app`
- 模型：`deepseek-chat`
- 配置文件：`aider.conf`
- 环境变量：通过 `.env` 文件配置

### 数据持久化
- 数据库文件：`./data/`
- Aider 配置：`./aider_config/`
- 日志文件：容器内 `/app/logs/`
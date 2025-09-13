#!/bin/bash

# Linear Webhook Handler - Docker 部署脚本

set -e

echo "🚀 开始部署 Linear Webhook Handler..."

# 检查环境变量文件
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 文件，正在从 env.example 创建..."
    cp env.example .env
    echo "📝 请编辑 .env 文件，填入您的 API 密钥"
    echo "   特别是 OPENAI_API_KEY (DeepSeek API Key)"
    exit 1
fi

# 检查必需的 API 密钥
if ! grep -q "your_deepseek_api_key_here" .env; then
    echo "✅ 环境变量配置检查通过"
else
    echo "❌ 请在 .env 文件中配置您的 DeepSeek API Key"
    echo "   将 'your_deepseek_api_key_here' 替换为您的实际 API Key"
    exit 1
fi

# 创建必要的目录
echo "📁 创建数据目录..."
mkdir -p data
mkdir -p aider_config

# 构建 Docker 镜像
echo "🔨 构建 Docker 镜像..."
docker build -t linear-webhook-handler:latest .

# 停止现有容器
echo "🛑 停止现有容器..."
docker-compose down 2>/dev/null || true

# 启动服务
echo "🚀 启动服务..."
docker-compose up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
echo "🔍 检查服务状态..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ 服务启动成功！"
    echo ""
    echo "📚 API 文档:"
    echo "   - Swagger UI: http://localhost:8000/docs"
    echo "   - ReDoc: http://localhost:8000/redoc"
    echo ""
    echo "🔧 管理命令:"
    echo "   - 查看日志: docker-compose logs -f"
    echo "   - 停止服务: docker-compose down"
    echo "   - 重启服务: docker-compose restart"
    echo ""
    echo "🤖 Aider 配置:"
    echo "   - 工作目录: /app"
    echo "   - 使用模型: DeepSeek Chat"
    echo "   - 配置文件: ./aider_config/"
else
    echo "❌ 服务启动失败，请检查日志:"
    docker-compose logs
    exit 1
fi

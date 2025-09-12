import uvicorn
import os
from pathlib import Path

if __name__ == "__main__":
    # 获取项目根目录
    project_root = Path(__file__).parent
    
    # 配置
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "true").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info")
    
    print(f"🚀 启动 Linear Webhook Handler API")
    print(f"📍 地址: http://{host}:{port}")
    print(f"📚 API 文档: http://{host}:{port}/docs")
    print(f"📖 ReDoc: http://{host}:{port}/redoc")
    print(f"🔄 热重载: {'开启' if reload else '关闭'}")
    print(f"📊 日志级别: {log_level}")
    print("-" * 50)
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        access_log=True
    )

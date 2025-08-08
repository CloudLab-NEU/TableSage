from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend_api.muti_knowledge_visual_api import router as knowledge_router
from backend_api.core_processor_api import router as processor_router
from backend_api.any_record_visual_api import router as statistics_router
from backend_api.file_service_api import router as file_router
from backend_api.config_api import router as config_router  # 新增配置路由
from mcp_client.client import router as chat_router
from contextlib import asynccontextmanager
from mcp_client.client import load_mcp_config, load_all_tools

import uvicorn
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 启动时加载
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    load_mcp_config()
    await load_all_tools()
    yield
    # 关闭时执行
    pass

# 创建FastAPI应用实例
app = FastAPI(
    title="TableSage多维知识库API",
    description="提供多维知识库的查询和可视化接口",
    version="1.0.0",
    lifespan=lifespan
)

# 添加CORS中间件，允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(knowledge_router)
app.include_router(processor_router)
app.include_router(statistics_router) 
app.include_router(chat_router) 
app.include_router(file_router)  # 添加文件服务路由
app.include_router(config_router)  # 添加配置管理路由

@app.get("/")
async def root():
    """根路径，返回API基本信息"""
    return {
        "message": "TableSage多维知识库API",
        "version": "1.0.0",
        "status": "运行中",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health")
async def health_check():
    """健康检查接口"""
    try:
        # 这里可以添加数据库连接检查等
        return {
            "status": "healthy",
            "message": "服务运行正常"
        }
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        raise HTTPException(status_code=500, detail="服务异常")

if __name__ == "__main__":
    # 启动服务器
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,  # 开发环境启用热重载
        log_level="info"
    )
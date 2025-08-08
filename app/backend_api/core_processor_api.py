from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from core_progress.tablesage_processor import TableSageProcessor
import logging
from fastapi.responses import StreamingResponse
import json
from mcp_client.client import generate_session_id, result_cache

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/processor", tags=["核心答题处理"])

# 初始化TableSage处理器
table_sage_processor = TableSageProcessor()

class TableData(BaseModel):
    """表格数据模型"""
    header: List[str] = Field(..., description="表格表头")
    rows: List[List[Any]] = Field(..., description="表格行数据")

class QuestionRequest(BaseModel):
    """问题请求模型"""
    question: str = Field(..., min_length=1, description="用户问题")
    table: TableData = Field(..., description="表格数据")

class AnswerResponse(BaseModel):
    """答案响应模型"""
    status: str = Field(description="响应状态")
    data: Dict[str, Any] = Field(description="答案数据")
    message: Optional[str] = Field(None, description="额外消息")

@router.post("/answer", response_model=AnswerResponse)
async def process_question(request: QuestionRequest):
    """
    处理用户问题并返回答案
    
    Args:
        request: 包含问题和表格数据的请求
        
    Returns:
        dict: 包含答案和相关信息的响应
    """
    try:
        logger.info(f"收到问题处理请求: {request.question[:50]}...")
        
        # 转换表格数据格式
        user_table = {
            "header": request.table.header,
            "rows": request.table.rows
        }
        
        # 调用TableSage处理器
        result = table_sage_processor.process(request.question, user_table)
        
        # 检查是否有错误
        if "error" in result:
            logger.error(f"处理过程中出现错误: {result['error']}")
            return AnswerResponse(
                status="error",
                data=result,
                message="处理问题时遇到错误"
            )
        
        # 成功处理
        logger.info(f"问题处理完成，置信度: {result.get('confidence', 0)}")
        
        return AnswerResponse(
            status="success",
            data={
                "answer": result.get("answer", ""),
                "confidence": result.get("confidence", 0.0),
                "context_used": result.get("context_used", ""),
                "flow_path": result.get("flow_path", "unknown"),
                "similar_questions": result.get("similar_questions", []),
                "metadata": {
                    "question_length": len(request.question),
                    "table_size": f"{len(request.table.header)}x{len(request.table.rows)}",
                    "processing_method": result.get("flow_path", "unknown")
                }
            },
            message="问题处理成功"
        )
        
    except Exception as e:
        logger.error(f"API处理失败: {str(e)}")
        import traceback
        error_details = traceback.format_exc()
        
        raise HTTPException(
            status_code=500, 
            detail={
                "error": str(e),
                "error_details": error_details,
                "message": "服务器内部错误"
            }
        )

@router.post("/answer-stream")
async def process_question_stream(request: QuestionRequest):
    # 生成会话ID
    
    def event_stream():
        user_table = {
            "header": request.table.header,
            "rows": request.table.rows
        }

        session_id = generate_session_id(request.question, user_table)
        try:
            for item in table_sage_processor.process_stream(request.question, user_table):
                # 添加session_id到每个响应
                item["session_id"] = session_id
                
                # 如果是最终结果，缓存起来
                if item.get("step") == "end":
                    complete_result = item.get("complete_result")
                    if complete_result:
                        result_cache[session_id] = complete_result
                        # 添加报告生成提示
                        item["report_available"] = True
                        item["generate_report_url"] = f"/api/chat/generate-report/{session_id}"
                
                yield json.dumps(item, ensure_ascii=False) + "\n"
        except Exception as e:
            error_item = {
                "step": "error",
                "error": str(e),
                "session_id": session_id
            }
            yield json.dumps(error_item, ensure_ascii=False) + "\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@router.get("/config")
async def get_processor_config():
    """
    获取处理器配置信息
    
    Returns:
        dict: 配置信息
    """
    try:
        return {
            "status": "success",
            "config": {
                "confidence_threshold": table_sage_processor.confidence_threshold,
                "processor_components": [
                    "AnsweringProcessor",
                    "GuidancingProcessor", 
                    "FinalAnswerProcessor"
                ],
                "version": "1.0.0"
            }
        }
    except Exception as e:
        logger.error(f"获取配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取配置失败")

@router.post("/batch-answer")
async def process_batch_questions(requests: List[QuestionRequest]):
    """
    批量处理问题（可选功能）
    
    Args:
        requests: 问题请求列表
        
    Returns:
        dict: 批量处理结果
    """
    try:
        if len(requests) > 10:  # 限制批量数量
            raise HTTPException(status_code=400, detail="批量请求数量不能超过10个")
        
        results = []
        for i, request in enumerate(requests):
            try:
                # 转换表格数据格式
                user_table = {
                    "header": request.table.header,
                    "rows": request.table.rows
                }
                
                # 处理单个问题
                result = table_sage_processor.process(request.question, user_table)
                results.append({
                    "index": i,
                    "question": request.question[:50] + "..." if len(request.question) > 50 else request.question,
                    "status": "error" if "error" in result else "success",
                    "result": result
                })
            except Exception as e:
                results.append({
                    "index": i,
                    "question": request.question[:50] + "..." if len(request.question) > 50 else request.question,
                    "status": "error",
                    "result": {"error": str(e)}
                })
        
        return {
            "status": "completed",
            "total_requests": len(requests),
            "successful": len([r for r in results if r["status"] == "success"]),
            "failed": len([r for r in results if r["status"] == "error"]),
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量处理失败: {str(e)}")
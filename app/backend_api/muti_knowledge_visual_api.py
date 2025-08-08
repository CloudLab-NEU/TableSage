from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from db.db_manager import DatabaseManager
from utils.build_similar_graph import SimilarityGraphBuilder
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["多维知识库"])

# 初始化数据库管理器
db_manager = DatabaseManager()

#获取知识库题目数量，框架数量
@router.get("/overview")
async def get_knowledge_overview():
    """
    获取多维知识库概览信息
    
    Returns:
        dict: 包含题库总数量等基本信息
    """
    try:
        # 获取题库总数量
        total_count = db_manager.knowledge_db.count_documents({})
        
        # 获取一些统计信息
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_questions": {"$sum": 1},
                    "avg_question_length": {"$avg": {"$strLenCP": "$question"}}
                }
            }
        ]
        
        stats = list(db_manager.knowledge_db.aggregate(pipeline))
        avg_length = round(stats[0]["avg_question_length"], 2) if stats else 0
        
        return {
            "status": "success",
            "data": {
                "total_questions": total_count,
                "average_question_length": avg_length,
                "database_name": "TableSage多维知识库"
            }
        }
    except Exception as e:
        logger.error(f"获取知识库概览失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取概览信息失败: {str(e)}")

#分页查询接口
@router.get("/questions")
async def get_questions_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索关键词")
):
    """
    获取问题列表（分页）
    
    Args:
        page: 页码，从1开始
        page_size: 每页数量，最多100条
        search: 可选的搜索关键词
        
    Returns:
        dict: 包含问题列表和分页信息
    """
    try:
        # 构建查询条件
        query = {}
        if search:
            query = {"question": {"$regex": search, "$options": "i"}}
        
        # 计算跳过的文档数量
        skip = (page - 1) * page_size
        
        # 获取总数
        total_count = db_manager.knowledge_db.count_documents(query)
        
        # 获取问题列表
        cursor = db_manager.knowledge_db.find(
            query,
            {
                "table_id": 1,
                "question": 1,
                "_id": 0
            }
        ).skip(skip).limit(page_size)
        
        questions = list(cursor)
        
        # 计算总页数
        total_pages = (total_count + page_size - 1) // page_size
        
        return {
            "status": "success",
            "data": {
                "questions": questions,
                "pagination": {
                    "current_page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
        }
    except Exception as e:
        logger.error(f"获取问题列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取问题列表失败: {str(e)}")

#获取当前选中问题的详细内容（表格，三种策略，问题）
@router.get("/question/{table_id}")
async def get_question_detail(table_id: str):
    """
    获取特定问题的详细信息，包括三种策略和表格内容
    
    Args:
        table_id: 表格ID
        
    Returns:
        dict: 包含问题详情、策略和表格结构的完整信息
    """
    try:
        # 获取知识条目
        knowledge = db_manager.get_knowledge_by_id(table_id)
        
        if not knowledge:
            raise HTTPException(status_code=404, detail=f"未找到ID为 {table_id} 的问题")
        
        # 提取三种策略
        strategies = {
            "cot": knowledge['strategy'].get("cot", ""),
            "column_sorting": knowledge['strategy'].get("column_sorting", ""),
            "schema_linking": knowledge['strategy'].get("schema_linking", "")
        }
        
        # 提取表格结构信息
        table_info = knowledge.get("table", {})
        
        # 组织返回数据
        result = {
            "id": knowledge.get("table_id"),
            "question": knowledge.get("question", ""),
            "question_skeleton": knowledge.get("question_skeleton", ""),
            "answer": knowledge.get("answer", ""),
            "strategies": strategies,
            "table_info": {
                "header": table_info.get("header", []),
                "rows": table_info.get("rows", []),
            }
        }
        
        return {
            "status": "success",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取问题详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取问题详情失败: {str(e)}")

@router.get("/search")
async def search_questions(
    query: str = Query(..., min_length=1, description="搜索查询"),
    limit: int = Query(10, ge=1, le=50, description="返回结果数量限制")
):
    """
    基于文本搜索问题
    
    Args:
        query: 搜索查询字符串
        limit: 返回结果数量限制
        
    Returns:
        dict: 搜索结果列表
    """
    try:
        # 使用数据库管理器的文本搜索功能
        search_results = db_manager.search_similar_questions_by_text(query)
        
        # 限制结果数量
        limited_results = search_results[:limit]
        
        return {
            "status": "success",
            "data": {
                "query": query,
                "results": limited_results,
                "total_found": len(search_results),
                "returned_count": len(limited_results)
            }
        }
        
    except Exception as e:
        logger.error(f"搜索问题失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

#返回问题相似度图，展示问题之间的关系    
@router.get("/similarity-graph")
async def build_similarity_graph(
    question: str = Query(..., min_length=1, description="起始问题内容"),
    max_layers: int = Query(2, ge=1, le=3, description="图的最大层数"),
    top_n: int = Query(5, ge=1, le=10, description="每层最多显示的相似问题数量")
):
    """
    构建问题相似度图，用于可视化展示
    
    Args:
        question: 起始问题内容
        max_layers: 图的最大层数（1-3层）
        top_n: 每层最多显示的相似问题数量（1-10个）
        
    Returns:
        dict: ECharts格式的图数据，包含节点、边和类别信息
    """
    try:
        # 创建图构建器
        builder = SimilarityGraphBuilder(max_layers=max_layers, top_n=top_n)
        
        # 构建图并获取ECharts格式数据
        builder.build_graph(question)
        echarts_data = builder.to_echarts_format()
        return {
            "status": "success",
            "data": {
                "query": question,
                "graph_data": echarts_data,
                "graph_stats": {
                    "nodes_count": len(echarts_data.get('nodes', [])),
                    "links_count": len(echarts_data.get('links', [])),
                    "max_layers": max_layers,
                    "top_n": top_n
                }
            }
        }
        
    except Exception as e:
        logger.error(f"构建相似度图失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"构建相似度图失败: {str(e)}")
    

#统计当前学习记录库中的各种策略的使用频率
@router.get("/strategy-statistics")
async def get_strategy_statistics():
    """
    统计当前学习记录库中各种策略的使用频率
    
    Returns:
        dict: 包含各策略使用数量及占比的统计信息
    """
    try:
        # 1. 统计学习记录库中 flag=2 的数量
        flag_2_count = db_manager.learning_records.count_documents({"flag": 2})
        # 统计flag=1的数量
        flag_1_count = db_manager.learning_records.count_documents({"flag": 1})
        
        # 总记录数（flag=1 + flag=2）
        total_records = flag_1_count + flag_2_count
        
        # 2. 联查学习记录表和指导记录表，获取 flag=1 时各策略的数量
        pipeline = [
            {
                "$match": {"flag": 1}
            },
            {
                "$lookup": {
                    "from": "GuidanceRecordsDataBase",
                    "localField": "table_id",
                    "foreignField": "table_id",
                    "as": "guidance"
                }
            },
            {
                "$unwind": "$guidance"
            },
            {
                "$group": {
                    "_id": "$guidance.strategy_type",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        # 初始化策略计数
        strategy_counts = {
            "cot": 0,
            "coloumn_sorting": 0, 
            "schema_linking": 0
        }
        
        # 初始化flag=1策略计数
        strategy_counts_flag_1 = {
            "cot": 0,
            "coloumn_sorting": 0,
            "schema_linking": 0
        }
        
        # 统计flag=1情况下各策略数量
        results = list(db_manager.learning_records.aggregate(pipeline))
        for result in results:
            strategy_type = result["_id"]
            count = result["count"]
            if strategy_type in strategy_counts_flag_1:
                strategy_counts_flag_1[strategy_type] = count
                strategy_counts[strategy_type] = count
        
        # 3. 将flag=2的数量加到各个策略的数量中
        strategy_counts["cot"] += flag_2_count
        strategy_counts["coloumn_sorting"] += flag_2_count
        strategy_counts["schema_linking"] += flag_2_count
        
        # 计算总记录数和各策略占比
        total_strategies = sum(strategy_counts.values())
        
        # 修改：计算每个策略自己的教学成功率
        # 公式：策略在flag=1下的数量 / (策略在flag=1下的数量 + flag=2数量)
        strategy_percentages_flag_1 = {}
        for strategy, count in strategy_counts_flag_1.items():
            # 计算该策略的总数 (flag=1 + flag=2)
            strategy_total = count + flag_2_count
            if strategy_total > 0:
                strategy_percentages_flag_1[strategy] = round(count / strategy_total * 100, 2)
            else:
                strategy_percentages_flag_1[strategy] = 0
        
        # 计算总体占比
        strategy_percentages = {}
        if total_strategies > 0:
            for strategy, count in strategy_counts.items():
                strategy_percentages[strategy] = round(count / total_strategies * 100, 2)
        
        return {
            "status": "success",
            "data": {
                "strategy_statistics": {
                    "counts": strategy_counts,
                    "percentages": strategy_percentages
                },
                "strategy_statistics_flag_1": {
                    "counts": strategy_counts_flag_1,
                    "percentages": strategy_percentages_flag_1
                },
                "flag_2_count": flag_2_count,
                "flag_1_count": flag_1_count,
                "total_records": total_records,
                "total_strategies": total_strategies
            }
        }
        
    except Exception as e:
        logger.error(f"获取策略统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取策略统计信息失败: {str(e)}")
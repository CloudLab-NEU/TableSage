from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict
from db.db_manager import DatabaseManager
from datetime import datetime, timedelta

import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/statistics", tags=["统计分析"])

# 初始化数据库管理器
db_manager = DatabaseManager()
db_manager.teaching_records.create_index("table_id")
db_manager.db["MutiKnowledgeDataBase"].create_index("table_id")

# 该接口可以获取到按天统计到的flag=0，1，2的数量，以及学习记录库中的总数
# 然后可以用来计算导师能力的提升，以及学徒能力的提升
@router.get("/daily-records")
async def get_daily_records_statistics(
    days: Optional[int] = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    按天统计学习记录中的flag=0、flag=1和flag=2的数量
    
    Args:
        days: 要统计的天数（从今天往前算，默认30天）
        start_date: 开始日期（格式：YYYY-MM-DD），优先级高于days参数
        end_date: 结束日期（格式：YYYY-MM-DD），默认为今天
        
    Returns:
        dict: 按天统计的学习记录数量
    """
    try:
        # 处理日期参数
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="结束日期格式错误，应为YYYY-MM-DD")
        else:
            end_date_obj = datetime.now()
            
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="开始日期格式错误，应为YYYY-MM-DD")
        else:
            start_date_obj = end_date_obj - timedelta(days=days)
            
        # 确保开始日期早于结束日期
        if start_date_obj > end_date_obj:
            raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
        
        # 设置查询日期范围
        date_filter = {
            "first_answer_time": {
                "$gte": start_date_obj.replace(hour=0, minute=0, second=0, microsecond=0),
                "$lte": end_date_obj.replace(hour=23, minute=59, second=59, microsecond=999999)
            }
        }
        
        # 使用MongoDB聚合管道按天和flag分组
        pipeline = [
            {
                "$match": date_filter
            },
            {
                "$project": {
                    "date_string": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$first_answer_time"
                        }
                    },
                    "flag": 1
                }
            },
            {
                "$group": {
                    "_id": {
                        "date": "$date_string",
                        "flag": "$flag"
                    },
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"_id.date": 1, "_id.flag": 1}
            }
        ]
        
        # 执行聚合查询
        results = list(db_manager.learning_records.aggregate(pipeline))
        
        # 初始化日期范围内的所有日期
        delta = end_date_obj - start_date_obj
        all_dates = [(start_date_obj + timedelta(days=i)).strftime("%Y-%m-%d") 
                     for i in range(delta.days + 1)]
        
        # 初始化返回结果，所有日期的flag=0,1,2数量都设为0
        daily_stats = {
            date: {"flag_0": 0, "flag_1": 0, "flag_2": 0} for date in all_dates
        }
        
        # 填充查询结果
        for result in results:
            date = result["_id"]["date"]
            flag = result["_id"]["flag"]
            count = result["count"]
            
            if date in daily_stats:
                daily_stats[date][f"flag_{flag}"] = count
        
        # 计算每天的总记录数
        for date in daily_stats:
            daily_stats[date]["total"] = (
                daily_stats[date]["flag_0"] + 
                daily_stats[date]["flag_1"] + 
                daily_stats[date]["flag_2"]
            )
        
        # 转换为列表形式，便于前端处理
        daily_stats_list = [
            {
                "date": date,
                "flag_0": stats["flag_0"],
                "flag_1": stats["flag_1"],
                "flag_2": stats["flag_2"],
                "total": stats["total"]
            }
            for date, stats in daily_stats.items()
        ]
        
        # 计算总计
        total_stats = {
            "flag_0": sum(item["flag_0"] for item in daily_stats_list),
            "flag_1": sum(item["flag_1"] for item in daily_stats_list),
            "flag_2": sum(item["flag_2"] for item in daily_stats_list),
            "total": sum(item["total"] for item in daily_stats_list)
        }
        
        return {
            "status": "success",
            "data": {
                "daily_statistics": daily_stats_list,
                "total_statistics": total_stats,
                "date_range": {
                    "start_date": start_date_obj.strftime("%Y-%m-%d"),
                    "end_date": end_date_obj.strftime("%Y-%m-%d"),
                    "days": len(all_dates)
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取每日记录统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取每日记录统计失败: {str(e)}")
    
@router.get("/error-records-count")
async def get_error_records_count():
    """
    统计错题记录库中的错题总数
    
    Returns:
        dict: 包含错题记录总数的信息
    """
    try:
        # 统计错题记录库中的文档总数
        error_count = db_manager.error_records.count_documents({})
        
        return {
            "status": "success",
            "data": {
                "total_error_records": error_count,
            }
        }
        
    except Exception as e:
        logger.error(f"获取错题记录统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取错题记录统计失败: {str(e)}")
    
@router.get("/strategy-categories")
async def get_strategy_statistics():
    """
    统计每个问题类别下不同策略类型的使用次数
    
    Returns:
        dict: 包含各问题类别下不同策略类型数量统计的信息
    """
    try:
        # 使用MongoDB聚合管道进行联查和统计
        pipeline = [
            {
                "$project": {
                    "table_id": 1,
                    "strategy_type": 1
                }
            },
            # 只保留一个优化的 lookup
            {
                "$lookup": {
                    "from": "MutiKnowledgeDataBase",
                    "localField": "table_id",
                    "foreignField": "table_id",
                    "as": "knowledge_info",
                    # 使用子管道限制返回字段，减少数据传输量
                    "pipeline": [
                        {"$project": {"categories": 1, "_id": 0}}
                    ]
                }
            },
            # 过滤掉没有匹配到知识库的记录
            {
                "$match": {
                    "knowledge_info": {"$ne": []}
                }
            },
            # 展开知识库数组
            {
                "$unwind": "$knowledge_info"
            },
            # 按照类别和策略类型进行分组计数
            {
                "$group": {
                    "_id": {
                        "category": "$knowledge_info.categories",
                        "strategy_type": "$strategy_type"
                    },
                    "count": {"$sum": 1}
                }
            },
            # 按照类别和策略类型排序
            {
                "$sort": {"_id.category": 1, "_id.strategy_type": 1}
            }
        ]
        
        # 执行聚合查询
        results = list(db_manager.teaching_records.aggregate(pipeline))
        # 处理结果，重新组织为易于使用的格式
        # 先找出所有唯一的类别和策略类型
        categories = set()
        strategy_types = set()
        
        for result in results:
            categories.add(result["_id"]["category"])
            strategy_types.add(result["_id"]["strategy_type"])
        
        # 初始化每个类别的统计数据
        statistics = {}
        for category in categories:
            statistics[category] = {str(strategy_type): 0 for strategy_type in strategy_types}
        
        # 填充统计数据
        for result in results:
            category = result["_id"]["category"]
            strategy_type = str(result["_id"]["strategy_type"])
            count = result["count"]
            statistics[category][strategy_type] = count
        
        # 为每个类别计算策略总数
        for category in statistics:
            statistics[category]["total"] = sum(
                count for strategy_type, count in statistics[category].items()
                if strategy_type != "total"
            )
        
        # 计算总统计数据
        total_statistics = {str(strategy_type): 0 for strategy_type in strategy_types}
        for category, counts in statistics.items():
            for strategy_type, count in counts.items():
                if strategy_type != "total":
                    total_statistics[strategy_type] = total_statistics.get(strategy_type, 0) + count
        
        total_statistics["total"] = sum(count for strategy_type, count in total_statistics.items() if strategy_type != "total")
        
        # 将统计数据转换为列表格式，便于前端处理
        result_list = [
            {
                "category": category,
                **counts
            }
            for category, counts in statistics.items()
        ]
        
        return {
            "status": "success",
            "data": {
                "category_statistics": result_list,
                "total_statistics": total_statistics
            }
        }
        
    except Exception as e:
        logger.error(f"获取策略统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取策略统计失败: {str(e)}")
    
@router.get("/learning-records-count")
async def get_learning_records_count():
    """
    统计学习记录库中的记录总数
    
    Returns:
        dict: 包含学习记录总数的信息
    """
    try:
        # 统计学习记录库中的文档总数
        records_count = db_manager.teaching_records.count_documents({})
        
        return {
            "status": "success",
            "data": {
                "total_teaching_records": records_count,
            }
        }
        
    except Exception as e:
        logger.error(f"获取学习记录统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取学习记录统计失败: {str(e)}")
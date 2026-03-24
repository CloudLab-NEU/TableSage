"""
TableSage 完整流程集成测试脚本
=================================
前置条件:
  1. 已配置 .env 文件 (OPENAI_API_KEY, OPENAI_API_BASE, MONGO_URI 等)
  2. MongoDB 中已有知识库数据
  3. conda activate tablesage

运行方式:
  cd d:\TableSage\app
  python tests/integration_test.py

可选参数:
  python tests/integration_test.py --test db       # 只测试数据库
  python tests/integration_test.py --test llm      # 只测试 LLM
  python tests/integration_test.py --test rag      # 只测试 RAG 检索
  python tests/integration_test.py --test agent    # 只测试 Agent 全流程
  python tests/integration_test.py --test all      # 全部测试 (默认)
"""

import sys
import os
import time
import json
import argparse
import traceback
from typing import Optional

# ── 路径设置 ─────────────────────────────────────────────────────────────────
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# ── ANSI 颜色 ─────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✓ {msg}{RESET}")
def fail(msg):  print(f"  {RED}✗ {msg}{RESET}")
def warn(msg):  print(f"  {YELLOW}⚠ {msg}{RESET}")
def info(msg):  print(f"  {CYAN}→ {msg}{RESET}")
def section(title): print(f"\n{BOLD}{BLUE}{'─'*60}\n  {title}\n{'─'*60}{RESET}")

# ── 测试结果累计 ──────────────────────────────────────────────────────────────
RESULTS = []
def record(name, passed, detail=""):
    RESULTS.append({"name": name, "passed": passed, "detail": detail})


# ═══════════════════════════════════════════════════════════════════════════════
# Test 1: 环境检查
# ═══════════════════════════════════════════════════════════════════════════════
def test_environment():
    section("Test 1 · 环境与配置检查")
    from dotenv import load_dotenv
    load_dotenv()

    checks = {
        "OPENAI_API_KEY":  os.environ.get("OPENAI_API_KEY"),
        "DB_HOST":       os.environ.get("DB_HOST"),
        "LLM_MODEL":       os.environ.get("LLM_MODEL", "(default: gpt-3.5-turbo)"),
    }
    all_ok = True
    for k, v in checks.items():
        if v:
            ok(f"{k} = {v[:20]}...")
        else:
            fail(f"{k} 未设置")
            all_ok = False

    optional = {
        "OPENAI_API_BASE": os.environ.get("OPENAI_API_BASE", "(not set, using default)"),
        "DB_NAME":         os.environ.get("DB_NAME", "(not set)"),
    }
    for k, v in optional.items():
        warn(f"{k} = {v}")

    record("环境配置检查", all_ok,
           "所有必填环境变量已设置" if all_ok else "缺少必填环境变量")
    return all_ok


# ═══════════════════════════════════════════════════════════════════════════════
# Test 2: 数据库连接与基本操作
# ═══════════════════════════════════════════════════════════════════════════════
def test_database():
    section("Test 2 · 数据库连接与操作")
    try:
        from db.db_manager import DatabaseManager
        db = DatabaseManager()
        ok("DatabaseManager 初始化成功")

        # 统计信息
        stats = db.get_statistics()
        info(f"知识库记录数: {stats.get('knowledge_records', 0)}")
        info(f"学习记录数:   {stats.get('learning_records', {})}")
        info(f"错误记录数:   {stats.get('error_records', 0)}")
        info(f"指导记录数:   {stats.get('teaching_records', {})}")

        knowledge_count = stats.get('knowledge_records', 0)
        if knowledge_count == 0:
            warn("知识库为空！RAG 和 Agent 测试将跳过")
            record("数据库连接", True, "连接成功但知识库为空")
            return None  # 返回 None 表示 DB 可用但无数据

        # 获取一条样本记录
        sample = db.knowledge_db.find_one({})
        if sample:
            table_id = sample.get("table_id", "")
            ok(f"获取样本记录成功，table_id = {table_id}")

            # 测试 get_knowledge_by_id
            retrieved = db.get_knowledge_by_id(table_id)
            assert retrieved is not None, "get_knowledge_by_id 返回 None"
            ok(f"get_knowledge_by_id 验证通过")
            info(f"  问题: {retrieved.get('question', '')[:60]}...")

            # 测试 get_learning_record
            lr = db.get_learning_record(table_id)
            if lr:
                ok(f"get_learning_record 返回 flag={lr.get('flag')}")
            else:
                info("该记录暂无学习记录 (flag=None)")

            # 测试 batch_get_learning_records
            all_ids = [d["table_id"] for d in db.knowledge_db.find({}, {"table_id": 1}).limit(5)]
            batch = db.batch_get_learning_records(all_ids)
            ok(f"batch_get_learning_records 返回 {len(batch)}/{len(all_ids)} 条")

            record("数据库连接与操作", True, f"知识库 {knowledge_count} 条记录")
            return sample  # 返回样本供后续测试使用

    except Exception as e:
        fail(f"数据库测试失败: {e}")
        traceback.print_exc()
        record("数据库连接与操作", False, str(e))
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Test 3: LLM 连接
# ═══════════════════════════════════════════════════════════════════════════════
def test_llm():
    section("Test 3 · LLM 连接测试")
    try:
        from openai_api.openai_client import OpenAIClient
        client = OpenAIClient()
        ok("OpenAIClient 初始化成功")

        t0 = time.time()
        resp = client.get_llm_response([
            {"role": "user", "content": "你是什么模型"}
        ])
        elapsed = time.time() - t0
        ok(f"LLM 调用成功 ({elapsed:.1f}s)")
        info(f"  响应: {resp[:80]}")

        if "42" in resp:
            ok("LLM 响应内容正确（包含 '42'）")
        else:
            warn(f"LLM 响应不含预期数字，实际: {resp[:40]}")

        record("LLM 连接测试", True, f"响应耗时 {elapsed:.1f}s")
        return True

    except Exception as e:
        fail(f"LLM 测试失败: {e}")
        traceback.print_exc()
        record("LLM 连接测试", False, str(e))
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Test 4: utils 工具函数
# ═══════════════════════════════════════════════════════════════════════════════
def test_utils():
    section("Test 4 · 工具函数测试")
    try:
        from utils.utils import TableUtils, normalize_answer
        tu = TableUtils()

        # table2format
        test_table = {
            "header": ["Name", "Score", "Active"],
            "rows": [["Alice", 95.5, True], ["Bob", None, False]]
        }
        formatted = tu.table2format(test_table)
        assert "95.5" in formatted, "table2format 应含 95.5"
        assert "None" in formatted, "table2format 应含 None"
        ok("table2format 处理非字符串数据正常")

        # is_answer_correct
        assert tu.is_answer_correct("<Answer>['yes']</Answer>", ["yes"]) is True
        assert tu.is_answer_correct("<Answer>['no']</Answer>", ["yes"]) is False
        assert tu.is_answer_correct("<Answer>['1,000']</Answer>", ["1000"]) is True
        ok("is_answer_correct 验证通过（精确/数字格式/大小写）")

        # normalize_answer
        assert normalize_answer(["hello"]) == "hello"
        assert normalize_answer("['world']") == "world"
        ok("normalize_answer 验证通过")

        record("工具函数测试", True)
        return True

    except AssertionError as e:
        fail(f"断言失败: {e}")
        record("工具函数测试", False, str(e))
        return False
    except Exception as e:
        fail(f"utils 测试异常: {e}")
        traceback.print_exc()
        record("工具函数测试", False, str(e))
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Test 5: RAG 检索
# ═══════════════════════════════════════════════════════════════════════════════
def test_rag(sample_record):
    section("Test 5 · RAG 相似问题检索")
    if not sample_record:
        warn("跳过：知识库为空或 DB 不可用")
        record("RAG 检索", None, "跳过")
        return None

    try:
        from core_progress.search_similar_question import find_topn_question
        from utils.utils import TableUtils

        tu = TableUtils()
        question = sample_record.get("question", "")
        table = sample_record.get("table", {"header": [], "rows": []})

        info(f"测试问题: {question[:60]}...")

        # 提取骨架信息
        proc = tu.match_similar_data_processor(question, table)
        sql_skeleton = proc.get("sql_skeleton", "")
        question_skeleton = proc.get("question_skeleton", "")
        question_skeleton_embedding = proc.get("question_skeleton_embedding", [])
        table_structure = proc.get("table_structure", "")

        info(f"SQL 骨架: {sql_skeleton[:50]}")
        info(f"问题骨架: {question_skeleton[:50]}")

        t0 = time.time()
        result = find_topn_question(
            question_skeleton=question_skeleton,
            skeleton_embedding=question_skeleton_embedding,
            table_structure=table_structure,
            top_n=3
        )
        elapsed = time.time() - t0

        if not result or not isinstance(result, tuple):
            warn("RAG 检索返回空结果")
            record("RAG 检索", True, "返回 0 条（无相似题）")
            return []

        similar_ids, topnList = result
        ok(f"RAG 检索成功 ({elapsed:.2f}s)，返回 {len(similar_ids)} 条相似题")
        for i, (sid, score) in enumerate(zip(similar_ids, topnList)):
            info(f"  [{i+1}] table_id={sid}  similarity={score:.4f}")

        record("RAG 检索", True, f"返回 {len(similar_ids)} 条，耗时 {elapsed:.2f}s")
        return similar_ids

    except Exception as e:
        fail(f"RAG 检索失败: {e}")
        traceback.print_exc()
        record("RAG 检索", False, str(e))
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Test 6: Agent 工具单独测试
# ═══════════════════════════════════════════════════════════════════════════════
def test_agent_tools(similar_ids):
    section("Test 6 · Agent 工具独立测试")
    if not similar_ids:
        warn("跳过：无 RAG 结果")
        record("Agent 工具测试", None, "跳过")
        return

    # 6-1: get_learning_records_tool
    print(f"\n  {BOLD}6-1 get_learning_records_tool{RESET}")
    try:
        from agent.tools.learning_record_tool import get_learning_records_tool
        result = get_learning_records_tool(similar_ids)

        ok(f"调用成功 | mastered={len(result.get('mastered_ids', []))} strategy={len(result.get('strategy_ids', []))} attempt={len(result.get('attempt_ids', []))} reflection={len(result.get('reflection_ids', []))}")
        info(f"auto_confidence = {result.get('auto_confidence', 0):.1%}")
        info(result.get('auto_confidence_explanation', ''))

        if result.get("success_strategy_context"):
            info(f"success_strategy_context 摘要: {result['success_strategy_context'][:80]}...")
        if result.get("reflection_context"):
            info(f"reflection_context 摘要:   {result['reflection_context'][:80]}...")
    except Exception as e:
        fail(f"get_learning_records_tool 失败: {e}")
        traceback.print_exc()
        record("Agent 工具测试", False, str(e))
        return

    # 6-2: answer_by_id_tool（仅对 attempt_ids 中第一条测试）
    attempt_ids = result.get("attempt_ids", [])
    if attempt_ids:
        print(f"\n  {BOLD}6-2 answer_by_id_tool (table_id={attempt_ids[0]}){RESET}")
        try:
            from agent.tools.answer_by_id_tool import answer_by_id_tool
            t0 = time.time()
            ans = answer_by_id_tool(attempt_ids[0], use_existing_learning=True)
            elapsed = time.time() - t0

            if "error" in ans:
                fail(f"answer_by_id_tool 返回错误: {ans['error']}")
            else:
                correct_str = f"{GREEN}正确{RESET}" if ans.get("is_correct") else f"{RED}错误{RESET}"
                ok(f"answer_by_id_tool 完成 ({elapsed:.1f}s) | {correct_str} | strategy={ans.get('strategy_used')}")
                info(f"  回答摘要: {ans.get('answer', '')[:80]}...")
        except Exception as e:
            fail(f"answer_by_id_tool 失败: {e}")
            traceback.print_exc()
    else:
        warn("所有 similar_ids 都在 skip_ids 或 error_context_ids 中，跳过 answer_by_id 测试")

    record("Agent 工具测试", True, f"工具调用全部完成")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 7: Agent 完整流程详细测试（自定义问题）
# ═══════════════════════════════════════════════════════════════════════════════

TOOL_DESC = {
    "get_learning_records":  "查询相似题历史学习记录",
    "answer_by_id":          "尝试回答相似题",
    "apply_strategy_by_id":  "用策略重新回答相似题",
    "think":                 "思考评估当前上下文",
    "generate_final_answer": "生成用户问题的最终答案",
}

def _print_agent_result(result: dict, elapsed: float, label: str = "Agent"):
    """统一打印 agent.run() 的完整结果，含相似题、工具调用轨迹、最终答案。"""

    # ── 基本摘要 ─────────────────────────────────────────────────────────────
    print(f"\n  {BOLD}{'─'*54}")
    print(f"  {label} 执行摘要  (耗时 {elapsed:.1f}s){RESET}")
    print(f"  {'─'*54}")
    info(f"flow_path   : {result.get('flow_path', '-')}")
    info(f"total_steps : {result.get('total_steps', 0)} 步工具调用")
    info(f"context_used: {result.get('context_used', '-')}")

    # ── RAG 相似题 ───────────────────────────────────────────────────────────
    sim_ids = result.get("similar_questions", [])
    print(f"\n  {BOLD}RAG 检索到的相似题 ({len(sim_ids)} 条):{RESET}")
    if sim_ids:
        for i, sid in enumerate(sim_ids, 1):
            info(f"  [{i}] {sid}")
    else:
        warn("  未检索到相似题（知识库为空或匹配失败）")

    # ── 逐步工具调用轨迹 ─────────────────────────────────────────────────────
    trace = result.get("reasoning_trace", [])
    print(f"\n  {BOLD}工具调用轨迹 (共 {len(trace)} 条):{RESET}")
    for i, step in enumerate(trace, 1):
        step_type = step.get("type", "")
        step_no   = step.get("step", "?")
        if step_type == "tool_call":
            tool    = step.get("tool", "?")
            desc    = TOOL_DESC.get(tool, tool)
            args    = step.get("arguments", {})
            summary = step.get("result_summary", "")

            arg_parts = []
            import json
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except:
                    args = {}
                    
            if isinstance(args, dict):
                for k, v in args.items():
                    if k in ("is_training", "true_answer"):   # 内部注入参数不展示
                        continue
                    v_str = str(v)
                    arg_parts.append(f"{k}={v_str[:40]+'...' if len(v_str)>40 else v_str}")
            arg_str = ", ".join(arg_parts) if arg_parts else ""

            print(f"\n  {BOLD}  Step {step_no}-{i}: [{tool}]{RESET}  {CYAN}# {desc}{RESET}")
            if arg_str:
                info(f"    参数: {arg_str}")
            # 根据工具类型拆解摘要
            if "Error" in summary:
                fail(f"    结果: {summary}")
            elif tool == "get_learning_records":
                info(f"    结果: {summary}")
            elif tool in ("answer_by_id", "apply_strategy_by_id"):
                correct = "✓ 正确" if "is_correct=True" in summary else "✗ 错误"
                print(f"    {'  '+GREEN+correct+RESET if 'True' in summary else '  '+RED+correct+RESET}  {summary}")
            elif tool == "generate_final_answer":
                info(f"    结果: {summary}")
            else:
                info(f"    结果: {summary}")

        elif step_type == "agent_done":
            content = step.get("content", "")[:120]
            print(f"\n  {BOLD}  Step {step_no}-{i}: [agent 结束思考]{RESET}")
            info(f"    {content}")

    # ── 最终答案 ─────────────────────────────────────────────────────────────
    answer = result.get("answer") or result.get("raw_answer", "")
    print(f"\n  {BOLD}{'─'*54}")
    print(f"  最终答案:{RESET}")
    if answer:
        print(f"  {GREEN}{answer}{RESET}")
    else:
        warn("  (空 — generate_final_answer 未被调用或模型未遵循 <Answer> 格式)")


async def test_agent_full(sample_record=None, is_training=False):
    """Test 7: 用数据库样本或自定义问题做完整【多Agent编排】流程测试。"""
    section("Test 7 · 多Agent联合编排流程测试 (Router -> TableSage -> Viz)")

    # 准备更复杂的测试数据 (需要多步逻辑：过滤 + 聚合 + 比较)
    custom_question = (
        "Calculate the mean fare paid by the passengers."
    )
    custom_table = {
        "head": ["", "PassengerId", "Survived", "Pclass", "Name", "Sex", "Age", "SibSp", "Parch", "Ticket", "Fare", "Cabin", "Embarked", "AgeBand"],
        "rows": [
            ["0", "1", "0", "3", "Braund, Mr. Owen Harris", "male", "22.0", "1", "0", "A/5 21171", "7.25", "", "S", "2"],
            ["1", "2", "1", "1", "Cumings, Mrs. John Bradley (Florence Briggs Thayer)", "female", "38.0", "1", "0", "PC 17599", "71.2833", "C85", "C", "3"],
            ["2", "3", "1", "3", "Heikkinen, Miss. Laina", "female", "26.0", "0", "0", "STON/O2. 3101282", "7.925", "", "S", "2"],
            ["3", "4", "1", "1", "Futrelle, Mrs. Jacques Heath (Lily May Peel)", "female", "35.0", "1", "0", "113803", "53.1", "C123", "S", "3"],
            ["4", "5", "0", "3", "Allen, Mr. William Henry", "male", "35.0", "0", "0", "373450", "8.05", "", "S", "3"]
        ]
    }
    info(f"测试问题: {custom_question}")
    info(f"测试表格: {len(custom_table['rows'])} 行数据")

    try:
        from agent.router_agent import RouterAgent
        from agent.tablesage_agent import TableSageAgent
        from agent.visualization_agent import VisualizationAgent
        from mcp_client.connection import all_tools, call_tool, load_mcp_config, load_all_tools
        
        # 0. Initialize MCP Tools (Crucial for Visualization)
        load_mcp_config()
        await load_all_tools()
        
        # 1. Router 分析
        router = RouterAgent()
        plan = await router.analyze_intent(custom_question, has_cached_data=False)
        ok(f"Router 分析完成: needs_data={plan.get('needs_data_query')}, needs_viz={plan.get('needs_visualization')}")
        
        needs_data = plan.get("needs_data_query", True)
        needs_viz = plan.get("needs_visualization", False)
        core_q = plan.get("core_question", custom_question)
        viz_instr = plan.get("visualization_instruction", "生成图表")
        
        cached_data = None
        
        # 2. TableSage 答题 (如果需要)
        # Align with chat_api.py: force run if viz needed but no cache
        should_run_data = needs_data or (needs_viz and not cached_data)
        
        if should_run_data:
            info(f"触发 TableSageAgent 答题: {core_q}")
            agent = TableSageAgent(max_steps=15)
            t0 = time.time()
            result = agent.run(question=core_q, table=custom_table)
            elapsed = time.time() - t0
            _print_agent_result(result, elapsed, label="TableSage Result")
            cached_data = result # result IS the complete_result
        
        # 3. Visualization 绘图 (如果需要)
        if needs_viz:
            if cached_data:
                info(f"触发 VisualizationAgent 绘图: {viz_instr}")
                viz_agent = VisualizationAgent(mcp_tools=all_tools, tool_caller=call_tool)
                t0 = time.time()
                tool_calls = await viz_agent.generate_chart(custom_table, cached_data, viz_instr)
                elapsed = time.time() - t0
                
                if tool_calls and "none" not in [tc.get("name") for tc in tool_calls]:
                    ok(f"Visualization 完成 ({elapsed:.1f}s)，生成了 {len(tool_calls)} 个图表调用")
                    for tc in tool_calls:
                        if "content" in tc:
                            info(f"  图表结果 [{tc.get('name')}]: {tc.get('content')}")
                        elif "error" in tc:
                            fail(f"  图表调用失败 [{tc.get('name')}]: {tc.get('error')}")
                else:
                    warn(f"Visualization 未生成具体图表调用: {tool_calls}")
            else:
                fail("无法绘图：缺少答题数据上下文")

        ok("多Agent编排流程测试完成")
        record("多Agent编排流程", True, "Router -> TableSage -> Viz 链路通畅")
        return True

    except Exception as e:
        fail(f"多Agent流程测试失败: {e}")
        traceback.print_exc()
        record("多Agent编排流程", False, str(e))
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# （Test 8 已合并入 Test 7，此处保留占位以便 --test custom 选项向后兼容）
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# Test 8: Chat API 统一编排流程 (Unified Flow)
# ═══════════════════════════════════════════════════════════════════════════════
async def test_chat_api_unified():
    section("Test 8 · Chat API 统一编排流程 (Unified Flow)")
    
    from backend_api.chat_api import api_chat, QuestionRequest, TableData, result_cache
    
    test_table = TableData(
        header=["Name", "Score"],
        rows=[["Alice", 90], ["Bob", 80]]
    )
    
    # 场景 1: 输入校验 (无表格 + 无缓存)
    print(f"\n  {BOLD}8-1 输入校验测试 (空上下文){RESET}")
    empty_table = TableData(header=[], rows=[])
    req_empty = QuestionRequest(question="查看结果", table=empty_table)
    
    try:
        resp = await api_chat(req_empty)
        # StreamingResponse context manager helper
        async for line in resp.body_iterator:
            if not line or not line.strip():
                continue
            clean_line = line.strip()
            if clean_line.startswith("data: "):
                clean_line = clean_line[6:]
            if not clean_line:
                continue
                
            try:
                data = json.loads(clean_line)
            except json.JSONDecodeError:
                continue
            if data.get("step") == "error" and "上传" in data.get("error", ""):
                ok("校验通过：系统正确提醒用户上传表格")
                break
    except Exception as e:
        fail(f"输入校验测试异常: {e}")

    # 场景 2: 强制答题测试 (画图意图 + 无缓存 -> 自动触发答题)
    print(f"\n  {BOLD}8-2 强制答题测试 (画图但无缓存){RESET}")
    req_viz = QuestionRequest(question="画个成绩柱状图", table=test_table)
    
    # Mock Router 让其返回只有画图意图
    mock_plan = {
        "needs_data_query": False,
        "needs_visualization": True,
        "needs_report": False,
        "core_question": "学生的成绩分布如何？",
        "visualization_instruction": "生成柱状图"
    }
    
    with patch("backend_api.chat_api.router_agent.analyze_intent", AsyncMock(return_value=mock_plan)):
        # 同时 Mock TableSageAgent 的 run_stream 避免真实网络请求
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_stream.return_value = iter([
            {"step": "thinking", "content": "正在处理数据..."},
            {"step": "end", "complete_result": {"answer": "测试答案", "user_question": "学生的成绩分布如何？", "user_table": test_table.model_dump()}}
        ])
        
        with patch("backend_api.chat_api.TableSageAgent", return_value=mock_agent_instance):
            with patch("backend_api.chat_api.visualization_agent.generate_chart", AsyncMock(return_value=[{"name": "none", "message": "图表已生成", "content": "mock_chart"}])):
                resp = await api_chat(req_viz)
                steps_seen = []
                async for line in resp.body_iterator:
                    if not line or not line.strip():
                        continue
                    clean_line = line.strip()
                    if clean_line.startswith("data: "):
                        clean_line = clean_line[6:]
                    if not clean_line:
                        continue
                    try:
                        item = json.loads(clean_line)
                    except json.JSONDecodeError:
                        continue
                    steps_seen.append(item.get("step"))
                
                if "thinking" in steps_seen and "visualization_start" in steps_seen:
                    ok("逻辑正确：即使 needs_data_query 为 False，在无缓存时也自动触发了答题步骤")
                else:
                    fail(f"逻辑错误：预期包含 thinking 和 visualization_start, 实际步骤: {steps_seen}")

    # 场景 3: 缓存复用测试 (已有缓存 -> 跳过答题直接画图)
    print(f"\n  {BOLD}8-3 缓存复用测试 (多轮对话){RESET}")
    session_id = "test_session_123"
    result_cache[session_id] = {"answer": "旧的答案数据", "user_question": "Q1", "user_table": test_table.model_dump()}
    
    req_cache = QuestionRequest(question="再加个图", table=test_table, session_id=session_id)
    with patch("backend_api.chat_api.router_agent.analyze_intent", AsyncMock(return_value=mock_plan)):
        resp = await api_chat(req_cache)
        steps_seen = []
        async for line in resp.body_iterator:
            if not line or not line.strip():
                continue
            clean_line = line.strip()
            if clean_line.startswith("data: "):
                clean_line = clean_line[6:]
            if not clean_line:
                continue
            try:
                item = json.loads(clean_line)
            except json.JSONDecodeError:
                continue
            steps_seen.append(item.get("step"))
            
        if "thinking" not in steps_seen and "visualization_start" in steps_seen:
            ok("逻辑正确：检测到缓存后跳过了 TableSageAgent 答题步骤，直接进入绘图")
        else:
            fail(f"缓存复用失败: 预期跳过 thinking, 实际步骤: {steps_seen}")

    record("Chat API 统一编排流程", True, "验证了校验、强制答题及缓存复用逻辑")


# ═══════════════════════════════════════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════════════════════════════════════
def print_summary():
    section("测试汇总")
    passed = [r for r in RESULTS if r["passed"] is True]
    failed = [r for r in RESULTS if r["passed"] is False]
    skipped = [r for r in RESULTS if r["passed"] is None]

    for r in RESULTS:
        if r["passed"] is True:
            symbol = f"{GREEN}PASS{RESET}"
        elif r["passed"] is False:
            symbol = f"{RED}FAIL{RESET}"
        else:
            symbol = f"{YELLOW}SKIP{RESET}"
        print(f"  [{symbol}] {r['name']:<30} {r['detail']}")

    print(f"\n  {BOLD}总计: {GREEN}{len(passed)} 通过{RESET}  "
          f"{RED}{len(failed)} 失败{RESET}  "
          f"{YELLOW}{len(skipped)} 跳过{RESET}{BOLD}{RESET}")

    if failed:
        print(f"\n{RED}  存在失败项，请检查上方日志。{RESET}")
        sys.exit(1)
    else:
        print(f"\n{GREEN}  所有测试通过！{RESET}")


# ═══════════════════════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TableSage 集成测试")
    parser.add_argument("--test", default="all",
                        choices=["env", "db", "llm", "utils", "rag", "tools", "agent", "custom", "all"],
                        help="选择要运行的测试模块")
    args = parser.parse_args()
    t = args.test

    print(f"\n{BOLD}{'═'*60}")
    print(f"  TableSage 集成测试  [{time.strftime('%Y-%m-%d %H:%M:%S')}]")
    print(f"{'═'*60}{RESET}")

    # 始终运行环境检查
    env_ok = test_environment()

    sample_record = None
    similar_ids = None

    if t in ("db", "rag", "tools", "agent", "all"):
        sample_record = test_database()

    if t in ("llm", "agent", "custom", "all"):
        test_llm()

    if t in ("utils", "all"):
        test_utils()

    if t in ("rag", "tools", "agent", "all"):
        if sample_record:
            similar_ids = test_rag(sample_record)
        else:
            record("RAG 检索", None, "跳过（无 DB 数据）")

    if t in ("tools", "all"):
        if similar_ids:
            test_agent_tools(similar_ids)
        else:
            record("Agent 工具测试", None, "跳过（无 RAG 结果）")

    if t in ("agent", "custom", "all"):
        asyncio.run(test_agent_full())

    if t in ("all",):
        asyncio.run(test_chat_api_unified())

    print_summary()

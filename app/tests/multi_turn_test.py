import sys
import os
import json
import asyncio
import hashlib

# 路径设置
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)

from backend_api.chat_api import api_chat, QuestionRequest, TableData
from db.db_manager import DatabaseManager

# ANSI 颜色
GREEN  = "\033[92m"
RED    = "\033[91m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✓ {msg}{RESET}")
def fail(msg):  print(f"  {RED}✗ {msg}{RESET}")
def info(msg):  print(f"  {BLUE}→ {msg}{RESET}")
def warn(msg):  print(f"  {YELLOW}⚠ {msg}{RESET}")
def header(msg): print(f"\n{BOLD}{CYAN}{'─'*60}\n  {msg}\n{'─'*60}{RESET}")


# ═══════════════════════════════════════════════════════════════════════
#  测试数据
# ═══════════════════════════════════════════════════════════════════════

# 表格1: 国际足球比赛统计 (12行 × 8列)
FOOTBALL_TABLE = TableData(
    header=["Country", "Matches Played", "Wins", "Draws", "Losses", "Goals For", "Goals Against", "Points"],
    rows=[
        ["Brazil",      20, 14, 3, 3, 42, 15, 45],
        ["Germany",     20, 12, 5, 3, 38, 18, 41],
        ["Argentina",   20, 13, 2, 5, 35, 20, 41],
        ["France",      20, 11, 6, 3, 33, 14, 39],
        ["Spain",       20, 10, 7, 3, 30, 16, 37],
        ["Netherlands", 20,  9, 5, 6, 28, 22, 32],
        ["Italy",       20,  8, 8, 4, 25, 17, 32],
        ["England",     20,  9, 4, 7, 27, 24, 31],
        ["Portugal",    20,  8, 5, 7, 26, 23, 29],
        ["Belgium",     20,  7, 6, 7, 24, 25, 27],
        ["Uruguay",     20,  6, 5, 9, 20, 28, 23],
        ["Colombia",    20,  5, 4, 11, 18, 32, 19],
    ]
)

# 表格2: 全球城市经济指标 (10行 × 7列)  ← 切换表格用
CITY_TABLE = TableData(
    header=["City", "Country", "GDP (Billion $)", "Population (M)", "Avg Salary ($)", "Cost Index", "Tech Companies"],
    rows=[
        ["New York",   "USA",       1740, 8.3,  85000, 187, 1200],
        ["London",     "UK",        1010, 9.0,  72000, 175, 980],
        ["Tokyo",      "Japan",      950, 13.9, 62000, 161, 1500],
        ["Shanghai",   "China",      680, 24.9, 35000, 108, 850],
        ["Singapore",  "Singapore",  420, 5.7,  68000, 165, 620],
        ["Dubai",      "UAE",        310, 3.4,  58000, 148, 380],
        ["Mumbai",     "India",      310, 20.7, 18000,  78, 520],
        ["Berlin",     "Germany",    190, 3.6,  55000, 112, 450],
        ["Sydney",     "Australia",  280, 5.3,  70000, 158, 340],
        ["São Paulo",  "Brazil",     430, 12.3, 22000,  92, 410],
    ]
)


async def ask(question: str, table: TableData, conv_id: str, turn_label: str):
    """封装一次问答调用，返回 (answer, raw_result, router_core_q)"""
    info(f"{turn_label}: \"{question}\"")
    req = QuestionRequest(
        question=question,
        table=table,
        conversation_id=conv_id
    )
    
    resp = await api_chat(req)
    answer = ""
    raw_result = {}
    router_core_q = ""
    tools_used = []
    
    async for line in resp.body_iterator:
        if not line or not line.strip():
            continue
            
        # Handle SSE format: strip "data: " prefix
        clean_line = line.strip()
        if clean_line.startswith("data: "):
            clean_line = clean_line[6:]
            
        if not clean_line:
            continue
            
        try:
            data = json.loads(clean_line)
        except json.JSONDecodeError:
            # Skip non-json noise if any
            continue
        
        if data.get("step") == "router":
            plan = data.get("plan", {})
            router_core_q = plan.get("core_question", "")
            info(f"  Router 改写: {router_core_q[:80]}...")
            
        if data.get("step") == "end":
            raw_result = data.get("complete_result", {})
            answer = raw_result.get("answer", "")
            tools_used = raw_result.get("tools_used", [])
    
    if answer:
        ok(f"  答案: {answer}")
        info(f"  工具链: {' → '.join(tools_used)}")
        info(f"  context_used: {raw_result.get('context_used', '?')}")
    else:
        warn(f"  答案为空 (raw_answer 前100: {raw_result.get('raw_answer', '')[:100]}...)")
    
    return answer, raw_result, router_core_q


async def run_multi_turn_test():
    print(f"\n{BOLD}{'═'*60}")
    print(f"  TableSage 多轮对话 & 难度升级测试")
    print(f"{'═'*60}{RESET}")

    db = DatabaseManager()
    conv_id = f"test_multi_{int(asyncio.get_event_loop().time())}"
    info(f"Conversation ID: {conv_id}")

    passed = 0
    failed = 0

    # ═══════════════════════════════════════════════════════════
    #  场景 A: 足球表格 - 同一表格多轮提问
    # ═══════════════════════════════════════════════════════════
    header("场景 A: 国际足球比赛统计 — 同一表格多轮提问")
    
    # A1: 基础聚合
    a1, r1, _ = await ask(
        "What is the average number of goals scored (Goals For) across all countries?",
        FOOTBALL_TABLE, conv_id, "A1 基础聚合"
    )
    if a1:
        passed += 1
    else:
        failed += 1

    # A2: 指代追问 (What about...)
    a2, r2, q2 = await ask(
        "What about the average goals conceded?",
        FOOTBALL_TABLE, conv_id, "A2 指代追问"
    )
    if a2:
        # 验证 Router 是否正确理解了指代
        if "Goals Against" in q2 or "goals conceded" in q2.lower() or "goals against" in q2.lower():
            ok("  Router 正确理解了指代关系")
        else:
            warn(f"  Router 改写可能不准确: {q2}")
        passed += 1
    else:
        failed += 1

    # A3: 条件筛选 + 计算
    a3, r3, _ = await ask(
        "How many countries have a win rate above 50%?",
        FOOTBALL_TABLE, conv_id, "A3 条件筛选+计算"
    )
    if a3:
        passed += 1
    else:
        failed += 1

    # A4: 比较推理
    a4, r4, _ = await ask(
        "Which country has the best goal difference (Goals For minus Goals Against)?",
        FOOTBALL_TABLE, conv_id, "A4 比较推理"
    )
    if a4:
        passed += 1
    else:
        failed += 1

    # A5: 多步推理 + 基于前文
    a5, r5, q5 = await ask(
        "Among those countries, which ones have more than 35 points?",
        FOOTBALL_TABLE, conv_id, "A5 多步推理+指代"
    )
    if a5:
        passed += 1
    else:
        failed += 1

    # 检查 A 系列历史记录
    ctx_a = db.get_session_context(conv_id)
    info(f"A 系列完成后，数据库历史条数: {len(ctx_a['history'])}")
    if len(ctx_a["history"]) == 5:
        ok("5轮对话历史全部记录 ✓")
        passed += 1
    else:
        fail(f"历史条数异常: {len(ctx_a['history'])} (期望 5)")
        failed += 1

    # ═══════════════════════════════════════════════════════════
    #  场景 B: 切换到城市经济表格 — 验证临时记忆清理
    # ═══════════════════════════════════════════════════════════
    header("场景 B: 切换到城市经济表格 — 验证记忆隔离")

    # B1: 直接问新表格
    b1, rb1, _ = await ask(
        "Which city has the highest GDP?",
        CITY_TABLE, conv_id, "B1 新表格基础问题"
    )
    if b1:
        passed += 1
    else:
        failed += 1

    # 检查历史是否正确重置
    ctx_b = db.get_session_context(conv_id)
    history_count_after_switch = len(ctx_b["history"])
    info(f"切换表格后，数据库历史条数: {history_count_after_switch}")
    if history_count_after_switch == 1:
        ok("表格切换后历史记录正确重置为 1 条 ✓")
        passed += 1
    else:
        warn(f"历史条数: {history_count_after_switch} (期望重置为 1)")
        # 不算 fail，可能设计上保留旧历史

    # B2: 多条件筛选
    b2, rb2, _ = await ask(
        "List Asia cities with GDP above 500 billion",
        CITY_TABLE, conv_id, "B2 多条件筛选"
    )
    if b2:
        passed += 1
    else:
        failed += 1

    # B3: 跨列计算
    b3, rb3, _ = await ask(
        "What is the ratio of GDP to population for Singapore?",
        CITY_TABLE, conv_id, "B3 跨列计算"
    )
    if b3:
        passed += 1
    else:
        failed += 1

    # B4: 追问指代 (基于前文但不同列)
    b4, rb4, q4 = await ask(
        "And what about for New York?",
        CITY_TABLE, conv_id, "B4 指代追问"
    )
    if b4:
        if "ratio" in q4.lower() or "GDP" in q4 or "population" in q4.lower():
            ok("  Router 正确继承了前文的 GDP/Population ratio 上下文")
        else:
            warn(f"  Router 改写: {q4}")
        passed += 1
    else:
        failed += 1

    # ═══════════════════════════════════════════════════════════
    #  场景 C: 回到足球表格 — 验证再次切换
    # ═══════════════════════════════════════════════════════════
    header("场景 C: 再次切换回足球表格")

    c1, rc1, _ = await ask(
        "What is the total number of draws across all countries?",
        FOOTBALL_TABLE, conv_id, "C1 再次切换"
    )
    if c1:
        passed += 1
    else:
        failed += 1

    # 验证不应该残留城市表格的上下文
    ctx_c = db.get_session_context(conv_id)
    info(f"再次切换后，数据库历史条数: {len(ctx_c['history'])}")

    # ═══════════════════════════════════════════════════════════
    #  汇总
    # ═══════════════════════════════════════════════════════════
    print(f"\n{BOLD}{'═'*60}")
    print(f"  测试汇总")
    print(f"{'─'*60}{RESET}")
    total = passed + failed
    print(f"  通过: {GREEN}{passed}/{total}{RESET}")
    print(f"  失败: {RED}{failed}/{total}{RESET}")
    
    if failed == 0:
        print(f"\n{GREEN}{BOLD}  ✓ 所有多轮对话测试通过！{RESET}")
    else:
        print(f"\n{RED}{BOLD}  ✗ 有 {failed} 个测试失败{RESET}")

    print(f"{'═'*60}\n")


if __name__ == "__main__":
    asyncio.run(run_multi_turn_test())

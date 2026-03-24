"""
上下文大小审计脚本
==================
用 monkey-patch 拦截每个工具返回的完整内容，测量实际大小。
"""
import sys, os, json
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)

# ANSI
GREEN  = "\033[92m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# 收集每次工具调用的原始返回
tool_returns = []

# Monkey-patch _execute_tool
from agent.tablesage_agent import TableSageAgent
_original_execute = TableSageAgent._execute_tool

def _patched_execute(self, tool_name, arguments):
    result = _original_execute(self, tool_name, arguments)
    serialized = json.dumps(result, ensure_ascii=False, default=str)
    tool_returns.append({
        "tool": tool_name,
        "result": result,
        "serialized": serialized,
        "chars": len(serialized),
    })
    return result

TableSageAgent._execute_tool = _patched_execute

def main():
    custom_table = {
        "header": ["Student", "Math", "English", "Science"],
        "rows": [
            ["Alice",   92, 85, 88],
            ["Bob",     76, 90, 70],
            ["Charlie", 88, 78, 95],
            ["Diana",   60, 72, 65],
            ["Eve",     95, 88, 91],
            ["Frank",   73, 65, 80],
        ]
    }
    question = "What is the average score of the class in mathematics?"

    print(f"\n{BOLD}{'═'*70}")
    print(f"  上下文大小审计 - 实际工具返回内容测量")
    print(f"{'═'*70}{RESET}\n")

    agent = TableSageAgent(max_steps=15)
    
    # 跑完整流程
    for chunk in agent.run_stream(question=question, table=custom_table):
        step = chunk.get("step")
        if step == "rag_done":
            print(f"  {CYAN}RAG: {len(chunk.get('similar_questions', []))} 道相似题{RESET}")
        elif step == "tool_call":
            print(f"  {CYAN}→ 调用: {chunk.get('tool')}{RESET}")
        elif step == "end":
            print(f"  {GREEN}✓ 答案: {chunk.get('answer')}{RESET}")

    # ═══ 逐个工具返回详细分析 ═══
    print(f"\n{BOLD}{'═'*70}")
    print(f"  各工具返回内容详细分析")
    print(f"{'═'*70}{RESET}")
    
    total_chars = 0
    for i, tr in enumerate(tool_returns):
        tool = tr["tool"]
        chars = tr["chars"]
        tokens_est = chars // 4
        total_chars += chars
        
        print(f"\n{BOLD}┌─ [{i+1}] {tool} ── {chars} chars ≈ {tokens_est} tokens{RESET}")
        
        result = tr["result"]
        if isinstance(result, dict):
            for k, v in result.items():
                v_str = json.dumps(v, ensure_ascii=False, default=str)
                v_len = len(v_str)
                
                if v_len > 300:
                    tag = f"{RED}🔴 大"
                    preview = v_str[:200] + "..."
                elif v_len > 80:
                    tag = f"{YELLOW}🟡 中"
                    preview = v_str[:120] + ("..." if v_len > 120 else "")
                else:
                    tag = f"{GREEN}🟢 小"
                    preview = v_str
                    
                print(f"│  {tag}{RESET} {k} ({v_len} chars): {preview}")
        
        print(f"└{'─'*69}")

    # ═══ 汇总 ═══
    print(f"\n{BOLD}{'═'*70}")
    print(f"  汇 总")
    print(f"{'─'*70}{RESET}")
    for tr in tool_returns:
        bar_len = tr["chars"] // 100  # 每100 chars 一个 █
        bar = "█" * bar_len
        print(f"  {tr['tool']:<30} {tr['chars']:>6} chars {CYAN}{bar}{RESET}")
    print(f"{'─'*70}")
    print(f"  {'总计 (追加到 messages 的量)':<30} {total_chars:>6} chars ≈ {total_chars//4:>5} tokens")
    print(f"{'═'*70}\n")

if __name__ == "__main__":
    main()

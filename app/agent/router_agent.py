import os
import json
import logging
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
# allow configuration of a smaller/faster model for routing (defaulting to the same main model if not set)
ROUTER_LLM_MODEL = os.getenv("ROUTER_LLM_MODEL", os.getenv("LLM_MODEL", "deepseek-chat"))

class RouterAgent:
    """
    RouterAgent acts as the dispatcher for TableSage.
    It takes user input (which may include conversational text and multi-step instructions) 
    and classifies it into a structured intent execution plan, determining whether to trigger
    the Data Agent, Visualization Agent, or Report Agent.
    """
    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE or None,
        )
        self.model = ROUTER_LLM_MODEL

    async def analyze_intent(
        self, 
        user_input: str, 
        has_cached_data: bool, 
        table_schema: str = "",
        history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Analyze user input to determine the execution plan.
        Supports multi-turn context via history.
        """
        system_prompt = f"""You are the Router Agent for TableSage, an intelligent data analysis system.
Your job is to analyze the user's input and determine which specialized backend agents need to be invoked.
The available agents are:
1. Data Agent: Performs data calculation, filtering, or retrieval logic on the table.
2. Visualization Agent: Draws charts based on the result data or the raw table.
3. Report Agent: Generates a summary document.

Performance Optimization Rule:
- Set `needs_data_query` to FALSE if the user's primary request is to visualize or report on the data ALREADY provided or visible, without requiring any new filtering, sorting, or calculation. 
- Example: "Draw a pie chart" -> `needs_data_query`: false, `needs_visualization`: true.
- Example: "Who are the top 3 and draw a chart" -> `needs_data_query`: true, `needs_visualization`: true.

You MUST output your routing decision as a pure JSON object ONLY.

JSON Schema:
{{
  "needs_data_query": boolean,  // True ONLY if new data processing (filtering/math) is needed.
  "needs_visualization": boolean, // True if the user asks for a chart.
  "needs_report": boolean,      // True if the user specifically asks to generate a report.
  "core_question": "string",    // Self-contained query for the data agent.
  "visualization_instruction": "string" // Instructions for the viz agent.
}}

Crucial Context:
- has_cached_data: {has_cached_data} (If true, you can refer to previous turnover results).
- table_schema headers: {table_schema}
- conversation_history: {json.dumps(history or [], ensure_ascii=False)}
"""
        
        user_message = f"User Input: {user_input}"

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1
            )
            
            result_str = response.choices[0].message.content.strip()
            # Clean up potential markdown formatting from deepseek/gpt
            if result_str.startswith("```json"):
                result_str = result_str[7:]
            if result_str.startswith("```"):
                result_str = result_str[3:]
            if result_str.endswith("```"):
                result_str = result_str[:-3]
                
            return json.loads(result_str.strip())
        except Exception as e:
            logger.error(f"RouterAgent JSON parsing failed: {e}")
            # Fallback safe plan
            return {
                "needs_data_query": True, # Safest fallback is to query data
                "needs_visualization": False,
                "needs_report": False,
                "core_question": user_input, # Just pass the whole query to the agent
                "visualization_instruction": ""
            }

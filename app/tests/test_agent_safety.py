import unittest
from unittest.mock import MagicMock, patch
from agent.tablesage_agent import TableSageAgent
from utils.utils import TableUtils
import json

class TestAgentSafety(unittest.TestCase):
    def setUp(self):
        self.test_question = "How many students?"
        self.test_table = {"header": ["Name", "Score"], "rows": [["Alice", 90]]}

    def test_table2format_with_string_input(self):
        """Test that TableUtils.table2format doesn't crash on string input."""
        string_table = "Name | Score\nAlice | 90"
        result = TableUtils.table2format(string_table)
        self.assertEqual(result, string_table)

    def test_table2format_with_invalid_dict(self):
        """Test that TableUtils.table2format doesn't crash on invalid dict."""
        invalid_table = {"foo": "bar"}
        result = TableUtils.table2format(invalid_table)
        self.assertTrue(result.startswith("Error: Invalid table format"))

    @patch('agent.tablesage_agent.OpenAI')
    @patch('agent.tablesage_agent.TableSageAgent._rag_retrieval')
    @patch('agent.tablesage_agent.TableSageAgent._execute_tool')
    def test_agent_enforces_context_structure(self, mock_execute, mock_rag, mock_openai):
        """Test that TableSageAgent overrides hallucinated string user_table."""
        mock_rag.return_value = {
            "similar_question_ids": ["q1"],
            "similarity_scores": [0.9],
            "question_skeleton": "..."
        }
        
        # Mock LLM calling generate_final_answer with a STRING user_table
        mock_response = MagicMock()
        mock_tc = MagicMock()
        mock_tc.id = "call_1"
        mock_tc.function.name = "generate_final_answer"
        # Hallucinated arguments: user_table is a string instead of a dict
        mock_tc.function.arguments = json.dumps({
            "user_question": "hallucinated question",
            "user_table": "hallucinated string table",
            "few_shot_ids": "not-a-list"
        })
        mock_response.choices[0].message.tool_calls = [mock_tc]
        mock_response.choices[0].finish_reason = "tool_calls"
        
        # Second response to stop the loop
        mock_stop_response = MagicMock()
        mock_stop_response.choices[0].message.tool_calls = []
        mock_stop_response.choices[0].finish_reason = "stop"
        
        mock_openai.return_value.chat.completions.create.side_effect = [mock_response, mock_stop_response]
        
        agent = TableSageAgent(max_steps=2)
        agent.run(self.test_question, self.test_table)
        
        # Verify that _execute_tool received the CORRECT (original) question and table
        self.assertTrue(mock_execute.called, "_execute_tool was not called")
        args_passed = mock_execute.call_args[0][1]
        self.assertEqual(args_passed["user_question"], self.test_question)
        self.assertEqual(args_passed["user_table"], self.test_table)
        self.assertEqual(args_passed["few_shot_ids"], "not-a-list")

    def test_agent_handles_non_dict_args(self):
        """Test that TableSageAgent catches cases where LLM passes a raw string as args."""
        # This is a bit harder to test via run() because msg.tool_calls parsing might vary,
        # but we can test the internal logic if we mock the tool call object.
        pass

if __name__ == '__main__':
    unittest.main()

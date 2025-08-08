from db.db_manager import DatabaseManager
from utils.utils import TableUtils
from openai_api.openai_client import OpenAIClient

class AnsweringProcessor:
    def __init__(self, confidence_threshold=0.8):
        """
        Initialize the answering processor
        
        Args:
            confidence_threshold (float): Confidence threshold, below which strategic answering is required
        """
        self.db_manager = DatabaseManager()
        self.openai_client = OpenAIClient()
        self.table_utils = TableUtils()
        self.confidence_threshold = confidence_threshold
    
    def process_answering(self, top_results):
        """
        Process the answering workflow
        
        Args:
            top_results (list): Top N similar question records matched, containing table_id
            
        Returns:
            dict: Contains confidence and processing results
        """
        total_count = len(top_results)
        flag_0_count = 0
        
        flag_0_records = []
        other_flag_records = []
        not_found_ids = []

        for table_id in top_results:
            record = self.db_manager.get_learning_record(table_id)
            
            if record:
                if record.get("flag") == 0:
                    flag_0_records.append(table_id)
                    flag_0_count += 1
                else:
                    other_flag_records.append(table_id)
            else:
                not_found_ids.append(table_id)

        processed_results = []
        
        for table_id in other_flag_records:
            learning_record = self.db_manager.get_learning_record(table_id)
            if not learning_record:
                continue
                
            flag_value = learning_record.get("flag")
            rethink_summary = learning_record.get("rethink_summary", "")
            
            knowledge = self.db_manager.get_knowledge_by_id(table_id)
            if not knowledge:
                continue
                
            formatted_table = self.table_utils.table2format(knowledge["table"])
            question = knowledge.get("question", "")
            
            prompt = ""
            if flag_value == 1:
                prompt = self._build_guided_learning_prompt(question, formatted_table, rethink_summary)
            elif flag_value == 2:
                prompt = self._build_error_reflection_prompt(question, formatted_table, rethink_summary)
            
            messages = [{"role": "user", "content": prompt}]
            model_answer = self.openai_client.get_llm_response(messages)
            
            true_answer = knowledge.get("answer")
            is_correct = self.table_utils.is_answer_correct(model_answer, true_answer)
            
            if is_correct:
                flag_0_count += 1
            
            result_item = {
                "table_id": table_id,
                "is_correct": is_correct,
                "flag_unchanged": True,
                "model_answer": model_answer,
                "strategy_used": f"flag_{flag_value}"
            }
            processed_results.append(result_item)
        
        for table_id in not_found_ids:
            knowledge = self.db_manager.get_knowledge_by_id(table_id)
            
            if not knowledge:
                continue
                
            formatted_table = self.table_utils.table2format(knowledge["table"])

            question = knowledge.get("question", "")
            
            prompt = self._build_prompt(question, formatted_table)
            
            messages = [{"role": "user", "content": prompt}]
            model_answer = self.openai_client.get_llm_response(messages)
            
            true_answer = knowledge.get("answer")
            is_correct = self.table_utils.is_answer_correct(model_answer, true_answer)
            
            flag_value = 0 if is_correct else 3
            
            result_item = {
                "table_id": table_id,
                "is_correct": is_correct,
                "new_record": True,
                "flag": flag_value,
                "model_answer": model_answer
            }
            processed_results.append(result_item)
            
            self.db_manager.add_learning_record(table_id, flag_value)
            
            if is_correct:
                flag_0_count += 1
                
        confidence = flag_0_count / total_count if total_count > 0 else 0
        
        need_strategy = confidence < self.confidence_threshold
        
        incorrect_table_ids = []
        for result in processed_results:
            if not result["is_correct"]:
                incorrect_table_ids.append(result["table_id"])


        result = {
            "confidence": confidence,
            "flag_0_count": flag_0_count,
            "total_count": total_count,
            "need_strategy": need_strategy,
            "flag_0_records_count": len(flag_0_records),
            "other_flag_records": other_flag_records,
            "not_found": not_found_ids,
            "processed_results": processed_results,
            "incorrect_table_ids": incorrect_table_ids
        }
        
        return result
    
    def _build_guided_learning_prompt(self, question, formatted_table, rethink_summary):
        """
        Build prompt based on teacher-guided learning records (flag=1 case)
        
        Args:
            question (str): Question from knowledge base
            formatted_table (str): Formatted table
            rethink_summary (str): Learning reflection record under teacher guidance
            
        Returns:
            str: Built prompt
        """    

        prompt = f"""
        ### Task:
        You are given a table, a question, and a guided learning reflection. Use the guided learning reflection to help you answer the question correctly.
        
        ### Table:
        {formatted_table}
        
        ### Question:
        {question}
        
        ### Guided Learning Reflection:   
        {rethink_summary}
        
        ### Instructions:
        1. Read the guided learning reflection carefully to understand the correct approach and reasoning process.
        2. Apply the insights from the reflection to analyze the table and question.
        3. Identify the relevant data needed to answer the question and use the exact cell value(s) from the table.
        4. Carefully read the question to understand what type of answer is expected:
           - **Value-based questions**: Extract specific data from table.
           - **Yes/No questions**: Find values, then judge with 'yes'/'no'.
        
        **MANDATORY FORMAT REQUIREMENT**: You MUST put the final answer in the placeholder <Answer></Answer>, DO NOT include any explanation, reasoning, or additional text outside the Answer tags
        
        ### Example Answers:
        
        - For the question "scotland played their first match of the 1951 british home championship against which team?", the answer is <Answer>['England']</Answer> .
        - For another question "are there at least 2 nationalities on the chart?", the answer is <Answer>['yes']</Answer>.

        <Answer></Answer>
        """
        
        return prompt
    
    def _build_error_reflection_prompt(self, question, formatted_table, rethink_summary):
        """
        Build prompt based on student error reflection records (flag=2 case)
        
        Args:
            question (str): User question
            formatted_table (str): Formatted table
            rethink_summary (str): Student's self-summarized error reflection record
            
        Returns:
            str: Built prompt
        """

        prompt = f"""
        ### Task:
        You are given a table and a question. You have a self-reflection summary from your previous attempts to help you avoid the same mistakes.
        
        ### Table:
        {formatted_table}
        
        ### Question:
        {question}
        
        ### Self-Reflection Summary:
        {rethink_summary}
        
        ### Instructions:
        1. Carefully review your previous self-reflection to understand what went wrong and how to improve.
        2. Apply the lessons learned from your reflection to avoid repeating the same mistakes.
        3. Pay special attention to the specific errors or misconceptions identified in your reflection.
        4. Use the correct reasoning approach outlined in your self-reflection.
        5. Identify the relevant data needed to answer the question and use the exact cell value(s) from the table.
        
        **MANDATORY FORMAT REQUIREMENT**: You MUST put the final answer in the placeholder <Answer></Answer>, DO NOT include any explanation, reasoning, or additional text outside the Answer tags
        
        ### Example Answers:
        
        - For the question "scotland played their first match of the 1951 british home championship against which team?", the answer is <Answer>['England']</Answer> .
        - For another question "are there at least 2 nationalities on the chart?", the answer is <Answer>['yes']</Answer>.

        <Answer></Answer>
        """
        
        return prompt

    def _build_prompt(self, question, formatted_table):
        """
        Build prompt for letting the large model answer questions
        
        Args:
            question (str): User question
            formatted_table (str): Formatted table content
            
        Returns:
            str: Complete prompt
        """

        prompt = f"""
        ### Task:
        You are given a table and a question. Your goal is to answer the question using specific cell values from the table, ensuring the answer format matches the provided examples.
        
        ### Table Format:
        {formatted_table}
        
        ### Question:
        {question}
        
        ### Instructions:
        1. Carefully review the table structure, including headers and rows.
        2. Identify the relevant data needed to answer the question and use the exact cell value(s) from the table to answer the question.
        3. Carefully read the question to understand what type of answer is expected:
           - **Value-based questions**: Extract specific data from table.
           - **Yes/No questions**: Find values, then judge with 'yes'/'no'.
        
        **MANDATORY FORMAT REQUIREMENT**: You MUST put the final answer in the placeholder <Answer></Answer>, DO NOT include any explanation, reasoning, or additional text outside the Answer tags
        
        ### Example Answers:
        
        - For the question "scotland played their first match of the 1951 british home championship against which team?", the answer is <Answer>['England']</Answer> .
        - For another question "are there at least 2 nationalities on the chart?", the answer is <Answer>['yes']</Answer>.
        <Answer></Answer>

        """

        return prompt

    # def print_answering_results(self, result):
    #     """
    #     Print statistical information of answering process
        
    #     Args:
    #         result (dict): Result dictionary returned by process_answering method
    #     """
    #     print("\n" + "="*80)
    #     print("First Round Answering Statistics")
    #     print("="*80)
        
    #     confidence = result.get("confidence", 0)
    #     flag_0_count = result.get("flag_0_count", 0)
    #     total_count = result.get("total_count", 0)
    #     need_strategy = result.get("need_strategy", False)
        
    #     print(f"Total number of questions: {total_count}")
    #     print(f"Number of flag=0 questions: {flag_0_count}")
    #     print(f"Current confidence: {confidence:.2%}")
    #     print(f"Need strategic answering: {'Yes' if need_strategy else 'No'}")
        
    #     flag_0_records_count = result.get("flag_0_records_count", 0)
    #     other_flag_records = result.get("other_flag_records", [])
    #     not_found = result.get("not_found", [])
        
    #     print(f"\nRecord distribution:")
    #     print(f"  - Existing flag=0 records: {flag_0_records_count} questions")
    #     print(f"  - Records requiring strategic answers: {len(other_flag_records)} questions")
    #     print(f"  - New question records: {len(not_found)} questions")
        
    #     processed_results = result.get("processed_results", [])
    #     if processed_results:
    #         correct_count = sum(1 for r in processed_results if r["is_correct"])
    #         print(f"\nCurrent batch answer results: {correct_count}/{len(processed_results)} = {correct_count/len(processed_results):.2%}")
        
    #     print("="*80)

    # def _print_detailed_answers(self, processed_results):
    #     """
    #     Print detailed answer results for all questions, including questions, current answers and true answers
        
    #     Args:
    #         processed_results (list): Processing result list containing table_id and other information
    #     """
    #     print("\n" + "="*80)
    #     print("Question Answer Statistics")
    #     print("="*80)
        
    #     for i, result in enumerate(processed_results, 1):
    #         table_id = result["table_id"]
    #         is_correct = result["is_correct"]
            
    #         knowledge = self.db_manager.get_knowledge_by_id(table_id)
            
    #         if not knowledge:
    #             print(f"\nQuestion {i} [Table ID: {table_id}] - Data not found")
    #             continue
                
    #         question = knowledge.get("question", "Unknown question")
    #         true_answer = knowledge.get("answer", "Unknown answer")
    #         model_answer = result.get("model_answer", "Answer not saved")
            
    #         status = "✅ Correct" if is_correct else "❌ Incorrect"
    #         flag_info = ""
    #         if result.get("flag_unchanged"):
    #             flag_info = " [Flag unchanged]"
    #         elif result.get("new_record"):
    #             flag_info = f" [New record, Flag={result.get('flag', 3)}]"
            
    #         print(f"\nQuestion {i} [Table ID: {table_id}] {status}{flag_info}")
    #         print("-" * 60)
    #         print(f"Question: {question}")
    #         print(f"Model answer: {model_answer}")
    #         print(f"True answer: {true_answer}")

    #     print("="*80)

    
